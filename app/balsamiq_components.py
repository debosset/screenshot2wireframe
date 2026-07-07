"""
Référentiel complet des composants Balsamiq (controlTypeID officiels).

Source : liste exhaustive des 66 contrôles natifs de Balsamiq Mockups.
Le préfixe "com.balsamiq.mockups::" est utilisé dans les fichiers .bmml (XML),
mais PAS dans le JSON presse-papier (celui qu'on colle dans Balsamiq
Cloud/Confluence), qui utilise le nom court ("Button", "TextInput", etc.).
C'est ce nom court que ce fichier référence.

Utilité :
1. VALID_TYPE_IDS : whitelist pour valider/filtrer tout typeID généré par l'IA
   ou par le pipeline OCR avant de construire le JSON à coller.
2. TYPE_ALIASES : corrige les noms plausibles mais invalides qu'un LLM peut
   halluciner, en les remappant vers le vrai typeID.
3. MEASURED : tailles par défaut (measuredW/measuredH) pour un rendu correct
   à l'ouverture dans Balsamiq.
"""
from typing import Dict, Tuple

# ── Tous les typeID valides connus de Balsamiq ────────────────────────────
# Base : liste exhaustive de 65 controlTypeID extraits d'un fichier de
# référence Balsamiq officiel (un exemplaire de chaque contrôle).
# + Rectangle et SubTitle, confirmés comme contrôles réels par la doc/les
#   tutoriels Balsamiq mais absents de ce fichier de référence particulier.
# Volontairement PAS inclus : "Table" et "Window", que je ne peux confirmer
# nulle part comme de vrais typeID Balsamiq (probablement des noms plausibles
# mais faux, comme NavBar) — ils sont redirigés vers DataGrid via TYPE_ALIASES.
VALID_TYPE_IDS = {
    "Accordion", "Arrow", "BreadCrumbs", "BrowserWindow", "Button", "ButtonBar",
    "Calendar", "CallOut", "BarChart", "ColumnChart", "LineChart", "PieChart",
    "CheckBox", "ColorPicker", "ComboBox", "StickyNote", "CoverFlow", "DataGrid",
    "DateChooser", "TitleWindow", "FormattingToolbar", "FieldSet", "HelpButton",
    "HCurly", "HRule", "HorizontalScrollBar", "HSlider", "VSplitter", "Icon",
    "IconLabel", "Image", "Label", "Link", "LinkBar", "List", "Menu", "MenuBar",
    "ModalScreen", "MultilineButton", "NumericStepper", "Paragraph",
    "MediaControls", "ProgressBar", "RadioButton", "Canvas", "RedX",
    "RoundButton", "ScratchOut", "SearchBox", "Map", "TabBar", "TagCloud",
    "TextArea", "TextInput", "Title", "Tooltip", "Tree", "VCurly", "VRule",
    "VerticalScrollBar", "VSlider", "HSplitter", "VerticalTabBar",
    "VideoPlayer", "VolumeSlider", "Webcam",
    "SubTitle", "Rectangle",
}

# ── Corrections des typeID que l'IA invente souvent ───────────────────────
# clé = ce que le LLM génère parfois (plausible mais faux)
# valeur = le vrai typeID Balsamiq le plus proche
TYPE_ALIASES: Dict[str, str] = {
    "NavBar": "LinkBar",
    "Navbar": "LinkBar",
    "NavigationBar": "LinkBar",
    "BreadCrumb": "BreadCrumbs",
    "Breadcrumb": "BreadCrumbs",
    "Pagination": "ButtonBar",       # pas de contrôle natif -> approximé
    "Dropdown": "ComboBox",
    "Select": "ComboBox",
    "Table": "DataGrid",
    "Grid": "DataGrid",
    "Divider": "HRule",
    "Separator": "HRule",
    "Textbox": "TextInput",
    "Input": "TextInput",
    "TextField": "TextInput",
    "Checkbox": "CheckBox",
    "Radio": "RadioButton",
    "Avatar": "Icon",
    "Badge": "Label",
    "Chip": "Label",
    "Tabs": "TabBar",
    "Modal": "ModalScreen",
    "Dialog": "ModalScreen",
    "SearchBar": "SearchBox",
    "Slider": "HSlider",
    "ProgressBarControl": "ProgressBar",
}

