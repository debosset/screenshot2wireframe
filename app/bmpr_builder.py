"""
Génère un fichier .bmpr moderne pour Balsamiq Wireframes.

Important : BMML est l'ancien format XML. Balsamiq Wireframes travaille avec des
projets .bmpr. Le fichier généré ici est un projet JSON contenant un wireframe.
"""
import json
import uuid
from typing import Any, Dict, List

TYPE_MAP = {
    "NavBar": "NavBar",
    "NavigationBar": "NavBar",
    "Button": "Button",
    "ButtonBar": "ButtonBar",
    "CheckBox": "CheckBox",
    "RadioButton": "RadioButton",
    "TextInput": "TextInput",
    "TextArea": "TextArea",
    "ComboBox": "ComboBox",
    "Label": "Label",
    "Title": "Title",
    "Image": "Image",
    "Rectangle": "Rectangle",
    "FieldSet": "FieldSet",
    "DataGrid": "DataGrid",
    "HRule": "HRule",
    "SearchBox": "SearchBox",
    "Paragraph": "Paragraph",
    "Icon": "Icon",
    "Link": "Link",
}

DEFAULT_PROPS = {
    "Button": {"text": "Button"},
    "CheckBox": {"text": "Option"},
    "RadioButton": {"text": "Option"},
    "Label": {"text": "Label"},
    "Title": {"text": "Title"},
    "NavBar": {"text": "Home, About, Contact"},
    "TextInput": {"text": ""},
    "TextArea": {"text": ""},
    "ComboBox": {"text": "Option 1\nOption 2\nOption 3"},
    "SearchBox": {"text": "Search"},
    "DataGrid": {"text": "Header 1, Header 2\nRow 1, Row 1"},
}


def _short_type(value: str | None) -> str:
    if not value:
        return "Rectangle"
    if "::" in value:
        value = value.split("::", 1)[1]
    return TYPE_MAP.get(value, "Rectangle")


def _control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    type_id = _short_type(comp.get("typeID") or comp.get("type"))
    control = {
        "ID": str(index + 1),
        "typeID": type_id,
        "zOrder": str(index),
        "measuredW": str(int(comp.get("measuredW", comp["w"]))),
        "measuredH": str(int(comp.get("measuredH", comp["h"]))),
        "x": str(int(comp["x"])),
        "y": str(int(comp["y"])),
        "w": str(int(comp["w"])),
        "h": str(int(comp["h"])),
    }
    control.update(DEFAULT_PROPS.get(type_id, {}))
    return control


def build_bmpr_data(components: List[Dict[str, Any]], name: str = "Wireframe") -> Dict[str, Any]:
    mockup_w = max((int(c["x"]) + int(c["w"]) for c in components), default=1000)
    mockup_h = max((int(c["y"]) + int(c["h"]) for c in components), default=800)
    resource_id = str(uuid.uuid4()).upper()

    mockup = {
        "controls": {"control": [_control(c, i) for i, c in enumerate(components)]},
        "attributes": {
            "name": name or "Wireframe",
            "order": 1,
            "parentID": None,
            "notes": None,
        },
        "branchID": "Master",
        "resourceID": resource_id,
        "mockupH": str(mockup_h),
        "mockupW": str(mockup_w),
        "measuredW": str(mockup_w),
        "measuredH": str(mockup_h),
        "version": "1.0",
        "calloutsOffset": {"x": 0, "y": 0},
    }

    return {
        "version": "1.0",
        "projectID": "0:1",
        "branchID": "Master",
        "mockups": [
            {
                "id": resource_id,
                "name": name or "Wireframe",
                "mockup": mockup,
            }
        ],
        "assets": [],
        "symbols": [],
        "trash": [],
    }


def build_bmpr(components: List[Dict[str, Any]], output_path: str, name: str = "Wireframe") -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        json.dump(build_bmpr_data(components, name), f, ensure_ascii=False, indent=2)
