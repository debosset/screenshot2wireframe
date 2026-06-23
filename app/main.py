import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from .opencv_analyzer import analyze_screenshot
from .balsamiq_json import classify
from .bmml_builder import build_bmml, build_bmml_string

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SnapWire")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
    up = UPLOAD_DIR / f"{job_id}{ext}"

    with open(up, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        components = analyze_screenshot(str(up))
        if not components:
            raise HTTPException(422, "Aucun composant détecté.")

        img_w = max((c["x"] + c["w"]) for c in components)
        img_h = max((c["y"] + c["h"]) for c in components)

        for c in components:
            c["typeID"] = classify(c["type"], c["x"], c["y"], c["w"], c["h"], img_w, img_h)

        title = Path(file.filename or "wireframe").stem
        bmml_xml = build_bmml_string(components, title)

        out = OUTPUT_DIR / f"{job_id}.bmml"
        build_bmml(components, str(out), title)

        return {
            "job_id": job_id,
            "components_count": len(components),
            "download_url": f"/download/{job_id}",
            "clipboard_bmml": bmml_xml,
            "types": sorted(set(c["typeID"] for c in components)),
        }
    finally:
        if up.exists():
            up.unlink()


@app.get("/download/{job_id}")
async def download(job_id: str):
    sid = job_id.replace("..", "").replace("/", "")
    f = OUTPUT_DIR / f"{sid}.bmml"
    if not f.exists():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(
        str(f),
        media_type="application/xml; charset=utf-8",
        filename=f"wireframe_{sid[:8]}.bmml",
    )


@app.get("/download/{job_id}/text", response_class=PlainTextResponse)
async def download_text(job_id: str):
    sid = job_id.replace("..", "").replace("/", "")
    f = OUTPUT_DIR / f"{sid}.bmml"
    if not f.exists():
        raise HTTPException(404, "Fichier introuvable.")
    return PlainTextResponse(f.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")
