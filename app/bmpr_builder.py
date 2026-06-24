"""
Génère un .bmpr valide — schéma exact reverse-engineered depuis vrais fichiers Balsamiq.
ATTRIBUTES et DATA sont du JSON texte brut (pas de compression zlib).
"""
import json, sqlite3, uuid, os
from typing import List, Dict, Any


def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)

    max_w = max((int(c["x"]) + int(c["w"])) for c in components) if components else 1000
    max_h = max((int(c["y"]) + int(c["h"])) for c in components) if components else 800

    # Construire les contrôles
    controls = []
    for i, c in enumerate(components):
        ctrl = {
            "ID": str(i),
            "typeID": c.get("typeID", c.get("type", "Rectangle")),
            "zOrder": str(i),
            "w": str(c["w"]),
            "h": str(c["h"]),
            "measuredW": str(c.get("measuredW", c["w"])),
            "measuredH": str(c.get("measuredH", c["h"])),
            "x": str(c["x"]),
            "y": str(c["y"]),
        }
        controls.append(ctrl)

    # DATA = JSON texte brut (pas de zlib !)
    mockup_data = json.dumps({
        "mockup": {
            "controls": {"control": controls},
            "measuredW": str(max_w),
            "measuredH": str(max_h),
            "mockupW": str(max_w),
            "mockupH": str(max_h),
            "version": "1.0",
        }
    }, separators=(",", ":"))

    # ATTRIBUTES = JSON texte brut
    mockup_attrs = json.dumps({
        "kind": "mockup",
        "name": project_name,
        "order": 1000.0,
    })

    resource_id = str(uuid.uuid4()).upper()

    # BRANCHES ATTRIBUTES = JSON texte brut (skinName "programmatic" comme dans les vrais fichiers)
    branch_attrs = json.dumps({
        "projectDescription": "",
        "symbolLibraryID": "",
        "fontFace": "Balsamiq Sans",
        "fontSize": 13,
        "linkColor": 545684,
        "selectionColor": 9813234,
        "skinName": "programmatic",
    })

    conn = sqlite3.connect(output_path)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE INFO (KEY TEXT PRIMARY KEY, VALUE TEXT);
        CREATE TABLE BRANCHES (ID TEXT PRIMARY KEY, ATTRIBUTES TEXT);
        CREATE TABLE RESOURCES (ID TEXT PRIMARY KEY, BRANCHID TEXT NOT NULL, ATTRIBUTES TEXT, DATA TEXT);
        CREATE TABLE THUMBNAILS (RESOURCEID TEXT, BRANCHID TEXT, DATA BLOB);
    """)

    c.executemany("INSERT INTO INFO VALUES (?,?)", [
        ("SchemaVersion", "2.0"),
        ("ArchiveFormat", "bmpr"),
        ("ArchiveRevisionUUID", ""),
        ("ArchiveAttributes", json.dumps({"name": project_name})),
        ("ArchiveRevision", "1"),
    ])

    c.execute("INSERT INTO BRANCHES VALUES (?,?)", ("Master", branch_attrs))

    c.execute(
        "INSERT INTO RESOURCES (ID, BRANCHID, ATTRIBUTES, DATA) VALUES (?,?,?,?)",
        (resource_id, "Master", mockup_attrs, mockup_data)
    )

    conn.commit()
    conn.close()
