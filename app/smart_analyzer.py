"""
Analyse intelligente : combine OCR (tesseract) + détection de zones (OpenCV).
Reconstruit les vrais composants UI : titres, labels, champs, boutons.
"""
import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Any


def _get_lines(img: np.ndarray, scale: float, min_conf: int = 35) -> List[Dict]:
    """Extrait les lignes de texte avec positions en base-1000px."""
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
            lines[key] = {'words': [], 'top': t, 'left': l, 'bottom': t+h, 'right': l+w, 'height': h}
        lines[key]['words'].append(word)
        lines[key]['bottom'] = max(lines[key]['bottom'], t+h)
        lines[key]['right']  = max(lines[key]['right'],  l+w)
        lines[key]['height'] = max(lines[key]['height'], h)

    result = []
    for line in sorted(lines.values(), key=lambda l: l['top']):
        text = ' '.join(line['words'])
        result.append({
            'text': text,
            'x': int(line['left']   / scale),
            'y': int(line['top']    / scale),
            'w': int((line['right'] - line['left']) / scale),
            'h': int(line['height'] / scale),
            'font_size': line['height'],  # en pixels réels
        })
    return result


def _get_input_zones(img: np.ndarray, scale: float) -> List[Dict]:
    """Détecte les zones de saisie (champs gris encadrés)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Détecter les rectangles clairs avec bordure (champs input typiques)
    blurred = cv2.GaussianBlur(gray, (3,3), 0)
    edges = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    dilated = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    zones = []
    img_h, img_w = img.shape[:2]
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        ratio = w / h if h > 0 else 0

        # Champ input : large et plat, surface correcte
        if ratio < 2 or h < 10 or area < 2000:
            continue
        if w < img_w * 0.05:  # trop petit
            continue

        # Convertir en base-1000px
        zones.append({
            'x': int(x / scale),
            'y': int(y / scale),
            'w': int(w / scale),
            'h': int(h / scale),
        })

    # Dédupliquer les zones qui se chevauchent trop
    zones.sort(key=lambda z: z['area'] if 'area' in z else z['w']*z['h'], reverse=True)
    clean = []
    for z in zones:
        dominated = False
        for c in clean:
            ix = max(0, min(z['x']+z['w'], c['x']+c['w']) - max(z['x'], c['x']))
            iy = max(0, min(z['y']+z['h'], c['y']+c['h']) - max(z['y'], c['y']))
            inter = ix * iy
            smaller = min(z['w']*z['h'], c['w']*c['h'])
            if smaller > 0 and inter/smaller > 0.5:
                dominated = True
                break
        if not dominated:
            clean.append(z)

    return clean


def smart_analyze(image_path: str) -> List[Dict[str, Any]]:
    """
    Analyse intelligente combinant OCR + OpenCV.
    Retourne une liste de composants avec leurs textes.
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    img_h, img_w = img.shape[:2]
    scale = img_w / 1000

    # 1. Lire toutes les lignes de texte
    lines = _get_lines(img, scale)

    components = []

    for line in lines:
        text = line['text']
        x, y, w, h = line['x'], line['y'], line['w'], line['h']
        font_px = line['font_size']

        # Classifier selon la taille du texte et la position
        if font_px >= 20:
            # Grand texte = titre
            tid = "Title"
            label = f"🔤 Titre"
        elif font_px >= 14:
            # Texte moyen = sous-titre ou section
            tid = "SubTitle"
            label = f"🔤 Sous-titre"
        else:
            # Petit texte = label ou paragraphe
            # Heuristique : si c'est suivi d'un champ en-dessous → Label
            tid = "Label"
            label = f"🏷️ Label"

        components.append({
            'typeID': tid,
            'label': label,
            'description': text,
            'x': x, 'y': y, 'w': max(w, 50), 'h': max(h, 15),
            'measuredW': max(w, 50), 'measuredH': max(h, 15),
            '_text': text,
        })

    # 2. Détecter les champs de saisie (zones rectangulaires)
    input_zones = _get_input_zones(img, scale)
    for zone in input_zones:
        # Chercher le label juste au-dessus
        label_text = ''
        best_dist = 999
        for line in lines:
            dist = zone['y'] - (line['y'] + line['h'])
            if 0 < dist < 40:
                # Aligné horizontalement
                if line['x'] < zone['x'] + zone['w'] and line['x'] + line['w'] > zone['x']:
                    if dist < best_dist:
                        best_dist = dist
                        label_text = line['text']

        # Texte dans la zone (valeur pré-remplie)
        zone_text = ''
        for line in lines:
            lx, ly, lw, lh = line['x'], line['y'], line['w'], line['h']
            if (zone['x'] <= lx + lw/2 <= zone['x'] + zone['w'] and
                zone['y'] <= ly + lh/2 <= zone['y'] + zone['h']):
                zone_text = line['text']
                break

        # Déterminer le typeID selon la hauteur
        if zone['h'] > 60:
            tid = "TextArea"
            emoji = "📄"
        elif zone['w'] > 400:
            tid = "TextInput"
            emoji = "✏️"
        elif zone['h'] < 30 and zone['w'] < 200:
            tid = "Button"
            emoji = "🔘"
        else:
            tid = "TextInput"
            emoji = "✏️"

        components.append({
            'typeID': tid,
            'label': f"{emoji} {'Champ texte' if tid=='TextInput' else tid}",
            'description': label_text or zone_text or '',
            'x': zone['x'], 'y': zone['y'],
            'w': zone['w'], 'h': zone['h'],
            'measuredW': zone['w'], 'measuredH': zone['h'],
            '_text': zone_text,
            '_label_above': label_text,
        })

    # Trier par position Y puis X
    components.sort(key=lambda c: (c['y'], c['x']))

    # Dédupliquer : supprimer les Labels qui sont couverts par un TextInput
    final = []
    input_zones_set = [(c['x'], c['y'], c['w'], c['h']) for c in components if c['typeID'] in {'TextInput','TextArea'}]
    for c in components:
        if c['typeID'] == 'Label':
            # Vérifier si ce label est aussi le texte dans un champ
            covered = False
            for ix, iy, iw, ih in input_zones_set:
                if (ix <= c['x'] <= ix+iw and iy <= c['y'] <= iy+ih):
                    covered = True
                    break
            if covered:
                continue
        final.append(c)

    return final
