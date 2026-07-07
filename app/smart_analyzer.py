"""
Analyse intelligente : OCR tesseract → composants Balsamiq avec bon espacement.
Pattern confirmé fonctionnel : label (GAP=18px) → champ.
"""
import cv2
import numpy as np
import pytesseract
import re
from typing import List, Dict, Any

from .balsamiq_components import MEASURED, DEFAULT_MEASURED

GAP = 18        # espace entre label et champ
FIELD_H = 28    # hauteur standard d'un TextInput
HINT_H = 14     # hauteur d'un texte hint
LABEL_H = 15    # hauteur d'un label standard


def _get_lines(img, scale, min_conf=30):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Tesseract est nettement plus fiable quand le texte fait au moins
    # ~25-30px de hauteur. Sur des screenshots réduits (webapp exportée en
    # petite résolution, ex: 859x664), le texte des labels/petits éléments
    # tombe souvent sous ce seuil et devient illisible ("cre a7" au lieu de
    # "Numéro OFEN..."). On agrandit donc l'image avant OCR si elle est
    # petite, uniquement pour la passe de reconnaissance de texte.
    ocr_scale = 1.0
    img_w_px = gray.shape[1]
    if img_w_px < 1800:
        ocr_scale = min(3.0, 1800 / img_w_px)
    if ocr_scale > 1.01:
        gray = cv2.resize(gray, None, fx=ocr_scale, fy=ocr_scale, interpolation=cv2.INTER_CUBIC)
    total_scale = scale * ocr_scale

    data = pytesseract.image_to_data(
        gray, lang='fra+eng', config='--psm 6 --oem 3',
        output_type=pytesseract.Output.DICT
    )
    lines = {}
    for i, word in enumerate(data['text']):
        word = word.strip()
        if not word or int(data['conf'][i]) < min_conf:
            continue
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        t, l, h, w = data['top'][i], data['left'][i], data['height'][i], data['width'][i]
        if key not in lines:
            lines[key] = {'words': [], 'top': t, 'left': l, 'bottom': t+h, 'right': l+w, 'h': h}
        lines[key]['words'].append(word)
        lines[key]['bottom'] = max(lines[key]['bottom'], t+h)
        lines[key]['right']  = max(lines[key]['right'],  l+w)
        lines[key]['h']      = max(lines[key]['h'], h)

    result = []
    for line in sorted(lines.values(), key=lambda l: l['top']):
        result.append({
            'text': ' '.join(line['words']),
            'x':  int(line['left']   / total_scale),
            'y':  int(line['top']    / total_scale),
            'w':  int((line['right'] - line['left']) / total_scale),
            'h':  int(line['h']      / total_scale),
            'h_px': int(line['h'] / ocr_scale),  # hauteur en pixels réels (image d'origine)
        })
    return result


