"""
Génère le JSON format presse-papier Balsamiq — format exact reverse-engineered.
Se colle directement dans Balsamiq avec Ctrl+V.
"""
import json
from typing import List, Dict, Any

# TypeID courts — format exact Balsamiq Cloud/Confluence
TYPE_MAP = {
    "com.balsamiq.mockups::Button":        "Button",
    "com.balsamiq.mockups::TextInput":     "TextInput",
    "com.balsamiq.mockups::Label":         "Label",
    "com.balsamiq.mockups::CheckBox":      "CheckBox",
    "com.balsamiq.mockups::Image":         "Image",
    "com.balsamiq.mockups::NavigationBar": "NavBar",
    "com.balsamiq.mockups::Rectangle":     "Rectangle",
}

DEFAULTS = {
    "Button":    {"text": "Button"},
    "TextInput": {"text": "", "hint": "Placeholder..."},
    "Label":     {"text": "Label", "size": "14"},
    "CheckBox":  {"text": "Option"},
    "NavBar":    {"text": "Home, About, Contact"},
    "Image":     {},
    "Rectangle": {},
}

def _make_control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    tid = TYPE_MAP.get(comp["type"], "Rectangle")
    ctrl = {
        "ID": str(index + 1),
        "typeID": tid,
        "zOrder": str(index),
        "measuredW": str(comp.get("measuredW", comp["w"])),
        "measuredH": str(comp.get("measuredH", comp["h"])),
        "x": str(comp["x"]),
        "y": str(comp["y"]),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
    }
    props = DEFAULTS.get(tid, {})
    if props:
        ctrl["properties"] = props
    return ctrl

def to_clipboard_json(components: List[Dict[str, Any]], project_id: str = "0:1") -> str:
    """
    Retourne le JSON exact que Balsamiq attend pour Ctrl+V.
    Structure reverse-engineered depuis Balsamiq Wireframes Cloud.
    """
    controls = [_make_control(c, i) for i, c in enumerate(components)]

    # Calcul de la bounding box pour mockupW/H
    max_x = max((c["x"] + c["w"]) for c in components) if components else 1000
    max_y = max((c["y"] + c["h"]) for c in components) if components else 800

    payload = {
        "mockup": {
            "controls": {
                "control": controls
            },
            "attributes": {
                "name": "Wireframe",
                "order": 0,
                "parentID": None,
                "notes": None,
            },
            "branchID": "Master",
            "mockupH": str(max_y),
            "mockupW": str(max_x),
            "measuredW": str(max_x),
            "measuredH": str(max_y),
            "version": "1.0",
        },
        "groupOffset": {"x": 0, "y": 0},
        "dependencies": [],
        "projectID": project_id,
    }
    return json.dumps(payload, indent=2)
