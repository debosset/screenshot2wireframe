"""
Génère le JSON texte/plain attendu par le presse-papier Balsamiq.
Format validé depuis un Ctrl+C Balsamiq : mockup.controls.control + projectID.
"""
import json
import random
import uuid
from typing import Any, Dict, List

BALSAMIQ_COMPONENTS = {
    # Types validés / très sûrs pour le clipboard Balsamiq text/plain.
    # Important : éviter NavBar, Rectangle, SearchBox, DataGrid, etc. car selon
    # la version Balsamiq ils sont refusés au collage.
    "Button": (61, 27),
    "RadioButton": (97, 23),
    "CheckBox": (78, 23),
    "TextInput": (79, 27),
    "Label": (100, 17),
}

SAFE_TYPEIDS = set(BALSAMIQ_COMPONENTS.keys())


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
    """
    Retourne uniquement des typeID validés au collage Balsamiq.

    Le test utilisateur a confirmé que le JSON text/plain fonctionne avec CheckBox.
    Le collage échouait ensuite avec des typeID plus risqués comme NavBar/Rectangle.
    On force donc une palette sûre : CheckBox, RadioButton, TextInput, Button, Label.
    """
    existing = _short_type(opencv_type)
    if existing in SAFE_TYPEIDS:
        return existing

    ratio = w / h if h > 0 else 1
    area = w * h

    # Petit carré : case à cocher
    if 0.65 <= ratio <= 1.45 and area < 2600 and w <= 90 and h <= 90:
        return "CheckBox"

    # Texte / libellé très plat
    if ratio >= 5.0 and h <= 22:
        return "Label"

    # Champ de saisie large et peu haut
    if ratio >= 3.2 and 18 <= h <= 45:
        return "TextInput"

    # Bouton classique
    if 1.4 <= ratio <= 6.5 and 18 <= h <= 48 and w <= 260:
        return "Button"

    # Fallback volontairement sûr : Button accepte bien w/h personnalisés.
    # C'est moins joli qu'un rectangle, mais ça colle dans Balsamiq.
    return "Button"


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
        if type_id not in SAFE_TYPEIDS:
            type_id = classify(type_id, int(comp["x"]), int(comp["y"]), int(comp["w"]), int(comp["h"]), max_x or 1000, max_y or 800)
        measured_w, measured_h = BALSAMIQ_COMPONENTS[type_id]
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
