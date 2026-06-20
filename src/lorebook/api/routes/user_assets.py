"""Routes for managing user-uploaded custom assets (e.g. background images)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/user-assets", tags=["user-assets"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def get_user_assets_root() -> Path:
    root = Path(__file__).resolve().parents[5] / "user" / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_backgrounds_dir() -> Path:
    d = get_user_assets_root() / "backgrounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/upload/background")
async def upload_background_image(file: UploadFile) -> dict:
    """Upload a custom background image and return its URL path."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    suffix = Path(file.filename or "image.png").suffix or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = get_backgrounds_dir() / filename
    dest.write_bytes(data)

    return {"url": f"/user-assets/backgrounds/{filename}", "filename": filename}


@router.get("/list/backgrounds")
async def list_background_images() -> dict:
    """List all uploaded background images."""
    backgrounds_dir = get_backgrounds_dir()
    files = []
    for f in sorted(backgrounds_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            files.append({"filename": f.name, "url": f"/user-assets/backgrounds/{f.name}"})
    return {"files": files}


@router.delete("/backgrounds/{filename}")
async def delete_background_image(filename: str) -> dict:
    """Delete a background image by filename."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = get_backgrounds_dir() / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")

    target.unlink()
    return {"status": "deleted", "filename": filename}
