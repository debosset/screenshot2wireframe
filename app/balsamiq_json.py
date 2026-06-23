"""
Génère le JSON format presse-papier Balsamiq.
TypeIDs et tailles mesurées reverse-engineered depuis vrais composants Balsamiq Cloud.
"""
import json, uuid
from typing import List, Dict, Any

# ── Table complète des typeIDs Balsamiq avec tailles par défaut ──────────────
# (measuredW, measuredH) = taille par défaut observée dans Balsamiq
BALSAMIQ_COMPONENTS = {
    # Boutons & actions
    "Button":          (61,  27),
    "ButtonBar":       (159, 27),
    "RadioButton":     (97,  23),
    "CheckBox":        (78,  23),
    "Toggle":          (54,  23),
    "Link":            (60,  17),

    # Champs de saisie
    "TextInput":       (79,  27),
    "TextArea":        (200, 100),
    "ComboBox":        (120, 27),
    "DatePicker":      (120, 27),
    "Slider":          (150, 20),
    "NumericStepper":  (90,  27),
    "TagInput":        (200, 27),
    "SearchBox":       (200, 27),

    # Navigation
    "NavBar":          (300, 30),
    "TabBar":          (300, 42),
    "BreadCrumb":      (250, 20),
    "Menu":            (120, 120),
    "TreePane":        (150, 200),
    "Accordion":       (200, 120),
    "SiteMap":         (300, 200),
    "Pagination":      (200, 30),

    # Texte & labels
    "Label":           (100, 17),
    "Title":           (200, 30),
    "Paragraph":       (300, 80),
    "BlockQuote":      (300, 60),
    "CallOut":         (39,  39),
    "Tooltip":         (120, 40),

    # Médias & contenus
    "Image":           (200, 150),
    "Icon":            (32,  32),
    "Video":           (300, 200),
    "Map":             (300, 200),
    "Chart":           (300, 200),
    "Table":           (300, 120),
    "DataGrid":        (300, 150),

    # Mise en page
    "Rectangle":       (200, 150),
    "RoundedRectangle":(200, 150),
    "Ellipse":         (100, 100),
    "Triangle":        (100, 100),
    "Arrow":           (100, 20),
    "Line":            (100, 5),
    "HRule":           (200, 5),

    # Conteneurs
    "FieldSet":        (300, 200),
    "Container":       (300, 200),
    "Canvas":          (400, 300),
    "Modal":           (400, 300),
    "Panel":           (300, 400),

    # Browser / Mobile
    "Browser":         (500, 400),
    "Window":          (400, 300),
    "Phone":           (200, 400),
    "Tablet":          (400, 300),
    "iPad":            (400, 550),

    # Listes
    "List":            (200, 150),
    "ColumnList":      (300, 150),
    "MultiColumnList": (300, 150),

    # Divers
    "ProgressBar":     (200, 20),
    "Spinner":         (30,  30),
    "Rating":          (100, 20),
    "Comment":         (200, 80),
    "StickyNote":      (120, 120),
    "Scratch":         (100, 80),
}

# ── Heuristiques de classification depuis OpenCV ─────────────────────────────

def classify(opencv_type: str, x: int, y: int, w: int, h: int, img_w: int = 1000, img_h: int = 800) -> str:
    """
    Convertit un type OpenCV générique en typeID Balsamiq précis
    en utilisant la position, le ratio et la taille du composant.
    """
    ratio = w / h if h > 0 else 1
    area  = w * h
    rel_y = y / img_h
    rel_x = x / img_w

    # ── Barre de navigation (pleine largeur, haut de page) ──────────────────
    if rel_y < 0.10 and w > img_w * 0.6 and h < 60:
        return "NavBar"

    # ── Barre de tabs (pleine largeur, proche du haut, hauteur moyenne) ─────
    if rel_y < 0.20 and w > img_w * 0.5 and 30 <= h <= 55:
        return "TabBar"

    # ── En-tête / Titre (pleine largeur, court, haut de section) ────────────
    if w > img_w * 0.4 and h < 35 and ratio > 8:
        return "Title"

    # ── Ligne de séparation (très plate et large) ───────────────────────────
    if ratio > 20 and h <= 5:
        return "HRule"

    # ── Champ de saisie (très large et plat) ────────────────────────────────
    if 4.0 <= ratio <= 14.0 and 20 <= h <= 38:
        if w > 250:
            return "SearchBox"
        return "TextInput"

    # ── Zone de texte multiligne (ratio ~1, surface moyenne) ────────────────
    if 0.8 <= ratio <= 3.5 and 60 <= h <= 200 and 150 <= w <= 500:
        return "TextArea"

    # ── Bouton (ratio moyen, petite hauteur) ─────────────────────────────────
    if 1.5 <= ratio <= 5.0 and 20 <= h <= 42 and w <= 200:
        return "Button"

    # ── Checkbox (petit carré) ───────────────────────────────────────────────
    if 0.6 <= ratio <= 1.8 and area < 2500 and w < 90:
        return "CheckBox"

    # ── ComboBox (ratio large, petite hauteur, largeur intermédiaire) ────────
    if 3.0 <= ratio <= 8.0 and 20 <= h <= 35 and 80 <= w <= 200:
        return "ComboBox"

    # ── Image / placeholder (grande surface, peu de détails internes) ────────
    if 0.5 <= ratio <= 2.5 and area > 15000:
        return "Image"

    # ── Tableau / DataGrid (grande largeur, hauteur significative) ───────────
    if ratio > 2.0 and h > 80 and w > 200:
        return "DataGrid"

    # ── Conteneur / FieldSet ─────────────────────────────────────────────────
    if area > 30000:
        return "FieldSet"

    # ── Label / texte court ──────────────────────────────────────────────────
    if ratio > 5.0 and h < 25:
        return "Label"

    # ── Fallback ─────────────────────────────────────────────────────────────
    return "Rectangle"


def _make_control(comp: Dict[str, Any], index: int, img_w: int = 1000, img_h: int = 800) -> Dict[str, Any]:
    tid = classify(comp["type"], comp["x"], comp["y"], comp["w"], comp["h"], img_w, img_h)
    mw, mh = BALSAMIQ_COMPONENTS.get(tid, (comp["w"], comp["h"]))
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
    """JSON exact attendu par Balsamiq pour Ctrl+V."""
    # Estimation de la taille de l'image source depuis les coordonnées max
    img_w = max((c["x"] + c["w"]) for c in components) if components else 1000
    img_h = max((c["y"] + c["h"]) for c in components) if components else 800

    controls = [_make_control(c, i, img_w, img_h) for i, c in enumerate(components)]
    sw, sh = str(img_w), str(img_h)

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
