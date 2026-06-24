"""
Lit le texte dans les zones détectées par OpenCV.
Permet d'identifier les labels au-dessus des champs et le contenu des zones.
"""
import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Any, Optional
import re


def _clean(text: str) -> str:
    """Nettoie le texte OCR : supprime les caractères parasites."""
    text = text.strip()
    text = re.sub(r'[|\\{}\[\]<>]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _read_zone(img: np.ndarray, x: int, y: int, w: int, h: int, lang: str = "fra+eng") -> str:
    """Lit le texte dans une zone de l'image."""
    # Marges légères pour capturer le texte complet
    pad = 4
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img.shape[1], x + w + pad)
    y2 = min(img.shape[0], y + h + pad)

    roi = img[y1:y2, x1:x2]
    if roi.size == 0:
        return ""

    # Prétraitement pour améliorer l'OCR
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
    # Agrandir pour meilleure reconnaissance
    scale = max(1, int(30 / h)) + 1  # plus on est petit, plus on agrandit
    if scale > 1:
        gray = cv2.resize(gray, (gray.shape[1] * scale, gray.shape[0] * scale), interpolation=cv2.INTER_CUBIC)

    # Binarisation
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = "--psm 7 --oem 3"  # psm 7 = ligne unique
    try:
        text = pytesseract.image_to_string(binary, lang=lang, config=config)
        return _clean(text)
    except Exception:
        return ""


def _find_label_above(components: List[Dict], target_idx: int, img: np.ndarray) -> Optional[str]:
    """
    Cherche un composant texte situé juste au-dessus du composant cible.
    Typiquement un Label au-dessus d'un TextInput.
    """
    target = components[target_idx]
    tx, ty, tw = target["x"], target["y"], target["w"]

    best = None
    best_dist = 999

    for i, c in enumerate(components):
        if i == target_idx:
            continue
        cx, cy, cw, ch = c["x"], c["y"], c["w"], c["h"]

        # Le label doit être AU-DESSUS (y < ty) et proche verticalement
        dist_y = ty - (cy + ch)
        if dist_y < 0 or dist_y > 40:
            continue

        # Alignement horizontal : chevauchement ou proximité
        overlap_x = min(tx + tw, cx + cw) - max(tx, cx)
        if overlap_x < min(tw, cw) * 0.2:
            continue

        if dist_y < best_dist:
            best_dist = dist_y
            best = c

    if best and best.get("_text"):
        return best["_text"]
    return None


def enrich_with_text(components: List[Dict[str, Any]], image_path: str) -> List[Dict[str, Any]]:
    """
    Enrichit chaque composant avec le texte OCR lu dans sa zone
    et le label trouvé au-dessus (pour les TextInput).
    """
    img = cv2.imread(image_path)
    if img is None:
        return components

    img_h, img_w = img.shape[:2]

    # Détecter les langues disponibles
    try:
        langs = pytesseract.get_languages()
        lang = "fra+eng" if "fra" in langs else "eng"
    except Exception:
        lang = "eng"

    # Lire le texte dans chaque zone
    for c in components:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        # Convertir depuis coordonnées 1000px vers pixels réels
        scale = img_w / 1000
        rx = int(x * scale)
        ry = int(y * scale)
        rw = int(w * scale)
        rh = int(h * scale)

        text = _read_zone(img, rx, ry, rw, rh, lang=lang)
        c["_text"] = text if len(text) > 1 else ""

    # Pour les TextInput/TextArea, chercher le label au-dessus
    for i, c in enumerate(components):
        if c.get("typeID") in {"TextInput", "TextArea", "SearchBox", "ComboBox", "CheckBox"}:
            label_text = _find_label_above(components, i, img)
            if label_text:
                c["_label_above"] = label_text

    return components
