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
CACHE: dict = {}

TYPE_LABELS = {
    "NavBar": "🧭 Barre de navigation",
    "TabBar": "📑 Barre d'onglets",
    "Title": "🔤 Titre",
    "SubTitle": "🔤 Sous-titre",
    "Label": "🏷️ Label",
    "Paragraph": "📝 Paragraphe",
    "TextInput": "✏️ Champ texte",
    "TextArea": "📄 Zone de texte",
    "SearchBox": "🔍 Champ recherche",
    "Button": "🔘 Bouton",
    "ButtonBar": "🔘 Barre de boutons",
    "PointyButton": "▶️ Bouton directionnel",
    "CheckBox": "☑️ Case à cocher",
    "RadioButton": "🔘 Bouton radio",
    "ComboBox": "📋 Liste déroulante",
    "DatePicker": "📅 Sélecteur date",
    "Image": "🖼️ Image",
    "Icon": "🎯 Icône",
    "Rectangle": "▭ Rectangle",
    "Canvas": "🎨 Zone colorée",
    "FieldSet": "📦 Groupe de champs",
    "DataGrid": "📊 Tableau de données",
    "HRule": "— Séparateur",
    "ProgressBar": "⏳ Barre de progression",
    "BreadCrumb": "🗺️ Fil d'Ariane",
    "Pagination": "📄 Pagination",
}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    component_mode: Optional[str] = Form("all"),
):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise HTTPException(400, "Format non supporté.")

    job_id = str(uuid.uuid4())
    ext = Path(file.filename or "screenshot.png").suffix or ".png"
    upload_path = UPLOAD_DIR / f"{job_id}{ext}"

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # On garde l'image pour l'OCR — suppression après
    try:
        components = analyze_screenshot(str(upload_path))
        if not components:
            raise HTTPException(422, "Aucun composant détecté.")

        img_w = max((c["x"] + c["w"]) for c in components)
        img_h = max((c["y"] + c["h"]) for c in components)

        for c in components:
            c["typeID"] = classify(c.get("type", "Rectangle"), c["x"], c["y"], c["w"], c["h"], img_w, img_h, mode=component_mode or "all")

        # OCR — lire les textes
        try:
            from .ocr_reader import enrich_with_text
            components = enrich_with_text(components, str(upload_path))
        except Exception as e:
            pass  # OCR optionnel

        # Trier par position
        components.sort(key=lambda c: (c["y"], c["x"]))

        # Préparer la réponse
        result = []
        for c in components:
            text = c.get("_text", "")
            label_above = c.get("_label_above", "")
            tid = c["typeID"]

            # Description lisible
            if label_above:
                description = f"{label_above}"
            elif text:
                description = text
            else:
                description = ""

            result.append({
                "typeID": tid,
                "label": TYPE_LABELS.get(tid, f"▭ {tid}"),
                "description": description,
                "x": c["x"], "y": c["y"],
                "w": c["w"], "h": c["h"],
                "measuredW": c.get("measuredW", c["w"]),
                "measuredH": c.get("measuredH", c["h"]),
            })

        CACHE[job_id] = result

        return {
            "job_id": job_id,
            "components_count": len(result),
            "components": result,
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()


@app.post("/generate")
async def generate(
    job_id: str = Form(...),
    project_id: Optional[str] = Form("0:1"),
):
    components = CACHE.get(job_id)
    if not components:
        raise HTTPException(404, "Session expirée, re-uploadez l'image.")

    clipboard_json = to_clipboard_json(components, project_id=project_id or "0:1")
    CACHE[f"{job_id}_json"] = clipboard_json

    bmpr_path = OUTPUT_DIR / f"{job_id}.bmpr"
    build_bmpr(components, str(bmpr_path), project_name="Wireframe")

    return {
        "download_url": f"/download-json/{job_id}",
        "bmpr_url": f"/download-bmpr/{job_id}",
        "clipboard_json": clipboard_json,
    }


@app.get("/download-json/{job_id}")
async def download_json(job_id: str):
    sid = job_id.replace("..", "").replace("/", "")
    content = CACHE.get(f"{sid}_json")
    if not content:
        raise HTTPException(404, "JSON introuvable.")
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="balsamiq_{sid[:8]}.json"'})


@app.get("/download-bmpr/{job_id}")
async def download_bmpr(job_id: str):
    sid = job_id.replace("..", "").replace("/", "")
    f = OUTPUT_DIR / f"{sid}.bmpr"
    if not f.exists():
        raise HTTPException(404, "Fichier .bmpr introuvable.")
    return FileResponse(str(f), media_type="application/octet-stream", filename=f"wireframe_{sid[:8]}.bmpr")
