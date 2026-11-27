"""
mindmap.py – Endpoint sinh Mindmap + Flashcards từ tài liệu đã upload.

POST  /api/mindmap/{document_id}         → sinh mới (engine hoặc pipeline AI hai bước)
GET   /api/mindmap/{document_id}         → lấy kết quả đã lưu
GET   /api/mindmap/{document_id}/reactflow → lấy định dạng ReactFlow
GET   /api/mindmap/health                → kiểm tra Ollama

Flow:
  1. Lấy document từ DB (phải ở status=extracted)
  2. Pipeline AI: knowledge JSON → mindmap/Mermaid/flashcards
  3. Chuyển mindmap sang định dạng ReactFlow
  4. Lưu kết quả vào DB (trường mindmap_data) và trả về
"""

from __future__ import annotations

import json
import html
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import validate_request_origin
from app.core.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.processing_run import ProcessingRun
from app.models.user import User
from app.schemas.document import ErrorResponse
from app.schemas.flashcard import ProcessingRunResponse
from app.schemas.mindmap_save import MindmapUpdateRequest
from app.services.ai_pipeline import AIServiceError, build_mermaid
from app.core.config import settings
from app.services.file_validator import FileTooLargeError, InvalidFileError, validate_and_read
from app.services.mindmap_generator import generate_mindmap_result
from app.services.ollama_service import check_ollama_health
from app.services.text_extractor import extract_text_from_bytes

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/mindmap",
    tags=["mindmap"],
    dependencies=[Depends(validate_request_origin)],
)


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", summary="Kiểm tra Ollama service")
async def mindmap_health() -> dict[str, Any]:
    """Kiểm tra Ollama đang chạy và model cấu hình sẵn sàng."""
    return await check_ollama_health()


# ── POST /guest – Sinh mindmap tạm thời, không lưu tài liệu ──────────────────

@router.post(
    "/guest",
    summary="Tạo mindmap không cần tài khoản",
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def generate_guest_mindmap(
    file: UploadFile = File(..., description="File PDF, DOCX hoặc PPTX"),
    mode: Literal["engine", "ai"] = Query("engine", description="Chế độ tạo mindmap"),
) -> dict[str, Any]:
    """Extract and generate a result in memory; guest input is not persisted."""
    try:
        file_type, content = await validate_and_read(file, settings.max_upload_bytes)
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE", "message": str(exc)},
        ) from exc
    except InvalidFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": str(exc)},
        ) from exc

    filename = Path((file.filename or "tai-lieu").replace("\\", "/")).name[:255]
    try:
        extracted_text, page_count = extract_text_from_bytes(file_type, content)
    except Exception as exc:  # noqa: BLE001
        logger.info("Guest upload could not be extracted: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNREADABLE_FILE", "message": "Không thể đọc nội dung file này."},
        ) from exc

    if len(extracted_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_EXTRACTABLE_TEXT",
                "message": "Tài liệu chưa có văn bản để tạo mindmap (PDF scan ảnh chưa được hỗ trợ OCR).",
            },
        )

    try:
        result = await generate_mindmap_result(
            mode=mode,
            extracted_text=extracted_text,
            original_filename=filename,
        )
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "AI_PROVIDER_ERROR", "message": str(exc)},
        ) from exc

    # No document row, processing run, or uploaded file is created for guests.
    return {
        "original_filename": filename,
        "page_count": page_count,
        "result": result,
    }


# ── POST /{id} – Sinh mindmap mới ────────────────────────────────────────────

