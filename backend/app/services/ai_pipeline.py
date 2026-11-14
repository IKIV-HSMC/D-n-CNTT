"""Two-step AI pipeline: normalize source text, then build study artifacts."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.services.ollama_service import _split_text

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 7_000
MAX_SECTIONS = 120
MAX_OUTPUT_NODES = 250
MAX_OUTPUT_CARDS = 250


class AIServiceError(RuntimeError):
    """Provider unavailable or returned output that violates the pipeline contract."""


class KnowledgeSection(BaseModel):
    heading: str = Field(min_length=1, max_length=180)
    level: int = Field(default=1, ge=1, le=5)
    summary: str = Field(default="", max_length=1600)
    facts: list[str] = Field(default_factory=list, max_length=20)


class KnowledgeDocument(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    sections: list[KnowledgeSection] = Field(min_length=1, max_length=MAX_SECTIONS)


class MindmapNodeOutput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=1600)
    parent_id: str | None = Field(default=None, max_length=80)


class FlashcardOutput(BaseModel):
    front: str = Field(min_length=1, max_length=1000)
    back: str = Field(min_length=1, max_length=2000)
    node_id: str = Field(default="", max_length=80)


class MindmapOutput(BaseModel):
    nodes: list[MindmapNodeOutput] = Field(min_length=1, max_length=MAX_OUTPUT_NODES)


class PresentationDocument(BaseModel):
    mindmap: MindmapOutput
    flashcards: list[FlashcardOutput] = Field(default_factory=list, max_length=MAX_OUTPUT_CARDS)


ProgressCallback = Callable[[str, int], Awaitable[None]]


async def generate_learning_material(
    text: str,
    title: str,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run both AI steps and return a validated, frontend-compatible result."""
    chunks = _split_text(text, MAX_CHUNK_CHARS)
    sections: list[KnowledgeSection] = []
    summaries: list[str] = []
    normalized_title = title.strip() or "Tài liệu học tập"

    for index, chunk in enumerate(chunks, start=1):
        prompt = (
            f"Tài liệu: {normalized_title}\nĐoạn {index}/{len(chunks)}\n\n"
            "Hãy trích xuất các mục kiến thức có trong đoạn dưới đây. Bảo toàn thuật ngữ, "
            "không thêm kiến thức bên ngoài. Trả về đúng JSON theo schema: "
            '{"title":"...","summary":"...","sections":[{"heading":"...",'
            '"level":1,"summary":"...","facts":["..."]}]}\n\n'
            f"NỘI DUNG:\n{chunk}"
        )
        raw = await _call_provider(
            settings.AI_STEP1_PROVIDER,
            _model_name(settings.AI_STEP1_PROVIDER, settings.AI_STEP1_MODEL),
            "Bạn là trợ lý phân tích học liệu. Chỉ trả về JSON hợp lệ theo yêu cầu; "
            "không suy diễn ngoài nội dung nguồn.",
            prompt,
            response_schema=_knowledge_schema(),
        )
        try:
            knowledge_part = KnowledgeDocument.model_validate(_parse_json(raw))
        except (ValidationError, ValueError, TypeError) as exc:
            raise AIServiceError(f"AI bước 1 trả về dữ liệu không đúng schema (đoạn {index}).") from exc
        if index == 1 and knowledge_part.title.strip():
            normalized_title = knowledge_part.title.strip()
        if knowledge_part.summary.strip():
            summaries.append(knowledge_part.summary.strip())
        sections.extend(knowledge_part.sections)
        if len(sections) > MAX_SECTIONS:
            sections = sections[:MAX_SECTIONS]
        if on_progress is not None:
            await on_progress("ai_step1", min(80, 10 + round(index / len(chunks) * 70)))

    if not sections:
        raise AIServiceError("AI bước 1 không trích xuất được mục kiến thức nào.")

    knowledge = KnowledgeDocument(
        title=normalized_title,
        summary="\n\n".join(summaries)[:4000],
        sections=sections,
    )
    knowledge_json = knowledge.model_dump(mode="json")
    presentation_prompt = (
        "Từ JSON kiến thức đã chuẩn hóa, tạo mindmap dạng cây và flashcard để ôn tập. "
        "Chỉ dùng dữ kiện có trong JSON. Nhãn mindmap ngắn; mỗi flashcard có câu hỏi "
        "cụ thể và câu trả lời đầy đủ. Trả về đúng JSON: "
        '{"mindmap":{"nodes":[{"id":"n1","label":"...","description":"...",'
        '"parent_id":null}]},"flashcards":[{"front":"...","back":"...",'
        '"node_id":"n1"}]}\n\n'
        "JSON KIẾN THỨC:\n"
        + json.dumps(knowledge_json, ensure_ascii=False)
    )
    if on_progress is not None:
        await on_progress("ai_step2", 85)
    raw_presentation = await _call_provider(
        settings.AI_STEP2_PROVIDER,
        _model_name(settings.AI_STEP2_PROVIDER, settings.AI_STEP2_MODEL),
        "Bạn thiết kế mindmap và flashcard từ dữ liệu kiến thức đã được kiểm tra. "
        "Chỉ trả về JSON hợp lệ; không thêm nhận định ngoài nguồn.",
        presentation_prompt,
        response_schema=_presentation_schema(),
    )
    try:
        presentation = PresentationDocument.model_validate(_parse_json(raw_presentation))
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIServiceError("AI bước 2 trả về mindmap hoặc flashcard không đúng schema.") from exc

    nodes = _normalize_nodes(presentation.mindmap.nodes)
    cards = [
        card.model_dump()
        for card in presentation.flashcards
        if card.front.strip() and card.back.strip()
    ]
    node_ids = {node["id"] for node in nodes}
    fallback_node_id = nodes[0]["id"]
    for card in cards:
        if card["node_id"] not in node_ids:
            card["node_id"] = fallback_node_id
    if on_progress is not None:
        await on_progress("validating", 95)

    return {
        "knowledge": knowledge_json,
        "mindmap": {"nodes": nodes},
        "flashcards": cards,
        "mermaid": build_mermaid(normalized_title, nodes),
        "backend": "ai_pipeline",
        "model": (
            f"{settings.AI_STEP1_PROVIDER}/{_model_name(settings.AI_STEP1_PROVIDER, settings.AI_STEP1_MODEL)}"
            f" → {settings.AI_STEP2_PROVIDER}/{_model_name(settings.AI_STEP2_PROVIDER, settings.AI_STEP2_MODEL)}"
        ),
        "pipeline": {
            "step1_provider": settings.AI_STEP1_PROVIDER,
            "step1_model": _model_name(settings.AI_STEP1_PROVIDER, settings.AI_STEP1_MODEL),
            "step2_provider": settings.AI_STEP2_PROVIDER,
            "step2_model": _model_name(settings.AI_STEP2_PROVIDER, settings.AI_STEP2_MODEL),
            "chunk_count": len(chunks),
        },
    }


