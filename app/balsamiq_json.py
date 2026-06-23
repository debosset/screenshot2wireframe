"""
Génère le JSON text/plain attendu par le presse-papier Balsamiq.

Deux modes sont disponibles :
- mode="all"  : essaie d'utiliser le catalogue complet des typeID Balsamiq connus.
- mode="safe" : force uniquement les typeID déjà validés au collage.
"""
import json
import random
import uuid
from typing import Any, Dict, List

# Tailles par défaut observées / usuelles dans Balsamiq.
# Le typeID est volontairement le nom court utilisé dans le JSON clipboard Balsamiq.
BALSAMIQ_COMPONENTS = {
    # Basique / texte
    "Label": (100, 17),
    "Title": (200, 30),
    "SubTitle": (180, 24),
    "Paragraph": (300, 80),
    "Text": (100, 17),
    "Link": (60, 17),
    "BlockQuote": (300, 60),
    "CallOut": (39, 39),
    "StickyNote": (120, 120),
    "Tooltip": (120, 40),
    "Comment": (200, 80),

    # Formulaires
    "Button": (61, 27),
    "ButtonBar": (159, 27),
    "TextInput": (79, 27),
    "TextArea": (200, 100),
    "ComboBox": (120, 27),
    "CheckBox": (78, 23),
    "RadioButton": (97, 23),
    "NumericStepper": (90, 27),
    "DateChooser": (120, 27),
    "DatePicker": (120, 27),
    "SearchBox": (200, 27),
    "TagInput": (200, 27),
    "Slider": (150, 20),
    "Switch": (54, 23),
    "Toggle": (54, 23),
    "ProgressBar": (200, 20),
    "ColorPicker": (80, 27),
    "PointyButton": (100, 27),

    # Mise en page / formes
    "Rectangle": (200, 150),
    "RoundButton": (100, 40),
    "RoundedRectangle": (200, 150),
    "Circle": (100, 100),
    "Ellipse": (100, 100),
    "Triangle": (100, 100),
    "Diamond": (100, 100),
    "Polygon": (100, 100),
    "Line": (100, 5),
    "HRule": (200, 5),
    "VRule": (5, 200),
    "Arrow": (100, 20),
    "CurlyBrace": (80, 120),
    "Bracket": (40, 120),
    "VerticalCurlyBrace": (120, 80),
    "VerticalBracket": (120, 40),
    "Canvas": (400, 300),
    "FieldSet": (300, 200),
    "Panel": (300, 400),
    "Modal": (400, 300),
    "Container": (300, 200),

    # Navigation
    "NavBar": (300, 30),
    "TabBar": (300, 42),
    "TabsBar": (300, 42),
    "VerticalTabBar": (120, 220),
    "BreadCrumb": (250, 20),
    "Menu": (120, 120),
    "TreePane": (150, 200),
    "Accordion": (200, 120),
    "SiteMap": (300, 200),
    "Pagination": (200, 30),
    "IconLabel": (120, 40),

    # Données / listes
    "List": (200, 150),
    "ColumnList": (300, 150),
    "MultiColumnList": (300, 150),
    "DataGrid": (300, 150),
    "Table": (300, 120),
    "Chart": (300, 200),
    "BarChart": (300, 200),
    "PieChart": (200, 200),
    "LineChart": (300, 200),

    # Médias / icônes
    "Image": (200, 150),
    "Icon": (32, 32),
    "ImagePlaceholder": (200, 150),
    "VideoPlayer": (300, 200),
    "Video": (300, 200),
    "Map": (300, 200),
    "Avatar": (64, 64),

    # Browser / desktop / mobile
    "BrowserWindow": (500, 400),
    "Browser": (500, 400),
    "Window": (400, 300),
    "Dialog": (400, 300),
    "Phone": (200, 400),
    "iPhone": (200, 400),
    "Tablet": (400, 300),
    "iPad": (400, 550),
    "Keyboard": (400, 150),
    "Calculator": (180, 240),

    # Divers
    "Spinner": (30, 30),
    "Rating": (100, 20),
    "Scratch": (100, 80),
    "HelpButton": (26, 26),
    "AlertBox": (300, 80),
}

