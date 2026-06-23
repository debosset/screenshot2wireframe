"""
Format JSON exact Balsamiq Wireframes — reverse-engineered depuis vrais composants.
Ctrl+V dans Balsamiq colle directement les composants.
"""
import json, uuid
from typing import List, Dict, Any

# typeID exacts copiés depuis Balsamiq
TYPE_MAP = {
    "com.balsamiq.mockups::Button":        "Button",
    "com.balsamiq.mockups::TextInput":     "TextInput",
    "com.balsamiq.mockups::Label":         "Label",
    "com.balsamiq.mockups::CheckBox":      "CheckBox",
    "com.balsamiq.mockups::Image":         "Image",
    "com.balsamiq.mockups::NavigationBar": "NavBar",
    "com.balsamiq.mockups::Rectangle":     "Rectangle",
}

# Tailles mesurées par défaut (measuredW/H) observées dans Balsamiq
MEASURED_DEFAULTS = {
    "Button":    (61,  27),
    "ButtonBar": (159, 27),
    "CheckBox":  (78,  23),
    "TextInput": (79,  27),
    "NavBar":    (300, 30),
    "Label":     (100, 20),
    "Image":     (200, 150),
    "Rectangle": (200, 150),
    "CallOut":   (39,  39),
}

def _classify_to_balsamiq(opencv_type: str, w: int, h: int) -> str:
    """Convertit le type OpenCV en typeID Balsamiq exact."""
    tid = TYPE_MAP.get(opencv_type, "Rectangle")
    # Raffinage par ratio pour mieux deviner le composant
    ratio = w / h if h > 0 else 1
    if tid == "Rectangle":
        if ratio > 6 and h < 35:   return "TextInput"
        if ratio > 3 and h < 45:   return "Button"
        if ratio > 8:               return "NavBar"
    return tid

def _make_control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    tid = _classify_to_balsamiq(comp["type"], comp["w"], comp["h"])
    mw, mh = MEASURED_DEFAULTS.get(tid, (comp["w"], comp["h"]))
    return {
        "ID": str(index),
        "typeID": tid,
        "zOrder": str(index),
        "measuredW": str(mw),
        "measuredH": str(mh),
        "x": str(comp["x"]),
        "y": str(comp["y"]),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
    }

def to_clipboard_json(components: List[Dict[str, Any]], project_id: str = "0:1") -> str:
    controls = [_make_control(c, i) for i, c in enumerate(components)]
    max_x = max((c["x"] + c["w"]) for c in components) if components else 800
    max_y = max((c["y"] + c["h"]) for c in components) if components else 600
    sw, sh = str(max_x), str(max_y)
    return json.dumps({
        "mockup": {
            "controls": {"control": controls},
            "attributes": {
                "name": "New Wireframe 1",
                "order": 938428.5264654435,
                "parentID": None,
                "notes": None,
            },
            "branchID": "Master",
            "resourceID": str(uuid.uuid4()).upper(),
            "mockupH": sh,
            "mockupW": sw,
            "measuredW": sw,
            "measuredH": sh,
            "version": "1.0",
            "calloutsOffset": {"x": 0, "y": 0},
        },
        "groupOffset": {"x": 0, "y": 0},
        "dependencies": [],
        "projectID": project_id,
    }, indent=2)
