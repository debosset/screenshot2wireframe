"""
Génère un .bmpr valide — schéma et règles confirmés depuis vrais fichiers Balsamiq.
Règle w/h : on met w ET h si la taille réelle diffère des mesuredW/H par défaut.
"""
import json, sqlite3, uuid, os
from typing import List, Dict, Any

# Tailles par défaut Balsamiq par typeID
MEASURED_DEFAULTS = {
    "Button": (61, 27), "PointyButton": (124, 27), "RoundButton": (32, 32),
    "ButtonBar": (159, 27), "CheckBox": (78, 23), "RadioButton": (97, 23),
    "TextInput": (79, 27), "TextArea": (200, 100), "ComboBox": (120, 27),
    "SearchBox": (200, 27), "TagInput": (200, 27), "Slider": (150, 20),
    "NumericStepper": (90, 27), "DatePicker": (120, 27), "Toggle": (54, 23),
    "Label": (100, 17), "Title": (200, 30), "SubTitle": (180, 24),
    "Paragraph": (300, 80), "Link": (60, 17), "HRule": (100, 10),
    "NavBar": (300, 30), "TabBar": (300, 42), "BreadCrumb": (250, 20),
    "Pagination": (200, 30), "Icon": (32, 32), "CallOut": (39, 39),
    "Image": (200, 150), "Rectangle": (200, 150), "Canvas": (100, 70),
    "FieldSet": (300, 200), "DataGrid": (300, 150), "Table": (300, 120),
    "ProgressBar": (200, 20), "Rating": (100, 20),
}


def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)

    max_w = max((int(c["x"]) + int(c["w"])) for c in components) if components else 948
    max_h = max((int(c["y"]) + int(c["h"])) for c in components) if components else 810

    controls = []
    for i, c in enumerate(components):
        tid = c.get("typeID", c.get("type", "Rectangle"))
        w, h = int(c["w"]), int(c["h"])
        def_w, def_h = MEASURED_DEFAULTS.get(tid, (w, h))

        ctrl = {
            "ID": str(i + 1),
            "typeID": tid,
            "zOrder": str(i),
            "measuredW": str(def_w),
            "measuredH": str(def_h),
            "x": str(c["x"]),
            "y": str(c["y"]),
        }

        # Mettre w/h si la taille réelle est différente des valeurs par défaut
        if w != def_w or h != def_h:
            ctrl["w"] = str(w)
            ctrl["h"] = str(h)

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
