"""
api.py – FastAPI nhận JSON trích xuất, trả mindmap + flashcards.

Chạy standalone:
  uvicorn api:app --reload   (cần: pip install fastapi uvicorn httpx)

BACKEND = "engine"  → dùng mindmap_engine (CPU, offline, không cần Ollama)
BACKEND = "model"   → gọi Ollama đang chạy local (cần: ollama serve)

Biến môi trường (tùy chọn):
  OLLAMA_HOST   = http://localhost:11434
  OLLAMA_MODEL  = mindmap-model
  OLLAMA_TIMEOUT = 120
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, status
from mindmap_engine import generate, to_reactflow

logger = logging.getLogger(__name__)

BACKEND = "model"  # "engine" | "model"

# ── Ollama config ──────────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mindmap-model")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

SYSTEM_PROMPT = (
    "Bạn là chuyên gia tóm tắt học liệu. Từ đoạn tài liệu, trả về DUY NHẤT một JSON: "
    '{"mindmap":{"nodes":[{"id","label","parent_id"}]},'
    '"flashcards":[{"front","back","node_id"}]}. '
    "Node gốc có parent_id=null, nhãn ngắn (<=8 từ), "
    "flashcard hỏi-đáp chính xác theo nội dung."
)

app = FastAPI(title="Doc → Mindmap & Flashcards")


# ── Ollama helper ──────────────────────────────────────────────────────────────

async def _call_ollama(text: str) -> dict[str, Any]:
    """Gọi Ollama /api/chat, trả về parsed JSON từ model."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 1024},
    }
    async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT) as client:
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Không kết nối được Ollama tại {OLLAMA_HOST}. "
                    "Chạy 'ollama serve' và 'ollama create mindmap-model' trước."
                ),
            ) from exc

    raw = resp.json().get("message", {}).get("content", "").strip()

    # Strip code fence nếu có
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.startswith("```"))

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Model trả về text không phải JSON: %s", raw[:200])
        # Fallback: đưa text thô vào engine để vẫn có kết quả
        return {"extracted_text": raw}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    """Kiểm tra Ollama và model sẵn sàng chưa."""
    async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=5.0) as client:
        try:
            r = await client.get("/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {
                "status": "ok",
                "backend": BACKEND,
                "ollama_running": True,
                "models": models,
                "mindmap_model_ready": any(OLLAMA_MODEL in m for m in models),
            }
        except (httpx.ConnectError, httpx.HTTPStatusError):
            return {
                "status": "degraded",
                "backend": BACKEND,
                "ollama_running": False,
                "models": [],
                "mindmap_model_ready": False,
            }


@app.post("/api/generate")
async def api_generate(doc: dict) -> dict:
    """
    Nhận JSON tài liệu đã trích xuất, trả về mindmap + flashcards + reactflow.

    Body tối thiểu: {"extracted_text": "<nội dung văn bản>"}
    """
    if BACKEND == "engine":
        # Chế độ CPU-only, không cần Ollama
        out = generate(doc)
    else:
        # Chế độ model: gọi Ollama
        text = doc.get("extracted_text") or json.dumps(doc, ensure_ascii=False)

        # Cắt nếu quá dài (Qwen2 1.5B: context 8192 tokens ≈ ~16000 ký tự)
        if len(text) > 12000:
            text = text[:12000]

        model_out = await _call_ollama(text)

        if "mindmap" in model_out:
            # Model trả JSON đúng → dùng thẳng
            out = model_out
        else:
            # Fallback: đưa vào engine CPU
            out = generate(model_out if "extracted_text" in model_out else {"extracted_text": text})

    # Thêm ReactFlow
    if "mindmap" in out:
        try:
            out["reactflow"] = to_reactflow(out["mindmap"])
        except Exception:
            pass

    return out