SAFE_COMPONENTS = {
    "Button": (61, 27),
    "RadioButton": (97, 23),
    "CheckBox": (78, 23),
    "TextInput": (79, 27),
    "Label": (100, 17),
}

ALIASES = {
    "NavigationBar": "NavBar",
    "Browser": "BrowserWindow",
    "DatePicker": "DateChooser",
    "RoundedRectangle": "Rectangle",
    "ImagePlaceholder": "Image",
    "Video": "VideoPlayer",
    "TabsBar": "TabBar",
    "Switch": "Toggle",
}


def _short_type(opencv_type: str) -> str:
    if not opencv_type:
        return "Rectangle"
    if "::" in opencv_type:
        opencv_type = opencv_type.split("::", 1)[1]
    return ALIASES.get(opencv_type, opencv_type)


def classify(opencv_type: str, x: int, y: int, w: int, h: int, img_w: int = 1000, img_h: int = 800, mode: str = "all") -> str:
    """Classifie une zone détectée en typeID Balsamiq."""
    catalog = SAFE_COMPONENTS if mode == "safe" else BALSAMIQ_COMPONENTS
    existing = _short_type(opencv_type)
    if existing in catalog:
        return existing

    ratio = w / h if h > 0 else 1
    area = w * h
    rel_y = y / img_h if img_h else 0

    if mode == "safe":
        if 0.65 <= ratio <= 1.45 and area < 2600 and w <= 90 and h <= 90:
            return "CheckBox"
        if ratio >= 5.0 and h <= 22:
            return "Label"
        if ratio >= 3.2 and 18 <= h <= 45:
            return "TextInput"
        if 1.4 <= ratio <= 6.5 and 18 <= h <= 48 and w <= 260:
            return "Button"
        return "Button"

    # Mode complet : composants plus riches.
    if rel_y < 0.10 and w > img_w * 0.60 and h <= 70:
        return "NavBar"
    if rel_y < 0.20 and w > img_w * 0.50 and 30 <= h <= 60:
        return "TabBar"
    if ratio > 20 and h <= 6:
        return "HRule"
    if 0.65 <= ratio <= 1.45 and area < 2600 and w <= 90 and h <= 90:
        return "CheckBox"
    if ratio >= 9 and h <= 26:
        return "Label"
    if ratio >= 3.2 and 18 <= h <= 45:
        if w >= 250:
            return "SearchBox"
        return "TextInput"
    if 1.4 <= ratio <= 6.5 and 18 <= h <= 50 and w <= 280:
        return "Button"
    if 0.8 <= ratio <= 3.5 and 60 <= h <= 220 and 150 <= w <= 600:
        return "TextArea"
    if ratio > 2.0 and h > 80 and w > 240:
        return "DataGrid"
    if 0.5 <= ratio <= 2.5 and area > 15000:
        return "Image"
    if area > 30000:
        return "FieldSet"
    return "Rectangle"


def to_clipboard_json(components: List[Dict[str, Any]], project_id: str = "0:1", mode: str = "all") -> str:
    """Génère le texte à mettre dans navigator.clipboard.writeText(...)."""
    mode = "safe" if mode == "safe" else "all"
    catalog = SAFE_COMPONENTS if mode == "safe" else BALSAMIQ_COMPONENTS

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
            max_x or 1000, max_y or 800, mode=mode,
        )
        type_id = _short_type(type_id)
        if type_id not in catalog:
            type_id = classify(type_id, int(comp["x"]), int(comp["y"]), int(comp["w"]), int(comp["h"]), max_x or 1000, max_y or 800, mode=mode)
        if type_id not in catalog:
            type_id = "Button" if mode == "safe" else "Rectangle"

        measured_w, measured_h = catalog[type_id]
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
