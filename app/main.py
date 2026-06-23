import uuid, shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from .opencv_analyzer import analyze_screenshot
from .balsamiq_json import to_clipboard_json, classify
from .bmml_builder import build_bmml

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
    if file.content_type not in {"image/png","image/jpeg","image/webp","image/gif"}:
        raise HTTPException(400, "Format non supporté.")
    job_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix or ".png"
    up = UPLOAD_DIR / f"{job_id}{ext}"
    with open(up, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        components = analyze_screenshot(str(up))
        if not components:
            raise HTTPException(422, "Aucun composant détecté.")

        # Enrichir les composants avec le typeID Balsamiq
        img_w = max((c["x"] + c["w"]) for c in components)
        img_h = max((c["y"] + c["h"]) for c in components)
        for i, c in enumerate(components):
            c["typeID"] = classify(c["type"], c["x"], c["y"], c["w"], c["h"], img_w, img_h)

        # Générer le .bmml téléchargeable
        out = OUTPUT_DIR / f"{job_id}.bmml"
        build_bmml(components, str(out), Path(file.filename).stem)

        # Générer aussi le JSON clipboard
        clipboard = to_clipboard_json(components, project_id=project_id or "0:1")

        return {
            "job_id": job_id,
            "components_count": len(components),
            "download_url": f"/download/{job_id}",
            "clipboard_json": clipboard,
            "types": list(set(c["typeID"] for c in components)),
        }
    finally:
        if up.exists(): up.unlink()

@app.get("/download/{job_id}")
async def download(job_id: str):
    sid = job_id.replace("..","").replace("/","")
    f = OUTPUT_DIR / f"{sid}.bmml"
    if not f.exists():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(str(f), media_type="application/octet-stream", filename=f"wireframe_{sid[:8]}.bmml")
