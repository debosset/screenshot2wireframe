import os
import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import shutil

from .opencv_analyzer import analyze_screenshot
from .bmpr_builder import build_bmpr

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Screenshot to Wireframe")
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

        output_path = OUTPUT_DIR / f"{job_id}.bmpr"
        build_bmpr(components, str(output_path), project_name=Path(file.filename).stem)

        return {
            "job_id": job_id,
            "components_count": len(components),
            "download_url": f"/download/{job_id}",
            "components": components[:5],
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()


@app.get("/download/{job_id}")
async def download(job_id: str):
    safe_id = job_id.replace("..", "").replace("/", "")
    output_path = OUTPUT_DIR / f"{safe_id}.bmpr"
    if not output_path.exists():
        raise HTTPException(404, "Fichier introuvable ou expiré.")
    return FileResponse(
        path=str(output_path),
        media_type="application/octet-stream",
        filename=f"wireframe_{safe_id[:8]}.bmpr",
    )


@app.delete("/cleanup/{job_id}")
async def cleanup(job_id: str):
    safe_id = job_id.replace("..", "").replace("/", "")
    f = OUTPUT_DIR / f"{safe_id}.bmpr"
    if f.exists():
        f.unlink()
    return {"deleted": True}
