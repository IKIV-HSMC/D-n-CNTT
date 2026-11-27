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
            "Phân tích nội dung đoạn tài liệu và nhóm các ý theo chủ đề/khái niệm, không tạo một mục riêng cho từng câu hoặc từng dòng. "
            "Bảo toàn định nghĩa, luận điểm, điều kiện, quy trình, ví dụ, số liệu và quan hệ nguyên nhân-kết quả có trong nguồn. "
            "Mỗi fact phải đủ ngữ cảnh để người đọc hiểu khi đứng riêng; giữ lại một cụm dẫn chứng ngắn từ tài liệu khi cần. "
            "Nếu đây là thơ hoặc văn học, tổ chức theo chủ đề, mạch nội dung/cảm xúc, hình ảnh, biện pháp nghệ thuật và tác dụng "
            "khi có căn cứ; không biến từng câu thơ thành nhánh chính và không khẳng định ý nghĩa không được văn bản hỗ trợ. "
            "Không thêm kiến thức bên ngoài. Trả về tiếng Việt nếu nguồn là tiếng Việt và đúng JSON theo schema: "
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
            parsed = _parse_json(raw)
            healed = _heal_knowledge_payload(parsed, normalized_title, chunk)
            knowledge_part = KnowledgeDocument.model_validate(healed)
        except Exception as exc:
            logger.warning("AI bước 1 đoạn %s lỗi schema (%s), tự động phục hồi", index, exc)
            try:
                fallback_healed = _heal_knowledge_payload({}, normalized_title, chunk)
                knowledge_part = KnowledgeDocument.model_validate(fallback_healed)
            except Exception as exc2:
                logger.warning("AI bước 1 đoạn %s fallback cũng lỗi (%s), bỏ qua đoạn này", index, exc2)
                continue
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
        "Chỉ dùng dữ kiện có trong JSON. Mindmap phải thể hiện đủ các ý quan trọng và quan hệ giữa chúng: "
        "một nút gốc, các nhánh chính theo chủ đề, rồi nút con cho luận điểm, chi tiết, ví dụ hoặc dẫn chứng. "
        "Không làm sơ đồ phẳng bằng cách đưa mọi câu hoặc mọi dòng thành nhánh ngang hàng; không lặp ý. "
        "Nhãn nút ngắn, mô tả của mỗi nút giải thích rõ nội dung và ngữ cảnh bằng câu hoàn chỉnh. "
        "Với thơ/văn học, ưu tiên chủ đề, mạch cảm xúc/nội dung, hình ảnh, biện pháp nghệ thuật và tác dụng "
        "được hỗ trợ bởi văn bản; không tự suy diễn.\n"
        "Flashcard phải là câu hỏi-đáp án rõ ràng, tự hiểu được khi xem riêng: câu hỏi nêu đúng chủ đề/ngữ cảnh; "
        "mỗi thẻ hỏi một ý; đáp án trả lời trực tiếp rồi giải thích ngắn bằng dữ kiện nguồn. "
        "Không tạo câu hỏi điền từ ngẫu nhiên, câu hỏi mơ hồ kiểu 'nói về điều gì', hoặc thẻ trùng lặp. "
        "Trả về tiếng Việt nếu nguồn là tiếng Việt và đúng JSON: "
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
        parsed_pres = _parse_json(raw_presentation)
        healed_pres = _heal_presentation_payload(parsed_pres, normalized_title, knowledge=knowledge)
        presentation = PresentationDocument.model_validate(healed_pres)
    except Exception as exc:
        logger.warning("AI bước 2 lỗi schema (%s), tự động phục hồi", exc)
        fallback_pres = _heal_presentation_payload({}, normalized_title, knowledge=knowledge)
        presentation = PresentationDocument.model_validate(fallback_pres)

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
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "format": response_schema if response_schema else "json",
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 8192},
                }
                try:
                    response = await client.post(
                        f"{settings.OLLAMA_HOST.rstrip('/')}/api/chat",
                        json=payload,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as err:
                    if err.response.status_code == 400 and payload["format"] != "json":
                        payload["format"] = "json"
                        response = await client.post(
                            f"{settings.OLLAMA_HOST.rstrip('/')}/api/chat",
                            json=payload,
                        )
                        response.raise_for_status()
                    else:
                        raise
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
        return {}
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
        return {}


def _heal_knowledge_payload(data: Any, default_title: str, chunk: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}

    for root_key in ("knowledge", "data", "result", "output", "document"):
        if root_key in data and isinstance(data[root_key], dict) and "sections" in data[root_key]:
            data = data[root_key]
            break

    title = str(data.get("title") or default_title or "Tài liệu học tập").strip()[:200]
    if not title:
        title = "Tài liệu học tập"

    summary = str(data.get("summary") or "").strip()[:4000]

    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        raw_sections = []
        for k, v in data.items():
            if isinstance(v, list) and v:
                raw_sections = v
                break

    clean_sections = []
    for idx, s in enumerate(raw_sections, 1):
        if not isinstance(s, dict):
            continue
        heading = (
            s.get("heading")
            or s.get("title")
            or s.get("name")
            or s.get("topic")
            or s.get("label")
            or ""
        )
        heading = str(heading).strip()[:180]
        if not heading:
            heading = f"Mục kiến thức {idx}"

        try:
            level = int(s.get("level", 1))
            if level < 1:
                level = 1
            elif level > 5:
                level = 5
        except (ValueError, TypeError):
            level = 1

        sec_summary = str(s.get("summary") or s.get("description") or "").strip()[:1600]

        raw_facts = s.get("facts") or s.get("points") or s.get("details") or []
        if isinstance(raw_facts, str):
            raw_facts = [line.strip() for line in raw_facts.split("\n") if len(line.strip()) > 3]
        elif not isinstance(raw_facts, list):
            raw_facts = []

        clean_facts = [str(f).strip()[:500] for f in raw_facts if str(f).strip()]
        if not clean_facts and sec_summary:
            clean_facts = [sec_summary[:300]]

        clean_sections.append({
            "heading": heading,
            "level": level,
            "summary": sec_summary,
            "facts": clean_facts[:20],
        })

    if not clean_sections:
        lines = [l.strip() for l in chunk.split("\n") if len(l.strip()) > 5 and not l.strip().startswith("<")]
        fb_heading = lines[0][:80] if lines else "Nội dung trọng tâm"
        fb_facts = lines[1:5] if len(lines) > 1 else [chunk[:200]]
        clean_sections.append({
            "heading": fb_heading,
            "level": 1,
            "summary": summary or (lines[0] if lines else ""),
            "facts": fb_facts,
        })

    return {
        "title": title,
        "summary": summary,
        "sections": clean_sections[:MAX_SECTIONS],
    }


def _heal_presentation_payload(
    data: Any,
    default_title: str,
    knowledge: KnowledgeDocument | None = None,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}

    for root_key in ("presentation", "data", "result", "output"):
        if root_key in data and isinstance(data[root_key], dict) and "mindmap" in data[root_key]:
            data = data[root_key]
            break

    mindmap = data.get("mindmap")
    if not isinstance(mindmap, dict):
        mindmap = {}

    raw_nodes = mindmap.get("nodes")
    if not isinstance(raw_nodes, list):
        raw_nodes = []

    clean_nodes = []
    for idx, n in enumerate(raw_nodes, 1):
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or f"node-{idx}").strip()
        label = str(n.get("label") or n.get("title") or n.get("name") or "").strip()[:180]
        if not label:
            label = f"Nhánh {idx}"
        desc = str(n.get("description") or n.get("summary") or "").strip()[:1600]
        pid = n.get("parent_id")
        if pid is not None:
            pid = str(pid).strip()
        clean_nodes.append({
            "id": nid,
            "label": label,
            "description": desc,
            "parent_id": pid,
        })

    # Cứu hộ thông minh: Nếu AI không trả về nodes hoặc chỉ trả về <= 1 node,
    # tự động dựng toàn bộ cây Mindmap từ các Section & Facts đã trích xuất ở Bước 1
    if len(clean_nodes) <= 1 and knowledge and knowledge.sections:
        clean_nodes = [
            {
                "id": "root",
                "label": default_title[:100] or "Chủ đề chính",
                "description": knowledge.summary or "Tổng quan tài liệu",
                "parent_id": None,
            }
        ]
        for s_idx, sec in enumerate(knowledge.sections[:MAX_SECTIONS], 1):
            sec_id = f"s{s_idx}"
            clean_nodes.append({
                "id": sec_id,
                "label": sec.heading[:180],
                "description": sec.summary or sec.heading,
                "parent_id": "root",
            })
            for f_idx, fact in enumerate(sec.facts[:6], 1):
                clean_nodes.append({
                    "id": f"{sec_id}_f{f_idx}",
                    "label": fact[:100],
                    "description": fact,
                    "parent_id": sec_id,
                })

    if not clean_nodes:
        clean_nodes.append({
            "id": "root",
            "label": default_title[:100] or "Chủ đề chính",
            "description": "Nội dung tổng quan",
            "parent_id": None,
        })

    raw_cards = data.get("flashcards")
    if not isinstance(raw_cards, list):
        raw_cards = []

    node_ids = {n["id"] for n in clean_nodes}
    fb_id = clean_nodes[0]["id"]
    clean_cards = []
    for idx, c in enumerate(raw_cards, 1):
        if not isinstance(c, dict):
            continue
        front = str(c.get("front") or c.get("question") or "").strip()[:1000]
        back = str(c.get("back") or c.get("answer") or "").strip()[:2000]
        nid = str(c.get("node_id") or fb_id).strip()
        if nid not in node_ids:
            nid = fb_id
        if front and back:
            clean_cards.append({
                "front": front,
                "back": back,
                "node_id": nid,
            })

    # Cứu hộ Flashcards: Nếu AI bước 2 không tạo flashcard, tự động tạo từ sections & facts
    if not clean_cards and knowledge and knowledge.sections:
        for s_idx, sec in enumerate(knowledge.sections[:30], 1):
            sec_id = f"s{s_idx}" if f"s{s_idx}" in node_ids else fb_id
            if sec.summary:
                clean_cards.append({
                    "front": f"Khái niệm / mục đích của {sec.heading} là gì?",
                    "back": sec.summary,
                    "node_id": sec_id,
                })
            for fact in sec.facts[:2]:
                if len(clean_cards) >= MAX_OUTPUT_CARDS:
                    break
                clean_cards.append({
                    "front": f"Điểm mấu chốt trong {sec.heading} là gì?",
                    "back": fact,
                    "node_id": sec_id,
                })

    return {
        "mindmap": {"nodes": clean_nodes[:MAX_OUTPUT_NODES]},
        "flashcards": clean_cards[:MAX_OUTPUT_CARDS],
    }


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
    known_ids = {node["id"] for node in nodes}
    for node in nodes:
        # The first node is represented by the Mermaid root declaration above.
        # Adding it to the child list creates a second root and makes Mermaid fail.
        if node["id"] == root_id:
            continue
        parent = node["parent_id"]
        if parent not in known_ids or parent == node["id"]:
            parent = root_id
        children.setdefault(parent, []).append(node)

    visited: set[str] = set()

    def add_children(parent_id: str | None, depth: int) -> None:
        for node in children.get(parent_id, []):
            if node["id"] in visited:
                continue
            visited.add(node["id"])
            lines.append(f"{'  ' * (depth + 1)}{safe_label(node['label'])}")
            add_children(node["id"], depth + 1)

    # Mermaid's declared root is indented by two spaces, so its first-level
    # branches must start at four spaces (and each descendant adds two more).
    add_children(root_id, 1)
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
