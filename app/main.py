import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from .balsamiq_json import classify
from .bmml_builder import build_bmml
from .opencv_analyzer import analyze_screenshot

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
async def convert(file: UploadFile = File(...)):
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
            c["typeID"] = classify(c["type"], c["x"], c["y"], c["w"], c["h"], img_w, img_h)

        title = Path(file.filename or "wireframe").stem
        output_path = OUTPUT_DIR / f"{job_id}.bmml"
        build_bmml(components, str(output_path), title)

        return {
            "job_id": job_id,
            "components_count": len(components),
            "download_url": f"/download/{job_id}",
            "types": sorted(set(c["typeID"] for c in components)),
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()


@app.get("/download/{job_id}")
async def download(job_id: str):
    safe_id = job_id.replace("..", "").replace("/", "")
    file_path = OUTPUT_DIR / f"{safe_id}.bmml"
    if not file_path.exists():
        raise HTTPException(404, "Fichier introuvable.")

    return FileResponse(
        str(file_path),
        media_type="application/xml; charset=utf-8",
        filename=f"wireframe_{safe_id[:8]}.bmml",
    )
