"""
Lit le texte avec tesseract et l'associe aux composants OpenCV.
Les composants sont en coordonnées base-1000px (largeur = 1000, hauteur proportionnelle).
"""
import cv2
import pytesseract
from typing import List, Dict, Any


def enrich_with_text(components: List[Dict[str, Any]], image_path: str) -> List[Dict[str, Any]]:
    img = cv2.imread(image_path)
    if img is None:
        return components

    img_h, img_w = img.shape[:2]
    # OpenCV travaille avec largeur = 1000px, hauteur proportionnelle
    # Donc scale = img_w / 1000 pour X ET Y
    scale = img_w / 1000

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Extraction mot par mot
    data = pytesseract.image_to_data(
        gray, lang='fra+eng',
        config='--psm 6 --oem 3',
        output_type=pytesseract.Output.DICT
    )

    # Mots en coordonnées base-1000
    words = []
    for i, word in enumerate(data['text']):
        word = word.strip()
        if not word or int(data['conf'][i]) < 35:
            continue
        words.append({
            'text': word,
            'x':  data['left'][i]  / scale,
            'y':  data['top'][i]   / scale,
            'w':  data['width'][i] / scale,
            'h':  data['height'][i]/ scale,
            'cx': (data['left'][i] + data['width'][i]/2)  / scale,
            'cy': (data['top'][i]  + data['height'][i]/2) / scale,
        })

    def words_in_zone(x, y, w, h):
        out = [wd for wd in words
               if x - 3 <= wd['cx'] <= x + w + 3
               and y - 3 <= wd['cy'] <= y + h + 3]
        out.sort(key=lambda wd: (round(wd['y']/5)*5, wd['x']))
        return out

    def words_above(x, y, w, max_dist=40):
        out = []
        for wd in words:
            # Le mot doit être au-dessus de la zone (cy < y) et pas trop loin
            dist = y - wd['cy']
            if not (2 < dist < max_dist):
                continue
            # Aligné horizontalement avec la zone
            if wd['cx'] < x - 10 or wd['cx'] > x + w + 10:
                continue
            out.append(wd)
        out.sort(key=lambda wd: (round(wd['y']/5)*5, wd['x']))
        return out

    for c in components:
        cx, cy, cw, ch = c['x'], c['y'], c['w'], c['h']
        tid = c.get('typeID', 'Rectangle')

        in_zone = words_in_zone(cx, cy, cw, ch)
        above   = words_above(cx, cy, cw)

        zone_text  = ' '.join(wd['text'] for wd in in_zone).strip()
        label_text = ' '.join(wd['text'] for wd in above).strip()

        c['_text']        = zone_text
        c['_label_above'] = label_text

        # Description selon le type
        if tid in {'TextInput', 'TextArea', 'SearchBox', 'ComboBox'}:
            c['description'] = label_text or zone_text or ''
        elif tid in {'Button', 'PointyButton', 'ButtonBar'}:
            c['description'] = zone_text or ''
        else:
            c['description'] = zone_text or label_text or ''

    return components
