"""
ollama_service.py – Gọi model Qwen2 đã fine-tune qua Ollama HTTP API.

Model: mindmap-model (Qwen2 1.5B, fine-tuned bằng QLoRA)
Ollama phải đang chạy: `ollama serve`

Env vars có thể override trong .env:
  OLLAMA_HOST   = http://localhost:11434   (default)
  OLLAMA_MODEL  = mindmap-model            (default)
  OLLAMA_TIMEOUT = 120                     (seconds, default)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# System prompt – yêu cầu AI sinh description cho mỗi node
SYSTEM_PROMPT = (
    "Bạn là chuyên gia tóm tắt học liệu. Từ đoạn tài liệu, trả về DUY NHẤT một JSON: "
    '{"mindmap":{"nodes":[{"id":"1","label":"Tên khái niệm ngắn","description":"Giải thích 1-2 câu rõ ràng","parent_id":null},...]},'
    '"flashcards":[{"front":"Câu hỏi?","back":"Trả lời","node_id":"1"}]}. '
    "Quy tắc: id dạng số nguyên; label tối đa 8 từ; description bắt buộc – giải thích cụ thể khái niệm; "
    "node gốc có parent_id=null; flashcard chính xác theo nội dung. "
    "CHỈ TRẢ VỀ JSON HỢP LỆ, không markdown, không giải thích thêm."
)

# Giới hạn độ dài chunk gửi lên model (tokens ≈ chars / 2 với tiếng Việt)
MAX_CHUNK_CHARS = 3000


class OllamaServiceError(Exception):
    """Lỗi khi gọi Ollama."""


async def _call_ollama(prompt: str) -> str:
    """Gửi một prompt tới Ollama, trả về chuỗi kết quả của model."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 2048,
        },
    }

    async with httpx.AsyncClient(
        base_url=settings.OLLAMA_HOST,
        timeout=settings.OLLAMA_TIMEOUT,
    ) as client:
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise OllamaServiceError(
                f"Không kết nối được Ollama tại {settings.OLLAMA_HOST}. "
                "Hãy chạy 'ollama serve' và 'ollama create mindmap-model'."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaServiceError(
                f"Ollama trả lỗi HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc

    data = resp.json()
    return data.get("message", {}).get("content", "")


def _parse_model_output(raw: str) -> dict[str, Any]:
    """Parse JSON từ output model; fallback trả về dict rỗng nếu không hợp lệ."""
    raw = raw.strip()

    # Model đôi khi bọc JSON trong code fence ```json ... ```
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            line for line in lines if not line.startswith("```")
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Model output không phải JSON hợp lệ, trả về dict rỗng.")
        return {}


async def generate_mindmap_from_text(extracted_text: str) -> dict[str, Any]:
    """
    Sinh mindmap + flashcards từ extracted_text dùng Ollama.

    Nếu text quá dài, cắt thành chunks, gọi model nhiều lần rồi merge kết quả.

    Returns:
        {
          "mindmap": {"nodes": [...]},
          "flashcards": [...],
          "backend": "ollama",
          "model": "<model_name>"
        }
    """
    # Cắt thành chunks để tránh vượt context window
    chunks = _split_text(extracted_text, MAX_CHUNK_CHARS)

    all_nodes: list[dict] = []
    all_flashcards: list[dict] = []
    node_id_offset = 0

    for idx, chunk in enumerate(chunks):
        logger.info("Gọi Ollama chunk %d/%d ...", idx + 1, len(chunks))
        raw = await _call_ollama(chunk)
        parsed = _parse_model_output(raw)

        # Merge nodes (offset id để tránh trùng)
        nodes = parsed.get("mindmap", {}).get("nodes", [])
        cards = parsed.get("flashcards", [])

        for node in nodes:
            orig_id = node.get("id")
            new_id = (node_id_offset + int(orig_id)) if str(orig_id).isdigit() else f"{idx}_{orig_id}"
            node["id"] = str(new_id)
            if node.get("parent_id") not in (None, "null"):
                try:
                    node["parent_id"] = str(node_id_offset + int(node["parent_id"]))
                except (ValueError, TypeError):
                    node["parent_id"] = f"{idx}_{node['parent_id']}"
            all_nodes.append(node)

        for card in cards:
            if card.get("node_id") and str(card["node_id"]).isdigit():
                card["node_id"] = str(node_id_offset + int(card["node_id"]))
            else:
                card["node_id"] = f"{idx}_{card.get('node_id', '')}"
            all_flashcards.append(card)

        node_id_offset += len(nodes)

    return {
        "mindmap": {"nodes": all_nodes},
        "flashcards": all_flashcards,
        "backend": "ollama",
        "model": settings.OLLAMA_MODEL,
    }


async def check_ollama_health() -> dict[str, Any]:
    """Kiểm tra Ollama đang chạy và model đã được load."""
    async with httpx.AsyncClient(
        base_url=settings.OLLAMA_HOST,
        timeout=10.0,
    ) as client:
        try:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            has_model = any(settings.OLLAMA_MODEL in m for m in models)
            return {
                "ollama_running": True,
                "models_available": models,
                "mindmap_model_loaded": has_model,
            }
        except (httpx.ConnectError, httpx.HTTPStatusError):
            return {
                "ollama_running": False,
                "models_available": [],
                "mindmap_model_loaded": False,
            }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_text(text: str, max_chars: int) -> list[str]:
    """Cắt text thành chunks không quá max_chars ký tự, ưu tiên cắt ở ranh giới đoạn."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).lstrip("\n")
        else:
            if current:
                chunks.append(current.strip())
            # Nếu chính đoạn văn còn quá dài thì cắt thẳng
            while len(para) > max_chars:
                chunks.append(para[:max_chars].strip())
                para = para[max_chars:]
            current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks
