import shutil, uuid, json, sqlite3, time, os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SnapWire")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
CACHE: dict = {}


def _build_bmpr(mockup_json: dict, output_path: str) -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)
    mockup = mockup_json.get("mockup", {})
    project_name = mockup.get("attributes", {}).get("name", "Wireframe")
    now = int(time.time() * 1000)
    branch_attrs = json.dumps({
        "projectDescription": "", "symbolLibraryID": "",
        "fontFace": "Balsamiq Sans", "fontSize": 13,
        "linkColor": 545684, "selectionColor": 9813234, "skinName": "programmatic",
    })
    conn = sqlite3.connect(output_path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE BRANCHES (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT);
        CREATE TABLE USERS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT);
        CREATE TABLE RESOURCES (ID VARCHAR(255), BRANCHID VARCHAR(255), ATTRIBUTES TEXT, DATA LONGTEXT,
            PRIMARY KEY (ID, BRANCHID), FOREIGN KEY (BRANCHID) REFERENCES BRANCHES(ID));
        CREATE TABLE THUMBNAILS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES MEDIUMTEXT);
        CREATE TABLE COMMENTS (ID VARCHAR(255) PRIMARY KEY, BRANCHID VARCHAR(255),
            RESOURCEID VARCHAR(255), DATA LONGTEXT, USERID VARCHAR(255), ATTRIBUTES TEXT,
            FOREIGN KEY (USERID) REFERENCES USERS(ID),
            FOREIGN KEY (RESOURCEID, BRANCHID) REFERENCES RESOURCES(ID, BRANCHID));
        CREATE TABLE INFO (NAME VARCHAR(255) PRIMARY KEY, VALUE TEXT);
    """)
    c.executemany("INSERT INTO INFO (NAME, VALUE) VALUES (?,?)", [
        ("SchemaVersion", "2.0"), ("ArchiveFormat", "bmpr"),
        ("ArchiveRevisionUUID", ""), ("ArchiveAttributes", json.dumps({"name": project_name})),
        ("ArchiveRevision", "1"),
    ])
    c.execute("INSERT INTO BRANCHES VALUES (?,?)", ("Master", branch_attrs))
    resource_id = str(uuid.uuid4()).upper()
    c.execute("INSERT INTO RESOURCES (ID, BRANCHID, ATTRIBUTES, DATA) VALUES (?,?,?,?)", (
        resource_id, "Master",
        json.dumps({"kind": "mockup", "name": project_name, "order": 938428.5264654435}),
        json.dumps(mockup_json)
    ))
    conn.commit()
    conn.close()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    groq_api_key: Optional[str] = Form(""),
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
        api_key = (groq_api_key or "").strip()

        if api_key.startswith("gsk_"):
            # ── Mode Groq Vision ─────────────────────────────────────────────
            from .groq_vision import analyze_with_groq, extract_components
            mockup_json = analyze_with_groq(str(upload_path), api_key, project_id=project_id or "0:1")
            components = extract_components(mockup_json)
            source = "groq"
        else:
            # ── Mode OCR fallback ────────────────────────────────────────────
            from .smart_analyzer import smart_analyze
            components = smart_analyze(str(upload_path))
            mockup_json = None
            source = "ocr"

        CACHE[job_id] = {"components": components, "mockup_json": mockup_json, "project_id": project_id or "0:1"}

        return {
            "job_id": job_id,
            "source": source,
            "components_count": len(components),
            "components": components,
        }
    finally:
        if upload_path.exists():
            upload_path.unlink()


@app.post("/generate")
async def generate(
    job_id: str = Form(...),
    project_id: Optional[str] = Form("0:1"),
):
    cached = CACHE.get(job_id)
    if not cached:
        raise HTTPException(404, "Session expirée, re-uploadez l'image.")

    components = cached["components"]
    mockup_json = cached.get("mockup_json")
    pid = project_id or cached.get("project_id", "0:1")

    if not mockup_json:
        # Construire depuis les composants OCR
        from .balsamiq_json import to_clipboard_json
        clipboard_str = to_clipboard_json(components, project_id=pid)
        mockup_json = json.loads(clipboard_str)
    else:
        mockup_json["projectID"] = pid

    clipboard_json = json.dumps(mockup_json, indent=2)
    CACHE[f"{job_id}_json"] = clipboard_json

    bmpr_path = OUTPUT_DIR / f"{job_id}.bmpr"
    _build_bmpr(mockup_json, str(bmpr_path))

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
