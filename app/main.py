import uuid, shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .opencv_analyzer import analyze_screenshot
from .balsamiq_json import to_clipboard_json

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
        clipboard = to_clipboard_json(components)
        return {
            "components_count": len(components),
            "clipboard_json": clipboard,
            "types": list(set(c["type"].split("::")[-1] for c in components)),
        }
    finally:
        if up.exists(): up.unlink()
