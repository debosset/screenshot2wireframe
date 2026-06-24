import shutil, uuid, json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates

from .balsamiq_json import classify, to_clipboard_json
from .opencv_analyzer import analyze_screenshot
from .bmpr_builder import build_bmpr

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SnapWire")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
CLIPBOARD_CACHE: dict = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form("0:1"),
    component_mode: Optional[str] = Form("all"),
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
            c["typeID"] = classify(
                c.get("type", "Rectangle"), c["x"], c["y"], c["w"], c["h"],
                img_w, img_h, mode=component_mode or "all"
            )

        clipboard_json = to_clipboard_json(components, project_id=project_id or "0:1", mode=component_mode or "all")
        CLIPBOARD_CACHE[job_id] = clipboard_json

        # Générer le .bmpr
        bmpr_path = OUTPUT_DIR / f"{job_id}.bmpr"
        build_bmpr(components, str(bmpr_path), project_name=Path(file.filename or "wireframe").stem)

        return {
            "job_id": job_id,
            "components_count": len(components),
            "clipboard_json": clipboard_json,
            "download_url": f"/download-json/{job_id}",
            "bmpr_url": f"/download-bmpr/{job_id}",
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
        content, media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="balsamiq_{safe_id[:8]}.json"'},
    )


@app.get("/download-bmpr/{job_id}")
async def download_bmpr(job_id: str):
    safe_id = job_id.replace("..", "").replace("/", "")
    f = OUTPUT_DIR / f"{safe_id}.bmpr"
    if not f.exists():
        raise HTTPException(404, "Fichier .bmpr introuvable.")
    return FileResponse(str(f), media_type="application/octet-stream", filename=f"wireframe_{safe_id[:8]}.bmpr")
