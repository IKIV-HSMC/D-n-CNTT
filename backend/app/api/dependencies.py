from fastapi import HTTPException, Request, status

from app.core.config import settings


async def validate_request_origin(request: Request) -> None:
    """Reject browser write requests from origins outside the configured allowlist."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if origin and origin not in settings.CORS_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin không được phép",
        )