@router.post(
    "/{document_id}",
    summary="Sinh Mindmap + Flashcards từ tài liệu",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProcessingRunResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def generate_mindmap(
    document_id: uuid.UUID,
    mode: Literal["engine", "ai"] = Query("engine", description="Chế độ: 'engine' (bóc tách cấu trúc) hoặc 'ai' (pipeline AI hai bước)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingRunResponse:
    """
    Tạo một tác vụ nền để sinh Mindmap + Flashcards từ tài liệu đã trích xuất.

    - Tài liệu phải có status = **extracted**.
    - Chế độ `engine`: Bóc tách cấu trúc tài liệu theo các cấp Heading (H1, H2, H3), định nghĩa và danh sách. Siêu nhanh và bám sát cấu trúc bài học.
    - Chế độ `ai`: AI bước 1 chuẩn hóa kiến thức; AI bước 2 tạo mindmap, Mermaid và flashcard.
    - Poll `GET /api/mindmap/runs/{run_id}` để theo dõi trạng thái và lấy kết quả.
    """
    doc = await _get_or_404(db, document_id, user.id)

    if doc.status != DocumentStatus.extracted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NOT_EXTRACTED",
                "message": (
                    f"Tài liệu chưa được trích xuất (status hiện tại: {doc.status.value}). "
                    "Upload và chờ trích xuất hoàn tất trước."
                ),
            },
        )

    if not doc.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_TEXT", "message": "Tài liệu không có nội dung văn bản."},
        )

    run = ProcessingRun(document_id=doc.id, user_id=user.id, mode=mode)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return _run_response(run)


