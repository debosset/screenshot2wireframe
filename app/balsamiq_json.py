"""
Génère le JSON texte/plain attendu par le presse-papier Balsamiq.
Format validé depuis un Ctrl+C Balsamiq : mockup.controls.control + projectID.
"""
import json
import random
import uuid
from typing import Any, Dict, List

BALSAMIQ_COMPONENTS = {
    "Button": (61, 27),
    "ButtonBar": (159, 27),
    "RadioButton": (97, 23),
    "CheckBox": (78, 23),
    "Toggle": (54, 23),
    "Link": (60, 17),
    "TextInput": (79, 27),
    "TextArea": (200, 100),
    "ComboBox": (120, 27),
    "DatePicker": (120, 27),
    "SearchBox": (200, 27),
    "NavBar": (300, 30),
    "TabBar": (300, 42),
    "BreadCrumb": (250, 20),
    "Label": (100, 17),
    "Title": (200, 30),
    "Paragraph": (300, 80),
    "Image": (200, 150),
    "Icon": (32, 32),
    "Table": (300, 120),
    "DataGrid": (300, 150),
    "Rectangle": (200, 150),
    "RoundedRectangle": (200, 150),
    "FieldSet": (300, 200),
    "HRule": (200, 5),
}


def _short_type(opencv_type: str) -> str:
    if not opencv_type:
        return "Rectangle"
    if "::" in opencv_type:
        opencv_type = opencv_type.split("::", 1)[1]
    aliases = {
        "NavigationBar": "NavBar",
        "BrowserWindow": "BrowserWindow",
    }
    return aliases.get(opencv_type, opencv_type)


def classify(opencv_type: str, x: int, y: int, w: int, h: int, img_w: int = 1000, img_h: int = 800) -> str:
    """Retourne un typeID court compatible avec le clipboard Balsamiq."""
    existing = _short_type(opencv_type)
    if existing in BALSAMIQ_COMPONENTS:
        return existing

    ratio = w / h if h > 0 else 1
    area = w * h
    rel_y = y / img_h if img_h else 0

    if rel_y < 0.10 and w > img_w * 0.6 and h < 60:
        return "NavBar"
    if rel_y < 0.20 and w > img_w * 0.5 and 30 <= h <= 55:
        return "TabBar"
    if w > img_w * 0.4 and h < 35 and ratio > 8:
        return "Title"
    if ratio > 20 and h <= 5:
        return "HRule"
    if 4.0 <= ratio <= 14.0 and 20 <= h <= 38:
        return "SearchBox" if w > 250 else "TextInput"
    if 0.8 <= ratio <= 3.5 and 60 <= h <= 200 and 150 <= w <= 500:
        return "TextArea"
    if 1.5 <= ratio <= 5.0 and 20 <= h <= 42 and w <= 220:
        return "Button"
    if 0.6 <= ratio <= 1.8 and area < 2500 and w < 90:
        return "CheckBox"
    if 3.0 <= ratio <= 8.0 and 20 <= h <= 35 and 80 <= w <= 220:
        return "ComboBox"
    if 0.5 <= ratio <= 2.5 and area > 15000:
        return "Image"
    if ratio > 2.0 and h > 80 and w > 200:
        return "DataGrid"
    if area > 30000:
        return "FieldSet"
    if ratio > 5.0 and h < 25:
        return "Label"
    return "Rectangle"


def to_clipboard_json(components: List[Dict[str, Any]], project_id: str = "0:1") -> str:
    """
    Génère le texte à mettre dans navigator.clipboard.writeText(...).
    Les x/y des contrôles sont relatifs au groupe copié, comme dans un vrai Ctrl+C Balsamiq.
    """
    if not components:
        components = []

    min_x = min((int(c["x"]) for c in components), default=0)
    min_y = min((int(c["y"]) for c in components), default=0)
    max_x = max((int(c["x"]) + int(c["w"]) for c in components), default=0)
    max_y = max((int(c["y"]) + int(c["h"]) for c in components), default=0)
    group_w = max(1, max_x - min_x)
    group_h = max(1, max_y - min_y)

    controls = []
    for i, comp in enumerate(components):
        type_id = comp.get("typeID") or classify(
            comp.get("type", "Rectangle"),
            int(comp["x"]), int(comp["y"]), int(comp["w"]), int(comp["h"]),
            max_x or 1000, max_y or 800,
        )
        measured_w, measured_h = BALSAMIQ_COMPONENTS.get(type_id, (int(comp["w"]), int(comp["h"])))
        w = int(comp["w"])
        h = int(comp["h"])

        ctrl = {
            "ID": str(i),
            "typeID": type_id,
            "zOrder": str(i),
            "measuredW": str(measured_w),
            "measuredH": str(measured_h),
            "x": str(int(comp["x"]) - min_x),
            "y": str(int(comp["y"]) - min_y),
        }

        # Balsamiq n'ajoute pas w/h quand le composant est à sa taille par défaut.
        # On les garde uniquement quand le screenshot indique une taille différente.
        if w != measured_w:
            ctrl["w"] = str(w)
        if h != measured_h:
            ctrl["h"] = str(h)

        controls.append(ctrl)

    payload = {
        "mockup": {
            "controls": {"control": controls},
            "attributes": {
                "name": "New Wireframe 1",
                "order": random.random() * 1_000_000,
                "parentID": None,
                "notes": None,
            },
            "branchID": "Master",
            "resourceID": str(uuid.uuid4()).upper(),
            "mockupH": str(group_h),
            "mockupW": str(group_w),
            "measuredW": str(group_w),
            "measuredH": str(group_h),
            "version": "1.0",
            "calloutsOffset": {"x": 0, "y": 0},
        },
        "groupOffset": {"x": 0, "y": 0},
        "dependencies": [],
        "projectID": project_id or "0:1",
    }
    return json.dumps(payload, ensure_ascii=False, indent=4)