def _detect_shapes(img, scale):
    """
    Détecte les Image et HRule via OpenCV (formes géométriques, pas de texte).
    Réutilise/adapte les heuristiques d'opencv_analyzer.py (jusqu'ici du code
    mort, jamais branché nulle part).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = img.shape[:2]
    shapes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 10 or h < 2:
            continue
        bbox_area = w * h
        if bbox_area > img_w * img_h * 0.9:
            continue
        ratio = w / h if h > 0 else 1

        # HRule : trait fin et très large (séparateur horizontal). On filtre
        # sur l'aire du rectangle englobant (bbox_area), pas contourArea :
        # pour une ligne quasi-droite, contourArea renvoie ~0 (polygone
        # dégénéré) et la ligne serait rejetée à tort par un seuil d'aire.
        if ratio > 15 and h <= 10:
            shapes.append({
                'x': int(x / scale), 'y': int(y / scale),
                'w': int(w / scale), 'h': int(h / scale), 'kind': 'HRule',
            })
            continue

        if h < 10:
            continue

        # Image : bloc rectangulaire large, peu de détails internes (faible
        # densité de contours) -> probablement une photo/placeholder, pas du
        # texte ni un bouton
        if 0.4 <= ratio <= 2.5 and bbox_area > 8000:
            area = cv2.contourArea(cnt)
            if area < 400:
                continue
            roi = img[y:y + h, x:x + w]
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
            roi_edges = cv2.Canny(roi_gray, 50, 150)
            density = np.count_nonzero(roi_edges) / bbox_area
            if density < 0.03:
                shapes.append({
                    'x': int(x / scale), 'y': int(y / scale),
                    'w': int(w / scale), 'h': int(h / scale), 'kind': 'Image',
                })
    return shapes


def _has_dropdown_marker(text):
    """Détecte un marqueur de liste déroulante (▼ ▾ ⌄ v en fin de texte)."""
    text = text.strip()
    return bool(re.search(r'[▼▾⌄∨]\s*$', text)) or bool(re.match(r'^.{1,40}\s+v$', text, re.IGNORECASE))

def _detect_inputs(img, scale):
    """Détecte les zones de saisie via OpenCV."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 20, 80)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (4, 2))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_h, img_w = img.shape[:2]
    zones = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        ratio = w / h if h > 0 else 0
        if ratio < 2 or h < 8 or w * h < 1500:
            continue
        if w < img_w * 0.04:
            continue
        zones.append({
            'x': int(x / scale), 'y': int(y / scale),
            'w': int(w / scale), 'h': int(h / scale),
            'area': w * h
        })

    # Dédupliquer
    zones.sort(key=lambda z: z['area'], reverse=True)
    clean = []
    for z in zones:
        dominated = any(
            max(0, min(z['x']+z['w'], c['x']+c['w']) - max(z['x'], c['x'])) *
            max(0, min(z['y']+z['h'], c['y']+c['h']) - max(z['y'], c['y']))
            > 0.5 * min(z['w']*z['h'], c['w']*c['h'])
            for c in clean
        )
        if not dominated:
            clean.append(z)
    return clean


def _label_above(line, inputs, max_dist=40):
    """Vérifie si une ligne de texte est un label au-dessus d'un champ."""
    for inp in inputs:
        dist = inp['y'] - (line['y'] + line['h'])
        if 0 < dist < max_dist:
            overlap = min(line['x']+line['w'], inp['x']+inp['w']) - max(line['x'], inp['x'])
            if overlap > min(line['w'], inp['w']) * 0.2:
                return True
    return False


def _is_hint(line):
    """Détecte un texte gris d'aide (hint) sous un label."""
    text = line['text'].lower()
    return (line['h_px'] < 12 and (
        'exemple' in text or 'ex :' in text or 'préfixer' in text or
        'merci' in text or 'saisir' in text or 'facultatif' in text.lower()
    ))


def _make_ctrl(id_, tid, x, y, w=None, h=None, props=None):
    mw, mh = MEASURED.get(tid, (w or 100, h or 20))
    c = {
        "ID": str(id_),
        "typeID": tid,
        "zOrder": str(id_),
        "measuredW": str(mw),
        "measuredH": str(mh),
        "x": str(x),
        "y": str(y),
    }
    if tid in {"TextInput","TextArea","ButtonBar","Rectangle","FieldSet","Image","HRule","ComboBox"}:
        if w: c["w"] = str(w)
        if h and h != mh: c["h"] = str(h)
    if props:
        c["properties"] = props
    return c


