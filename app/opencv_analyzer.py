"""
Analyse un screenshot avec OpenCV et retourne une liste de composants Balsamiq.
Aucun token IA consommé — tout se passe en local.
"""
import cv2
import numpy as np
from typing import List, Dict, Any


# ── Heuristiques de classification ──────────────────────────────────────────

def _classify(x: int, y: int, w: int, h: int, roi: np.ndarray, img_w: int, img_h: int) -> str:
    ratio = w / h if h > 0 else 1
    area = w * h
    rel_y = y / img_h  # position verticale relative

    # Barre de navigation (pleine largeur, haut de page)
    if rel_y < 0.12 and w > img_w * 0.7 and h < 80:
        return "com.balsamiq.mockups::NavigationBar"

    # Pied de page (pleine largeur, bas de page)
    if rel_y > 0.88 and w > img_w * 0.7:
        return "com.balsamiq.mockups::Rectangle"

    # Bouton (ratio large, petite hauteur)
    if 2.0 <= ratio <= 6.0 and 20 <= h <= 55 and w <= 300:
        return "com.balsamiq.mockups::Button"

    # Champ de saisie (ratio très large, très petite hauteur)
    if ratio > 4.0 and 18 <= h <= 45:
        return "com.balsamiq.mockups::TextInput"

    # Checkbox (petit carré)
    if 0.7 <= ratio <= 1.3 and area < 900:
        return "com.balsamiq.mockups::CheckBox"

    # Image / placeholder (ratio proche de 1, grande surface)
    if 0.5 <= ratio <= 2.0 and area > 10000:
        # Détecte si la zone contient peu de contours (= image vide / placeholder)
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        edges = cv2.Canny(gray_roi, 50, 150)
        density = np.count_nonzero(edges) / area
        if density < 0.02:
            return "com.balsamiq.mockups::Image"

    # Label / texte (très plat)
    if ratio > 8.0 and h < 30:
        return "com.balsamiq.mockups::Label"

    # Rectangle générique
    return "com.balsamiq.mockups::Rectangle"


def _merge_overlapping(rects: List[tuple], overlap_thresh: float = 0.3) -> List[tuple]:
    """Fusionne les rectangles qui se chevauchent trop (bruit OpenCV)."""
    if not rects:
        return []
    rects = sorted(rects, key=lambda r: r[2] * r[3], reverse=True)
    keep = []
    for r in rects:
        x1, y1, w1, h1 = r
        dominated = False
        for kx, ky, kw, kh in keep:
            ix = max(0, min(x1 + w1, kx + kw) - max(x1, kx))
            iy = max(0, min(y1 + h1, ky + kh) - max(y1, ky))
            inter = ix * iy
            union = w1 * h1 + kw * kh - inter
            if union > 0 and inter / union > overlap_thresh:
                dominated = True
                break
        if not dominated:
            keep.append(r)
    return keep


def analyze_screenshot(image_path: str) -> List[Dict[str, Any]]:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Impossible de lire l'image : {image_path}")

    img_h, img_w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── Prétraitement ────────────────────────────────────────────────────────
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 30, 100)

    # Dilatation pour connecter les contours proches
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # ── Détection des contours ───────────────────────────────────────────────
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    MIN_AREA = 400          # px² — ignore le bruit
    MAX_AREA = img_w * img_h * 0.95  # ignore le cadre entier
    MIN_SIDE = 10           # côté minimum

    raw_rects = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_AREA or area > MAX_AREA:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < MIN_SIDE or h < MIN_SIDE:
            continue
        raw_rects.append((x, y, w, h))

    # Suppression des doublons / chevauchements
    clean_rects = _merge_overlapping(raw_rects, overlap_thresh=0.4)

    # ── Mise à l'échelle Balsamiq (coordonnées en px, base 1000px de large) ─
    scale = 1000 / img_w

    components: List[Dict[str, Any]] = []
    for x, y, w, h in clean_rects:
        roi = img[y : y + h, x : x + w]
        kind = _classify(x, y, w, h, roi, img_w, img_h)

        bx = round(x * scale)
        by = round(y * scale)
        bw = round(w * scale)
        bh = round(h * scale)

        components.append({
            "type": kind,
            "x": bx,
            "y": by,
            "w": bw,
            "h": bh,
            "measuredW": bw,
            "measuredH": bh,
        })

    # Tri spatial (haut-gauche → bas-droite)
    components.sort(key=lambda c: (c["y"], c["x"]))
    return components
