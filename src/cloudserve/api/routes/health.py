"""Operational liveness endpoint for the scaffold."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cloudserve-api"}
