import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from .balsamiq_json import classify, to_clipboard_json
from .opencv_analyzer import analyze_screenshot

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SnapWire")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Petit cache mémoire pour permettre le téléchargement du JSON après conversion.
CLIPBOARD_CACHE = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form("0:1"),
):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise HTTPException(400, "Format non supporté.")

    job_id = str(uuid.uuid4())
    ext = Path(file.filename or "screenshot.png").suffix or ".png"
    upload_path = UPLOAD_DIR / f"{job_id}{ext}"

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        components = analyze_screenshot(str(upload_path))
        if not components:
            raise HTTPException(422, "Aucun composant détecté.")

        img_w = max((c["x"] + c["w"]) for c in components)
        img_h = max((c["y"] + c["h"]) for c in components)

        for c in components:
            c["typeID"] = classify(c.get("type", "Rectangle"), c["x"], c["y"], c["w"], c["h"], img_w, img_h)

        clipboard_json = to_clipboard_json(components, project_id=project_id or "0:1")
        CLIPBOARD_CACHE[job_id] = clipboard_json

        return {
            "job_id": job_id,
            "components_count": len(components),
            "clipboard_json": clipboard_json,
            "download_url": f"/download-json/{job_id}",
            "types": sorted(set(c["typeID"] for c in components)),
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()


@app.get("/download-json/{job_id}")
async def download_json(job_id: str):
    safe_id = job_id.replace("..", "").replace("/", "")
    content = CLIPBOARD_CACHE.get(safe_id)
    if not content:
        raise HTTPException(404, "JSON introuvable.")
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="balsamiq_clipboard_{safe_id[:8]}.json"'},
    )
