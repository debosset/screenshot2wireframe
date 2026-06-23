import os
import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import shutil

from .opencv_analyzer import analyze_screenshot
from .balsamiq_json import to_clipboard_bmlf, to_clipboard_json

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SnapWire")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Format non supporté. PNG, JPG, WEBP acceptés.")

    job_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix or ".png"
    upload_path = UPLOAD_DIR / f"{job_id}{ext}"

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        components = analyze_screenshot(str(upload_path))
        if not components:
            raise HTTPException(422, "Aucun composant détecté dans l'image.")

        return {
            "components_count": len(components),
            "clipboard_bmlf": to_clipboard_bmlf(components),
            "clipboard_json": to_clipboard_json(components),
            "types": list(set(c["type"].split("::")[-1] for c in components)),
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()
