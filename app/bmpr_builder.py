"""
Génère un .bmpr valide — schéma reverse-engineered depuis vrais fichiers Balsamiq.
Schéma réel : tables MAJUSCULES, colonnes ID/BRANCHID/ATTRIBUTES/DATA
"""
import json, sqlite3, zlib, uuid, time, os
from typing import List, Dict, Any

TYPE_MAP = {
    "com.balsamiq.mockups::Button":        "Button",
    "com.balsamiq.mockups::TextInput":     "TextInput",
    "com.balsamiq.mockups::Label":         "Label",
    "com.balsamiq.mockups::CheckBox":      "CheckBox",
    "com.balsamiq.mockups::Image":         "Image",
    "com.balsamiq.mockups::NavigationBar": "NavBar",
    "com.balsamiq.mockups::Rectangle":     "Rectangle",
    "NavBar": "NavBar", "TabBar": "TabBar",
    "Button": "Button", "TextInput": "TextInput",
    "Label": "Label", "Title": "Title",
    "CheckBox": "CheckBox", "ComboBox": "ComboBox",
    "Image": "Image", "Rectangle": "Rectangle",
    "FieldSet": "FieldSet", "DataGrid": "DataGrid",
    "HRule": "HRule", "SearchBox": "SearchBox",
    "Paragraph": "Paragraph", "TextArea": "TextArea",
}

def _enc(data: dict) -> bytes:
    return zlib.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"), level=6)

def _ctrl(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    tid = TYPE_MAP.get(comp.get("typeID", comp.get("type", "Rectangle")), "Rectangle")
    return {
        "ID": str(index),
        "typeID": tid,
        "zOrder": str(index),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
        "measuredW": str(comp.get("measuredW", comp["w"])),
        "measuredH": str(comp.get("measuredH", comp["h"])),
        "x": str(comp["x"]),
        "y": str(comp["y"]),
    }

def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)

    controls = [_ctrl(c, i) for i, c in enumerate(components)]
    max_w = max((c["x"] + c["w"]) for c in components) if components else 1000
    max_h = max((c["y"] + c["h"]) for c in components) if components else 800

    mockup_data = {
        "mockup": {
            "controls": {"control": controls},
            "measuredW": str(max_w),
            "measuredH": str(max_h),
            "mockupW": str(max_w),
            "mockupH": str(max_h),
            "version": "1.0",
        }
    }

    mockup_id = str(uuid.uuid4()).upper()
    branch_attrs = json.dumps({
        "projectDescription": "",
        "symbolLibraryID": "",
        "fontFace": "Balsamiq Sans",
        "fontSize": 13,
        "linkColor": 545684,
        "selectionColor": 9813234,
        "skinName": "sketch"
    })

    mockup_attrs = _enc({
        "kind": "mockup",
        "name": project_name,
        "order": 1000.0
    })

    conn = sqlite3.connect(output_path)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE INFO (
            KEY TEXT PRIMARY KEY,
            VALUE TEXT
        );
        CREATE TABLE BRANCHES (
            ID TEXT PRIMARY KEY,
            ATTRIBUTES TEXT
        );
        CREATE TABLE RESOURCES (
            ID TEXT PRIMARY KEY,
            BRANCHID TEXT NOT NULL,
            ATTRIBUTES BLOB,
            DATA BLOB
        );
        CREATE TABLE THUMBNAILS (
            RESOURCEID TEXT,
            BRANCHID TEXT,
            DATA BLOB
        );
    """)

    # INFO
    c.executemany("INSERT INTO INFO VALUES (?,?)", [
        ("SchemaVersion", "2.0"),
        ("ArchiveFormat", "bmpr"),
        ("ArchiveRevisionUUID", ""),
        ("ArchiveAttributes", json.dumps({"name": project_name})),
        ("ArchiveRevision", "1"),
    ])

    # BRANCHES
    c.execute("INSERT INTO BRANCHES VALUES (?,?)", ("Master", branch_attrs))

    # RESOURCES — mockup
    c.execute(
        "INSERT INTO RESOURCES (ID, BRANCHID, ATTRIBUTES, DATA) VALUES (?,?,?,?)",
        (mockup_id, "Master", mockup_attrs, _enc(mockup_data))
    )

    conn.commit()
    conn.close()
