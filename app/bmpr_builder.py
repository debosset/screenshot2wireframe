import json
import sqlite3
import zlib
import time
from typing import List, Dict, Any

TYPE_MAP = {
    "com.balsamiq.mockups::Button": "com.balsamiq.mockups::Button",
    "com.balsamiq.mockups::TextInput": "com.balsamiq.mockups::TextInput",
    "com.balsamiq.mockups::Label": "com.balsamiq.mockups::Label",
    "com.balsamiq.mockups::CheckBox": "com.balsamiq.mockups::CheckBox",
    "com.balsamiq.mockups::Image": "com.balsamiq.mockups::Image",
    "com.balsamiq.mockups::NavigationBar": "com.balsamiq.mockups::NavBar",
    "com.balsamiq.mockups::Rectangle": "com.balsamiq.mockups::Rectangle",
}

def _make_control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    type_id = TYPE_MAP.get(comp["type"], "com.balsamiq.mockups::Rectangle")
    properties = {}
    if "Button" in type_id:
        properties["text"] = "Button"
    elif "TextInput" in type_id:
        properties["text"] = ""
    elif "Label" in type_id:
        properties["text"] = "Label"
    elif "CheckBox" in type_id:
        properties["text"] = "Option"
    elif "NavBar" in type_id:
        properties["text"] = "Home, About, Contact"
    return {
        "ID": str(index + 1),
        "typeID": type_id,
        "zOrder": index,
        "locked": "false",
        "isInGroup": "-1",
        "x": str(comp["x"]),
        "y": str(comp["y"]),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
        "measuredW": str(comp.get("measuredW", comp["w"])),
        "measuredH": str(comp.get("measuredH", comp["h"])),
        "properties": properties,
    }

def _encode(data: dict) -> bytes:
    raw = json.dumps(data, separators=(",", ":"))
    return zlib.compress(raw.encode("utf-8"), level=6)

def build_bmpr(components: List[Dict[str, Any]], output_path: str, project_name: str = "Wireframe") -> None:
    controls = [_make_control(c, i) for i, c in enumerate(components)]
    mockup_data = {
        "mockup": {
            "measuredW": "1000",
            "measuredH": "800",
            "version": "1.0",
            "controls": {"control": controls}
        }
    }
    project_data = {
        "projectData": {
            "version": "1.0",
            "navigatorSortOrder": "manual",
            "currentBranch": "master"
        }
    }
    now = int(time.time() * 1000)
    conn = sqlite3.connect(output_path)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS resources (
        ID TEXT PRIMARY KEY NOT NULL,
        branchID TEXT NOT NULL DEFAULT 'master',
        parentID TEXT,
        name TEXT,
        kind TEXT,
        data BLOB,
        thumbnail BLOB,
        trashed INTEGER NOT NULL DEFAULT 0,
        "order" INTEGER NOT NULL DEFAULT 0,
        ts INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS branches (
        ID TEXT PRIMARY KEY NOT NULL,
        name TEXT,
        ts INTEGER
    )""")
    cur.execute("INSERT OR REPLACE INTO branches VALUES (?, ?, ?)", ("master", "master", now))
    cur.execute(
        'INSERT OR REPLACE INTO resources (ID, branchID, parentID, name, kind, data, ts, "order") VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ("__project__", "master", None, project_name, "project", _encode(project_data), now, 0)
    )
    cur.execute(
        'INSERT OR REPLACE INTO resources (ID, branchID, parentID, name, kind, data, ts, "order") VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ("mockups/Mockup1.bmml", "master", "__root__", project_name, "mockup", _encode(mockup_data), now, 0)
    )
    conn.commit()
    conn.close()