def _model_name(provider: str, configured_model: str) -> str:
    model = configured_model.strip()
    if provider == "ollama":
        return model or settings.OLLAMA_MODEL
    return model


async def _call_provider(
    provider: str,
    model: str,
    system: str,
    prompt: str,
    response_schema: dict[str, Any],
) -> str:
    if provider not in {"ollama", "gemini", "openai"}:
        raise AIServiceError(f"AI provider không được hỗ trợ: {provider}")
    if not model:
        raise AIServiceError(f"Hãy cấu hình model cho provider {provider}.")

    timeout = httpx.Timeout(settings.AI_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "ollama":
                response = await client.post(
                    f"{settings.OLLAMA_HOST.rstrip('/')}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 8192},
                    },
                )
                response.raise_for_status()
                return response.json().get("message", {}).get("content", "")

            if provider == "openai":
                if not settings.OPENAI_API_KEY:
                    raise AIServiceError("Chưa cấu hình OPENAI_API_KEY.")
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            if not settings.GEMINI_API_KEY:
                raise AIServiceError("Chưa cấu hình GEMINI_API_KEY.")
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json={
                    "model": model,
                    "input": prompt,
                    "system_instruction": system,
                    "response_format": {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": response_schema,
                    },
                    "generation_config": {"temperature": 0.2, "max_output_tokens": 8192},
                    "store": False,
                },
            )
            response.raise_for_status()
            steps = response.json().get("steps", [])
            text_parts = [
                part["text"]
                for step in steps
                if step.get("type") == "model_output"
                for part in step.get("content", [])
                if part.get("type") == "text" and isinstance(part.get("text"), str)
            ]
            if not text_parts:
                raise AIServiceError("Gemini không trả về nội dung JSON.")
            return "\n".join(text_parts)
    except AIServiceError:
        raise
    except httpx.TimeoutException as exc:
        raise AIServiceError(f"AI provider {provider} xử lý quá thời gian cho phép.") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("AI provider %s trả HTTP %s", provider, exc.response.status_code)
        raise AIServiceError(f"AI provider {provider} trả về HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.exception("Không gọi được AI provider %s", provider)
        raise AIServiceError(f"Không thể nhận kết quả hợp lệ từ AI provider {provider}.") from exc


def _parse_json(raw: Any) -> Any:
    if not isinstance(raw, str):
        raise AIServiceError("AI provider không trả về văn bản JSON.")
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _normalize_nodes(items: list[MindmapNodeOutput]) -> list[dict[str, Any]]:
    source = items[:MAX_OUTPUT_NODES]
    nodes = [item.model_dump() for item in source]
    if not nodes:
        raise AIServiceError("AI bước 2 không tạo được nút mindmap.")

    used_ids: set[str] = set()
    for index, node in enumerate(nodes, start=1):
        node_id = node["id"].strip()
        if not node_id or node_id in used_ids:
            node_id = f"node-{index}"
        node["id"] = node_id
        used_ids.add(node_id)

    root_id = nodes[0]["id"]
    known_ids = {node["id"] for node in nodes}
    nodes[0]["parent_id"] = None
    for node in nodes[1:]:
        parent_id = node["parent_id"]
        if parent_id not in known_ids or parent_id == node["id"]:
            node["parent_id"] = root_id

    # Break longer parent cycles so tree rendering and Mermaid generation terminate.
    by_id = {node["id"]: node for node in nodes}
    for node in nodes[1:]:
        seen = {node["id"]}
        parent_id = node["parent_id"]
        while parent_id is not None and parent_id != root_id:
            if parent_id in seen or parent_id not in by_id:
                node["parent_id"] = root_id
                break
            seen.add(parent_id)
            parent_id = by_id[parent_id]["parent_id"]
    return nodes


def build_mermaid(title: str, nodes: list[dict[str, Any]]) -> str:
    """Build Mermaid from validated nodes so model output cannot inject directives."""
    def safe_label(value: str) -> str:
        value = re.sub(r"[\r\n\[\]{}();#\"`|]", " ", value)
        return re.sub(r"\s+", " ", value).strip()[:100] or "Ý chính"

    children: dict[str | None, list[dict[str, Any]]] = {}
    lines = ["mindmap", f"  root(({safe_label(title)}))"]
    if not nodes:
        return "\n".join(lines)

    root_id = nodes[0]["id"]
    for node in nodes:
        parent = node["parent_id"]
        if node["id"] == root_id:
            parent = None
        children.setdefault(parent, []).append(node)

    visited: set[str] = set()

    def add_children(parent_id: str | None, depth: int) -> None:
        for node in children.get(parent_id, []):
            if node["id"] in visited:
                continue
            visited.add(node["id"])
            lines.append(f"{'  ' * (depth + 1)}{safe_label(node['label'])}")
            add_children(node["id"], depth + 1)

    add_children(None, 0)
    return "\n".join(lines)


def _knowledge_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "level": {"type": "integer"},
                        "summary": {"type": "string"},
                        "facts": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["heading", "level", "summary", "facts"],
                },
            },
        },
        "required": ["title", "summary", "sections"],
    }


def _presentation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "mindmap": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                                "parent_id": {"type": ["string", "null"]},
                            },
                            "required": ["id", "label", "description", "parent_id"],
                        },
                    }
                },
                "required": ["nodes"],
            },
            "flashcards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "front": {"type": "string"},
                        "back": {"type": "string"},
                        "node_id": {"type": "string"},
                    },
                    "required": ["front", "back", "node_id"],
                },
            },
        },
        "required": ["mindmap", "flashcards"],
    }
