import json, sqlite3, zlib, time, os
from typing import List, Dict, Any

TYPE_MAP = {
    "com.balsamiq.mockups::Button":        "com.balsamiq.mockups::Button",
    "com.balsamiq.mockups::TextInput":     "com.balsamiq.mockups::TextInput",
    "com.balsamiq.mockups::Label":         "com.balsamiq.mockups::Label",
    "com.balsamiq.mockups::CheckBox":      "com.balsamiq.mockups::CheckBox",
    "com.balsamiq.mockups::Image":         "com.balsamiq.mockups::Image",
    "com.balsamiq.mockups::NavigationBar": "com.balsamiq.mockups::NavBar",
    "com.balsamiq.mockups::Rectangle":     "com.balsamiq.mockups::Rectangle",
}

def _encode(data: dict) -> bytes:
    return zlib.compress(json.dumps(data, separators=(',',':')).encode('utf-8'), level=6)

def _ctrl(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    tid = TYPE_MAP.get(comp["type"], "com.balsamiq.mockups::Rectangle")
    props = {}
    if "Button" in tid:      props["text"] = "Button"
    elif "TextInput" in tid: props["text"] = ""
    elif "Label" in tid:     props["text"] = "Label"
    elif "CheckBox" in tid:  props["text"] = "Option"
    elif "NavBar" in tid:    props["text"] = "Home, About, Contact"
    return {
        "ID": str(index + 1),
        "typeID": tid,
        "zOrder": str(index),
        "locked": "false",
        "isInGroup": "-1",
        "x": str(comp["x"]),
        "y": str(comp["y"]),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
        "measuredW": str(comp.get("measuredW", comp["w"])),
        "measuredH": str(comp.get("measuredH", comp["h"])),
        "properties": props,
    }

def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    if os.path.exists(output_path):
        os.unlink(output_path)
    now = int(time.time() * 1000)

    mockup = {
        "mockup": {
            "measuredW": 1000,   # int — obligatoire
            "measuredH": 800,    # int — obligatoire
            "version": "1.0",
            "controls": {"control": [_ctrl(c, i) for i, c in enumerate(components)]}
        }
    }
    project = {
        "projectData": {
            "version": "1.0",
            "navigatorSortOrder": "manual"
        }
    }

    conn = sqlite3.connect(output_path)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE branches (ID TEXT PRIMARY KEY, name TEXT, ts INTEGER);
        CREATE TABLE resources (
            ID TEXT PRIMARY KEY,
            branchID TEXT NOT NULL DEFAULT 'master',
            parentID TEXT, name TEXT, kind TEXT,
            data BLOB, thumbnail BLOB,
            trashed INTEGER NOT NULL DEFAULT 0,
            "order" INTEGER NOT NULL DEFAULT 0,
            ts INTEGER
        );
    """)
    cur.execute("INSERT INTO branches VALUES (?,?,?)", ("master","master",now))
    cur.execute(
        'INSERT INTO resources (ID,branchID,parentID,name,kind,data,ts,"order") VALUES (?,?,?,?,?,?,?,?)',
        ("__project__","master",None,project_name,"project",_encode(project),now,0)
    )
    cur.execute(
        'INSERT INTO resources (ID,branchID,parentID,name,kind,data,ts,"order") VALUES (?,?,?,?,?,?,?,?)',
        ("mockups/Mockup1.bmml","master","__root__",project_name,"mockup",_encode(mockup),now,0)
    )
    conn.commit()
    conn.close()
