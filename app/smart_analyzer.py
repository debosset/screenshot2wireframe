"""
Analyse intelligente : OCR tesseract → composants Balsamiq avec bon espacement.
Pattern confirmé fonctionnel : label (GAP=18px) → champ.
"""
import cv2
import pytesseract
import re
from typing import List, Dict, Any

GAP = 18        # espace entre label et champ
FIELD_H = 28    # hauteur standard d'un TextInput
HINT_H = 14     # hauteur d'un texte hint
LABEL_H = 15    # hauteur d'un label standard

# Tailles measuredW/H par défaut Balsamiq
MEASURED = {
    "Title":       (300, 30),
    "SubTitle":    (250, 24),
    "Label":       (100, 17),
    "Link":        (150, 17),
    "TextInput":   (79,  27),
    "TextArea":    (200, 100),
    "Button":      (61,  27),
    "ButtonBar":   (159, 27),
    "CheckBox":    (100, 23),
    "RadioButton": (97,  23),
    "HRule":       (100, 10),
}


def _get_lines(img, scale, min_conf=30):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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
            'x':  int(line['left']   / scale),
            'y':  int(line['top']    / scale),
            'w':  int((line['right'] - line['left']) / scale),
            'h':  int(line['h']      / scale),
            'h_px': line['h'],  # hauteur en pixels réels
        })
    return result


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
    if tid in {"TextInput","TextArea","ButtonBar","Rectangle","FieldSet","Image","HRule"}:
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

        # Checkbox
        if text.startswith(('☑', '✓', '☐', '□', '✔')) or re.match(r'^[©@®]\s', text):
            checked = text[0] in ('☑','✓','✔','©','@')
            label = re.sub(r'^[☑✓☐□✔©@®]\s*', '', text).strip()
            controls.append(_make_ctrl(id_, "CheckBox", lx, ly, props={"text": label, "selected": checked}))
            id_ += 1
            continue

        # RadioButton
        if re.match(r'^[○●◉O©]\s', text) or '○' in text[:3] or '●' in text[:3]:
            parts = re.split(r'\s+[○●◉O©]\s+', text)
            for j, part in enumerate(parts):
                part = re.sub(r'^[○●◉O©]\s*', '', part).strip()
                if part:
                    selected = j == 0 and text[0] in ('●','◉')
                    controls.append(_make_ctrl(id_, "RadioButton", lx + j*200, ly, props={"text": part, "selected": selected}))
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

    # Champs non encore associés
    for k, inp in enumerate(inputs):
        if k not in used_inputs:
            tid = "TextArea" if inp['h'] > 50 else "TextInput"
            controls.append(_make_ctrl(id_, tid, inp['x'], inp['y'], w=inp['w'], h=inp['h']))
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