@router.get("/runs/{run_id}", response_model=ProcessingRunResponse)
async def get_processing_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingRunResponse:
    result = await db.execute(
        select(ProcessingRun).where(
            ProcessingRun.id == run_id,
            ProcessingRun.user_id == user.id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ xử lý")
    return _run_response(run)


@router.get("/{document_id}/runs/latest", response_model=ProcessingRunResponse)
async def get_latest_processing_run(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessingRunResponse:
    result = await db.execute(
        select(ProcessingRun)
        .where(
            ProcessingRun.document_id == document_id,
            ProcessingRun.user_id == user.id,
        )
        .order_by(ProcessingRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Tài liệu chưa có tác vụ mindmap")
    return _run_response(run)


@router.get("/{document_id}/runs", response_model=list[ProcessingRunResponse])
async def list_processing_runs(
    document_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProcessingRunResponse]:
    await _get_or_404(db, document_id, user.id)
    result = await db.execute(
        select(ProcessingRun)
        .where(
            ProcessingRun.document_id == document_id,
            ProcessingRun.user_id == user.id,
        )
        .order_by(ProcessingRun.created_at.desc())
        .limit(limit)
    )
    return [_run_summary_response(run) for run in result.scalars().all()]


def _run_summary_response(run: ProcessingRun) -> ProcessingRunResponse:
    return ProcessingRunResponse(
        id=run.id,
        document_id=run.document_id,
        mode=run.mode,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        attempts=run.attempts,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _run_response(run: ProcessingRun) -> ProcessingRunResponse:
    result_data: dict[str, Any] | None = None
    if run.status == "completed" and run.result_data:
        try:
            result_data = json.loads(run.result_data)
        except json.JSONDecodeError:
            logger.exception("Kết quả processing run %s không phải JSON hợp lệ", run.id)
    return ProcessingRunResponse(
        id=run.id,
        document_id=run.document_id,
        mode=run.mode,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        attempts=run.attempts,
        error_message=run.error_message,
        result=result_data,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


# ── GET /{id} – Lấy kết quả đã lưu ──────────────────────────────────────────

@router.get(
    "/{document_id}",
    summary="Lấy kết quả Mindmap đã sinh",
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def get_mindmap(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Lấy kết quả Mindmap đã được sinh trước đó (từ cột mindmap_data trong DB)."""
    doc = await _get_or_404(db, document_id, user.id)

    mindmap_data: Optional[str] = getattr(doc, "mindmap_data", None)
    if not mindmap_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_MINDMAP",
                "message": "Chưa có mindmap cho tài liệu này. Hãy POST /api/mindmap/{id} trước.",
            },
        )

    data = json.loads(mindmap_data)
    data["document_id"] = str(document_id)
    return data


# ── PUT /{id} – Cập nhật mindmap đã chỉnh sửa ────────────────────────────────

@router.put(
    "/{document_id}",
    summary="Cập nhật sơ đồ Mindmap đã chỉnh sửa",
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def update_mindmap(
    document_id: uuid.UUID,
    payload: MindmapUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cập nhật các nút của mindmap, sinh lại Mermaid và Reactflow tương ứng."""
    doc = await _get_or_404(db, document_id, user.id)

    raw_data = getattr(doc, "mindmap_data", None)
    current_data = json.loads(raw_data) if raw_data else {}

    title = Path(doc.original_filename).stem

    if payload.nodes is not None:
        nodes = [node.model_dump() for node in payload.nodes]
        current_data.setdefault("mindmap", {})["nodes"] = nodes
        if payload.mermaid is None:
            current_data["mermaid"] = build_mermaid(title, nodes)
        current_data["reactflow"] = _mindmap_to_reactflow({"nodes": nodes})

    if payload.mermaid is not None:
        current_data["mermaid"] = payload.mermaid

    current_data["document_id"] = str(document_id)

    doc.mindmap_data = json.dumps(current_data, ensure_ascii=False)
    await db.commit()

    return current_data


# ── GET /{id}/reactflow ───────────────────────────────────────────────────────

@router.get(
    "/{document_id}/reactflow",
    summary="Lấy dữ liệu ReactFlow của Mindmap",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def get_reactflow(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trả về nodes + edges ở định dạng ReactFlow để frontend render ngay."""
    doc = await _get_or_404(db, document_id, user.id)
    mindmap_data: Optional[str] = getattr(doc, "mindmap_data", None)

    if not mindmap_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_MINDMAP", "message": "Chưa có mindmap. POST trước."},
        )

    data = json.loads(mindmap_data)
    reactflow = data.get("reactflow") or _mindmap_to_reactflow(data.get("mindmap", {}))
    return {"document_id": str(document_id), "reactflow": reactflow}


# ── GET /{id}/export/svg ──────────────────────────────────────────────────────

@router.get(
    "/{document_id}/export/svg",
    summary="Xuất Mindmap thành file vector SVG",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def export_mindmap_svg(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Tải sơ đồ Mindmap dưới dạng file vector SVG chất lượng cao (không vỡ nét)."""
    doc = await _get_or_404(db, document_id, user.id)
    mindmap_data: Optional[str] = getattr(doc, "mindmap_data", None)

    if not mindmap_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_MINDMAP", "message": "Chưa có mindmap để xuất. Hãy sinh mindmap trước."},
        )

    data = json.loads(mindmap_data)
    mindmap = data.get("mindmap", {})
    svg_content = _generate_svg_from_mindmap(mindmap)

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(doc.original_filename).stem).strip("._")[:80]
    filename = f"{stem or 'mindmap'}_mindmap.svg"

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{document_id}/export/mermaid",
    summary="Tải mã nguồn Mermaid",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def export_mindmap_mermaid(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Tải sơ đồ dưới dạng tệp .mmd có thể mở bằng Mermaid-compatible tools."""
    doc = await _get_or_404(db, document_id, user.id)
    if not doc.mindmap_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_MINDMAP", "message": "Chưa có mindmap để xuất."},
        )
    data = json.loads(doc.mindmap_data)
    source = data.get("mermaid") or build_mermaid(
        Path(doc.original_filename).stem,
        data.get("mindmap", {}).get("nodes", []),
    )
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(doc.original_filename).stem).strip("._")[:80]
    filename = f"{stem or 'mindmap'}_mindmap.mmd"
    return Response(
        content=source,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Không tìm thấy tài liệu."},
        )
    return doc


def _mindmap_to_reactflow(mindmap: dict[str, Any], dx: int = 280, dy: int = 70) -> dict[str, Any]:
    """Chuyển đổi mindmap sang định dạng ReactFlow nodes + edges với vị trí tự động sắp xếp theo cây."""
    nodes = mindmap.get("nodes", [])
    if not nodes:
        return {"nodes": [], "edges": []}

    kids: dict[Optional[str], list[dict]] = {}
    for n in nodes:
        pid = n.get("parent_id")
        if pid in (None, "null", ""):
            pid = None
        else:
            pid = str(pid)
        kids.setdefault(pid, []).append(n)

    pos: dict[str, dict[str, int]] = {}
    row = [0]

    def walk(n: dict, depth: int) -> float:
        nid = str(n["id"])
        ch = kids.get(nid, [])
        if not ch:
            y = row[0] * dy
            row[0] += 1
        else:
            ys = [walk(c, depth + 1) for c in ch]
            y = sum(ys) / len(ys)
        pos[nid] = {"x": depth * dx, "y": int(y)}
        return y

    for r in kids.get(None, []):
        walk(r, 0)

    # Đảm bảo các node rời rạc cũng có vị trí
    for n in nodes:
        nid = str(n["id"])
        if nid not in pos:
            pos[nid] = {"x": 0, "y": row[0] * dy}
            row[0] += 1

    return {
        "nodes": [
            {
                "id": str(n["id"]),
                "data": {"label": n.get("label", "")},
                "position": pos.get(str(n["id"]), {"x": 0, "y": 0}),
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": f"e-{n['parent_id']}-{n['id']}",
                "source": str(n["parent_id"]),
                "target": str(n["id"]),
            }
            for n in nodes
            if n.get("parent_id") not in (None, "null", "")
        ],
    }


def _generate_svg_from_mindmap(mindmap: dict[str, Any]) -> str:
    """Sinh chuỗi XML SVG hoàn chỉnh từ dữ liệu mindmap."""
    rf = _mindmap_to_reactflow(mindmap, dx=260, dy=65)
    nodes = rf.get("nodes", [])
    edges = rf.get("edges", [])

    if not nodes:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><text x="20" y="100" fill="#fff">Không có dữ liệu</text></svg>'

    colors = ["#5a6cf0", "#a855f7", "#06b6d4", "#10b981", "#f59e0b", "#ec4899"]
    node_map = {str(n["id"]): n for n in nodes}

    max_x = max((n["position"]["x"] + len(n["data"]["label"]) * 9 + 50 for n in nodes), default=600)
    max_y = max((n["position"]["y"] + 60 for n in nodes), default=400)
    width = max(max_x + 80, 700)
    height = max(max_y + 80, 400)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background-color:#0f0f1a; font-family:sans-serif;">',
        '<defs>',
        '  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">',
        '    <circle cx="2" cy="2" r="1" fill="rgba(255,255,255,0.06)" />',
        '  </pattern>',
        '  <linearGradient id="root" x1="0%" y1="0%" x2="100%" y2="100%">',
        '    <stop offset="0%" stop-color="#4f46e5" />',
        '    <stop offset="100%" stop-color="#7c3aed" />',
        '  </linearGradient>',
        '</defs>',
        f'<rect width="{width}" height="{height}" fill="#0f0f1a" />',
        f'<rect width="{width}" height="{height}" fill="url(#grid)" />',
        '<g class="edges">',
    ]

    # Vẽ edges
    for idx, e in enumerate(edges):
        src = node_map.get(str(e["source"]))
        tgt = node_map.get(str(e["target"]))
        if not src or not tgt:
            continue
        src_w = max(130, min(240, len(src["data"]["label"]) * 9 + 30))
        x1 = src["position"]["x"] + src_w + 30
        y1 = src["position"]["y"] + 45
        x2 = tgt["position"]["x"] + 30
        y2 = tgt["position"]["y"] + 45
        cx = (x1 + x2) / 2
        color = colors[idx % len(colors)]
        svg_parts.append(
            f'  <path d="M {x1} {y1} C {cx} {y1}, {cx} {y2}, {x2} {y2}" fill="none" stroke="{color}" stroke-width="2.2" stroke-opacity="0.8" />'
        )

    svg_parts.append('</g><g class="nodes">')

    # Vẽ nodes
    for idx, n in enumerate(nodes):
        label = html.escape(str(n["data"]["label"]), quote=False)
        x = n["position"]["x"] + 30
        y = n["position"]["y"] + 25
        w = max(130, min(240, len(label) * 9 + 30))
        h = 40
        is_root = n["position"]["x"] == 0
        fill = 'url(#root)' if is_root else '#1e1e35'
        stroke = 'rgba(255,255,255,0.4)' if is_root else colors[idx % len(colors)]
        text_color = '#ffffff' if is_root else '#e2e8f0'

        svg_parts.append(f'  <g transform="translate({x},{y})">')
        svg_parts.append(f'    <rect width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5" />')
        if not is_root:
            svg_parts.append(f'    <rect x="0" y="4" width="4" height="{h-8}" rx="2" fill="{stroke}" />')
        text_x = w / 2 if is_root else 14
        anchor = 'middle' if is_root else 'start'
        svg_parts.append(f'    <text x="{text_x}" y="{h/2 + 4}" fill="{text_color}" font-size="12" font-weight="500" text-anchor="{anchor}">{label}</text>')
        svg_parts.append('  </g>')

    svg_parts.append('</g></svg>')
    return "\n".join(svg_parts)
