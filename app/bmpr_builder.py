"""
Génère un .bmpr valide — schéma et format confirmés fonctionnels.
Règle clé : w/h optionnels selon le type — certains composants utilisent uniquement measuredW/H.
"""
import json, sqlite3, uuid, os
from typing import List, Dict, Any

# Composants qui N'ont PAS besoin de w/h explicites (Balsamiq utilise measuredW/H)
NO_WH_TYPES = {
    "Title", "SubTitle", "Label", "Paragraph", "Link", "Text",
    "Button", "CheckBox", "RadioButton", "ComboBox", "DatePicker",
    "NumericStepper", "Slider", "Toggle", "Switch", "ProgressBar",
    "Icon", "CallOut", "Tooltip", "StickyNote", "Comment",
    "HRule", "VRule", "Arrow", "BreadCrumb", "Pagination",
    "Rating", "ColorPicker", "PointyButton", "RoundButton",
}

def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)

    max_w = max((int(c["x"]) + int(c["w"])) for c in components) if components else 948
    max_h = max((int(c["y"]) + int(c["h"])) for c in components) if components else 810

    controls = []
    for i, c in enumerate(components):
        tid = c.get("typeID", c.get("type", "Rectangle"))
        ctrl = {
            "ID": str(i + 1),
            "typeID": tid,
            "zOrder": str(i),
            "measuredW": str(c.get("measuredW", c["w"])),
            "measuredH": str(c.get("measuredH", c["h"])),
            "x": str(c["x"]),
            "y": str(c["y"]),
        }
        # Ajouter w/h seulement pour les composants qui en ont besoin
        if tid not in NO_WH_TYPES:
            ctrl["w"] = str(c["w"])
            ctrl["h"] = str(c["h"])

        controls.append(ctrl)

    mockup_data = json.dumps({
        "mockup": {
            "controls": {"control": controls},
            "measuredH": str(max_h),
            "measuredW": str(max_w),
            "mockupH": str(max_h),
            "mockupW": str(max_w),
            "version": "1.0",
        }
    }, separators=(",", ":"))

    mockup_attrs = json.dumps({"kind": "mockup", "name": project_name, "order": 938428.5264654435})
    branch_attrs = json.dumps({
        "projectDescription": "", "symbolLibraryID": "",
        "fontFace": "Balsamiq Sans", "fontSize": 13,
        "linkColor": 545684, "selectionColor": 9813234,
        "skinName": "programmatic",
    })
    resource_id = str(uuid.uuid4()).upper()

    conn = sqlite3.connect(output_path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE BRANCHES (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT);
        CREATE TABLE USERS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES TEXT);
        CREATE TABLE RESOURCES (
            ID VARCHAR(255), BRANCHID VARCHAR(255),
            ATTRIBUTES TEXT, DATA LONGTEXT,
            PRIMARY KEY (ID, BRANCHID),
            FOREIGN KEY (BRANCHID) REFERENCES BRANCHES(ID)
        );
        CREATE TABLE THUMBNAILS (ID VARCHAR(255) PRIMARY KEY, ATTRIBUTES MEDIUMTEXT);
        CREATE TABLE COMMENTS (
            ID VARCHAR(255) PRIMARY KEY, BRANCHID VARCHAR(255),
            RESOURCEID VARCHAR(255), DATA LONGTEXT,
            USERID VARCHAR(255), ATTRIBUTES TEXT,
            FOREIGN KEY (USERID) REFERENCES USERS(ID),
            FOREIGN KEY (RESOURCEID, BRANCHID) REFERENCES RESOURCES(ID, BRANCHID)
        );
        CREATE TABLE INFO (NAME VARCHAR(255) PRIMARY KEY, VALUE TEXT);
    """)
    c.executemany("INSERT INTO INFO (NAME, VALUE) VALUES (?,?)", [
        ("SchemaVersion", "2.0"), ("ArchiveFormat", "bmpr"),
        ("ArchiveRevisionUUID", ""), ("ArchiveAttributes", json.dumps({"name": project_name})),
        ("ArchiveRevision", "1"),
    ])
    c.execute("INSERT INTO BRANCHES VALUES (?,?)", ("Master", branch_attrs))
    c.execute("INSERT INTO RESOURCES (ID, BRANCHID, ATTRIBUTES, DATA) VALUES (?,?,?,?)",
        (resource_id, "Master", mockup_attrs, mockup_data))
    conn.commit()
    conn.close()