def smart_analyze(image_path: str) -> List[Dict[str, Any]]:
    img = cv2.imread(image_path)
    if img is None:
        return []

    img_h, img_w = img.shape[:2]
    scale = img_w / 1000

    lines  = _get_lines(img, scale)
    inputs = _detect_inputs(img, scale)

    controls = []
    id_ = 0
    used_inputs = set()

    for line in lines:
        text = line['text']
        lx, ly, lw, lh = line['x'], line['y'], line['w'], line['h']
        h_px = line['h_px']

        # ── Classifier la ligne ──────────────────────────────────────────────

        # ComboBox : ligne se terminant par un marqueur de liste déroulante
        # (ex: "Pays ▼", "Ville v") -> c'est la valeur affichée DANS le
        # ComboBox, pas un label au-dessus d'un champ
        if _has_dropdown_marker(text) and h_px < 30:
            controls.append(_make_ctrl(id_, "ComboBox", lx, ly, w=max(lw, 140), props={"text": text}))
            id_ += 1
            continue

        # Checkbox — symboles unicode OU notation Balsamiq officielle [x] / [ ]
        if text.startswith(('☑', '✓', '☐', '□', '✔')) or re.match(r'^[©@®]\s', text):
            checked = text[0] in ('☑','✓','✔','©','@')
            label = re.sub(r'^[☑✓☐□✔©@®]\s*', '', text).strip()
            controls.append(_make_ctrl(id_, "CheckBox", lx, ly, props={"text": label, "selected": checked}))
            id_ += 1
            continue
        m_cb = re.match(r'^\[\s*([xX]?)\s*\]\s*(.*)$', text)
        if m_cb:
            controls.append(_make_ctrl(id_, "CheckBox", lx, ly,
                props={"text": m_cb.group(2).strip(), "selected": bool(m_cb.group(1))}))
            id_ += 1
            continue

        # RadioButton — symboles unicode OU notation Balsamiq officielle (o) / ()
        if re.match(r'^[○●◉O©]\s', text) or '○' in text[:3] or '●' in text[:3]:
            parts = re.split(r'\s+[○●◉O©]\s+', text)
            for j, part in enumerate(parts):
                part = re.sub(r'^[○●◉O©]\s*', '', part).strip()
                if part:
                    selected = j == 0 and text[0] in ('●','◉')
                    controls.append(_make_ctrl(id_, "RadioButton", lx + j*200, ly, props={"text": part, "selected": selected}))
                    id_ += 1
            continue
        m_rb = re.match(r'^\(\s*([oO]?)\s*\)\s*(.*)$', text)
        if m_rb:
            controls.append(_make_ctrl(id_, "RadioButton", lx, ly,
                props={"text": m_rb.group(2).strip(), "selected": bool(m_rb.group(1))}))
            id_ += 1
            continue

        # Hint (texte gris d'aide) — Label petit
        if _is_hint(line):
            controls.append(_make_ctrl(id_, "Label", lx, ly, props={"text": text, "size": "10", "color": "9868950"}))
            id_ += 1
            continue

        # Grand titre
        if h_px >= 22:
            controls.append(_make_ctrl(id_, "Title", lx, ly, props={"text": text, "size": str(int(h_px * 0.8))}))
            id_ += 1

        # Sous-titre / section
        elif h_px >= 14:
            controls.append(_make_ctrl(id_, "SubTitle", lx, ly, props={"text": text}))
            id_ += 1

        # Label au-dessus d'un champ
        elif _label_above(line, inputs):
            controls.append(_make_ctrl(id_, "Label", lx, ly, props={"text": text}))
            id_ += 1

            # Trouver le champ associé
            best_inp = None
            best_dist = 999
            for k, inp in enumerate(inputs):
                dist = inp['y'] - (ly + lh)
                if 0 < dist < 40:
                    overlap = min(lx+lw, inp['x']+inp['w']) - max(lx, inp['x'])
                    if overlap > 0 and dist < best_dist:
                        best_dist = dist
                        best_inp = (k, inp)

            if best_inp and best_inp[0] not in used_inputs:
                k, inp = best_inp
                used_inputs.add(k)
                tid = "TextArea" if inp['h'] > 50 else "TextInput"
                controls.append(_make_ctrl(id_, tid, inp['x'], inp['y'], w=inp['w'], h=inp['h']))
                id_ += 1

        # Lien
        elif h_px <= 10 and ('>' in text or 'http' in text.lower() or 'www' in text.lower() or
              any(w in text.lower() for w in ['envoyer', 'lien', 'reprendre', 'vd.ch'])):
            controls.append(_make_ctrl(id_, "Link", lx, ly, props={"text": text}))
            id_ += 1

        # Label générique
        else:
            controls.append(_make_ctrl(id_, "Label", lx, ly, props={"text": text}))
            id_ += 1

    # Aide : une zone chevauche-t-elle un contrôle déjà placé ? (évite les
    # doublons : _detect_inputs() capte parfois le contour d'une simple
    # ligne de texte -- titre, sous-titre, breadcrumb -- comme si c'était
    # un vrai champ de saisie, ce qui créait un TextInput fantôme par-dessus
    # chaque Title/SubTitle/Label déjà détecté par l'OCR)
    def _overlaps_existing(x, y, w, h, min_ratio=0.35):
        for c in controls:
            cx, cy = int(c['x']), int(c['y'])
            cw = int(c.get('w', c['measuredW']))
            ch = int(c.get('h', c['measuredH']))
            ix = max(0, min(x + w, cx + cw) - max(x, cx))
            iy = max(0, min(y + h, cy + ch) - max(y, cy))
            if ix * iy > min_ratio * min(w * h, cw * ch):
                return True
        return False

    # Champs non encore associés -- on ignore ceux qui chevauchent déjà un
    # Title/SubTitle/Label/Link (contour de texte confondu avec un champ)
    for k, inp in enumerate(inputs):
        if k in used_inputs:
            continue
        if _overlaps_existing(inp['x'], inp['y'], inp['w'], inp['h']):
            continue
        tid = "TextArea" if inp['h'] > 50 else "TextInput"
        controls.append(_make_ctrl(id_, tid, inp['x'], inp['y'], w=inp['w'], h=inp['h']))
        id_ += 1

    # Image / HRule : formes géométriques sans texte, ignorées par l'OCR
    for shape in _detect_shapes(img, scale):
        if _overlaps_existing(shape['x'], shape['y'], shape['w'], shape['h']):
            continue
        controls.append(_make_ctrl(id_, shape['kind'], shape['x'], shape['y'], w=shape['w'], h=shape['h']))
        id_ += 1

    # Boutons navigation (Précédent/Suivant)
    for line in lines:
        text = line['text']
        if any(w in text for w in ['Précédent','Suivant','Suivante','Submit','Envoyer','Valider','Annuler']):
            # Déjà traité comme Label, le remplacer par Button
            for c in controls:
                if c.get('properties',{}).get('text') == text and c['typeID'] == 'Label':
                    c['typeID'] = 'Button'
                    c.pop('w', None)
                    c.pop('h', None)
                    mw, mh = MEASURED['Button']
                    c['measuredW'] = str(mw)
                    c['measuredH'] = str(mh)

    controls.sort(key=lambda c: (int(c['y']), int(c['x'])))

    # Enrichir pour l'affichage UI
    TYPE_LABELS = {
        "Title": "🔤 Titre", "SubTitle": "🔤 Sous-titre", "Label": "🏷️ Label",
        "Link": "🔗 Lien", "TextInput": "✏️ Champ texte", "TextArea": "📄 Zone texte",
        "Button": "🔘 Bouton", "ButtonBar": "🔘 Barre boutons",
        "CheckBox": "☑️ Case à cocher", "RadioButton": "🔘 Radio",
        "ComboBox": "🔽 Liste déroulante", "Image": "🖼️ Image", "HRule": "— Séparateur",
    }
    result = []
    for c in controls:
        tid = c['typeID']
        text = c.get('properties', {}).get('text', '')
        result.append({
            **c,
            "label": TYPE_LABELS.get(tid, f"▭ {tid}"),
            "description": text[:60] if text else '',
            "x": int(c['x']), "y": int(c['y']),
            "w": int(c.get('w', c['measuredW'])),
            "h": int(c.get('h', c['measuredH'])),
            "measuredW": int(c['measuredW']),
            "measuredH": int(c['measuredH']),
        })

    return result