# ── Tailles par défaut (measuredW, measuredH) en px base 1000 ────────────
MEASURED: Dict[str, Tuple[int, int]] = {
    "Title":        (300, 30),
    "SubTitle":     (250, 24),
    "Label":        (100, 17),
    "Link":         (150, 17),
    "TextInput":    (79, 27),
    "TextArea":     (200, 100),
    "Button":       (61, 27),
    "ButtonBar":    (159, 27),
    "CheckBox":     (100, 23),
    "RadioButton":  (97, 23),
    "HRule":        (100, 10),
    "VRule":        (10, 100),
    "Rectangle":    (200, 150),
    "FieldSet":     (300, 200),
    "Image":        (200, 150),
    "ComboBox":     (140, 27),
    "DataGrid":     (300, 150),
    "TabBar":       (300, 27),
    "LinkBar":      (400, 27),
    "MenuBar":      (400, 27),
    "Menu":         (140, 120),
    "BreadCrumbs":  (300, 20),
    "Accordion":    (250, 150),
    "List":         (150, 120),
    "Tree":         (200, 150),
    "ProgressBar":  (200, 20),
    "SearchBox":    (200, 27),
    "DateChooser":  (150, 27),
    "NumericStepper": (60, 27),
    "Paragraph":    (300, 60),
    "StickyNote":   (140, 100),
    "Icon":         (24, 24),
    "IconLabel":    (100, 24),
    "ModalScreen":  (400, 300),
    "TitleWindow":  (400, 300),
    "BrowserWindow":(600, 400),
    "Tooltip":      (150, 40),
    "MultilineButton": (140, 45),
    "ColorPicker":  (27, 27),
    "Calendar":     (250, 200),
    "TagCloud":     (250, 100),
    "CallOut":      (30, 30),
    "Arrow":        (60, 20),
    "RedX":         (24, 24),
    "RoundButton":  (40, 40),
    "HelpButton":   (24, 24),
    "VideoPlayer":  (300, 200),
    "Webcam":       (200, 150),
    "Map":          (300, 200),
    "BarChart":     (250, 180),
    "ColumnChart":  (250, 180),
    "LineChart":    (250, 180),
    "PieChart":     (180, 180),
}

DEFAULT_MEASURED: Tuple[int, int] = (100, 20)


def normalize_type_id(tid: str) -> str:
    """
    Retourne un typeID garanti valide pour Balsamiq.
    - Si déjà valide -> inchangé.
    - Si alias connu -> remappé.
    - Sinon -> fallback "Rectangle" (toujours accepté par Balsamiq).
    """
    if not tid:
        return "Rectangle"
    if tid in VALID_TYPE_IDS:
        return tid
    if tid in TYPE_ALIASES:
        return TYPE_ALIASES[tid]
    # essai insensible à la casse
    for valid in VALID_TYPE_IDS:
        if valid.lower() == tid.lower():
            return valid
    for alias, target in TYPE_ALIASES.items():
        if alias.lower() == tid.lower():
            return target
    return "Rectangle"


def get_measured(tid: str, fallback_w: int = 100, fallback_h: int = 20) -> Tuple[int, int]:
    return MEASURED.get(tid, (fallback_w, fallback_h))


def safe_int_str(value, default: int) -> str:
    """
    Convertit une valeur en entier puis en string, sans jamais planter.
    Groq met parfois le nom d'une clé ou une valeur aberrante dans un champ
    numérique (x/y/w/h/measuredW/measuredH) -- dans ce cas on retombe sur
    `default` plutôt que de laisser une valeur invalide se propager jusqu'au
    fichier .bmpr final.
    """
    try:
        return str(int(value))
    except (TypeError, ValueError):
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            return str(default)


_NUMERIC_FIELDS = {"x": 0, "y": 0, "w": 100, "h": 20, "measuredW": 100, "measuredH": 20}


def sanitize_numeric_fields(components):
    """Coerce x/y/w/h/measuredW/measuredH vers des entiers valides (en string)."""
    fixed = []
    for c in components:
        c = dict(c)
        for field, default in _NUMERIC_FIELDS.items():
            if field in c:
                c[field] = safe_int_str(c[field], default)
        fixed.append(c)
    return fixed


def sanitize_components(components):
    """
    Mode sûr : passe chaque composant dans normalize_type_id() pour garantir
    qu'aucun typeID invalide n'est envoyé à Balsamiq. À appeler juste avant
    la construction du JSON presse-papier / du .bmpr.
    Retourne (components_corrigés, liste_des_corrections_effectuées).
    """
    fixed = []
    corrections = []
    for c in components:
        tid = c.get("typeID", "Rectangle")
        new_tid = normalize_type_id(tid)
        if new_tid != tid:
            corrections.append({"from": tid, "to": new_tid, "id": c.get("ID")})
            c = {**c, "typeID": new_tid}
        fixed.append(c)
    return fixed, corrections
