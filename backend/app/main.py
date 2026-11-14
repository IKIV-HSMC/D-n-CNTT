import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth as auth_router
from app.api import documents as documents_router
from app.api import flashcards as flashcards_router
from app.api import mindmap as mindmap_router
from app.api import subjects as subjects_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle hooks – để sẵn điểm mở rộng (init AI models, cache, etc.)."""
    yield


app = FastAPI(
    title="AI Document-to-Mindmap API",
    description="Backend API cho tài khoản, tài liệu, mindmap, flashcard và lịch ôn SM-2.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(documents_router.router)
app.include_router(mindmap_router.router)
app.include_router(flashcards_router.router)
app.include_router(auth_router.router)
app.include_router(subjects_router.router)


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "Lỗi server nội bộ"},
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Kiểm tra backend đang chạy."""
    return {"status": "ok", "version": "1.0.0"}
