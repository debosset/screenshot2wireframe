import base64, json, re, uuid, io, time
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq, InternalServerError, RateLimitError
from PIL import Image

# Étape 1 : Groq décrit les éléments en texte simple (peu de tokens)
PROMPT_DESCRIBE = """Analyze this web form screenshot. List each UI element on ONE line using this format:
TYPE|TEXT|X|Y|W|H

Types: Title, SubTitle, Label, TextInput, TextArea, Button, CheckBox, RadioButton, NavBar, Link, HRule
- X,Y = position (0-1000 horizontal, 0-800 vertical)
- W = width (for TextInput/TextArea only)
- H = height (optional)

Example output:
Title|Identification du demandeur|100|20|600|
Label|Nom|100|80||
TextInput|de Bosset|100|95|500|
Label|Prénom|600|80||
TextInput|Adrien|600|95|300|
Button|Suivant|700|400||

List ALL visible elements. One element per line. Nothing else."""


def _prepare_image(image_path: str, max_size: int = 768) -> tuple:
    img = Image.open(image_path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    w, h = img.size
    if w > max_size or h > max_size:
        ratio = min(max_size/w, max_size/h)
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=75, optimize=True)
    buf.seek(0)
    return base64.standard_b64encode(buf.read()).decode("utf-8"), "image/jpeg"


MEASURED_DEFAULTS = {
    "Title":       (300, 30), "SubTitle":    (250, 24), "Label":       (100, 17),
    "Link":        (150, 17), "TextInput":   (79,  27), "TextArea":    (200, 100),
    "Button":      (61,  27), "ButtonBar":   (159, 27), "CheckBox":    (100, 23),
    "RadioButton": (97,  23), "HRule":       (200, 10), "NavBar":      (300, 30),
    "Image":       (200, 150),"Rectangle":   (200, 150),
}


def _parse_lines_to_controls(text: str) -> List[Dict]:
    """Convertit le texte ligne par ligne en contrôles Balsamiq."""
    controls = []
    id_ = 0
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 2:
            continue

        tid = parts[0].strip()
        label_text = parts[1].strip() if len(parts) > 1 else ""
        
        # Nettoyer le typeID
        tid_map = {
            'title': 'Title', 'subtitle': 'SubTitle', 'label': 'Label',
            'textinput': 'TextInput', 'input': 'TextInput', 'text': 'TextInput',
            'textarea': 'TextArea', 'button': 'Button', 'checkbox': 'CheckBox',
            'check': 'CheckBox', 'radio': 'RadioButton', 'radiobutton': 'RadioButton',
            'navbar': 'NavBar', 'nav': 'NavBar', 'link': 'Link', 'hrule': 'HRule',
            'image': 'Image', 'rectangle': 'Rectangle',
        }
        tid = tid_map.get(tid.lower(), tid)
        if tid not in MEASURED_DEFAULTS:
            tid = 'Label'

        try:
            x = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 100
            y = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 100
            w = int(parts[4].strip()) if len(parts) > 4 and parts[4].strip() else None
            h = int(parts[5].strip()) if len(parts) > 5 and parts[5].strip() else None
        except (ValueError, IndexError):
            x, y, w, h = 100, 100 + id_ * 30, None, None

        mw, mh = MEASURED_DEFAULTS.get(tid, (100, 20))

        ctrl = {
            "ID": str(id_),
            "typeID": tid,
            "zOrder": str(id_),
            "measuredW": str(mw),
            "measuredH": str(mh),
            "x": str(x),
            "y": str(y),
        }

        # w/h seulement si différent des defaults
        if tid in {"TextInput", "TextArea", "NavBar", "HRule", "Rectangle", "Image"}:
            if w: ctrl["w"] = str(w)
            if h and h != mh: ctrl["h"] = str(h)

        # Properties avec le texte
        if label_text and tid not in {"TextInput", "TextArea", "HRule", "Image", "Rectangle"}:
            ctrl["properties"] = {"text": label_text}

        controls.append(ctrl)
        id_ += 1

    return controls


def analyze_with_groq(image_path: str, api_key: str, project_id: str = "0:1") -> Dict[str, Any]:
    b64, mime = _prepare_image(image_path)
    client = Groq(api_key=api_key)

    last_error = None
    for attempt in range(3):
        try:
            # Groq décrit en texte — pas de JSON à parser !
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": PROMPT_DESCRIBE}
                ]}],
                temperature=0.0,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content
            
            # Convertir le texte en contrôles Balsamiq
            controls = _parse_lines_to_controls(raw)
            
            if not controls:
                raise ValueError("Aucun composant détecté")

            # Calculer les dimensions
            max_y = max(int(c["y"]) + MEASURED_DEFAULTS.get(c["typeID"], (100,30))[1] for c in controls)
            mockup_h = str(max(max_y + 50, 400))

            return {
                "mockup": {
                    "controls": {"control": controls},
                    "attributes": {"name": "New Wireframe 1", "order": 938428.5264654435, "parentID": None, "notes": None},
                    "branchID": "Master",
                    "resourceID": str(uuid.uuid4()).upper(),
                    "mockupH": mockup_h,
                    "mockupW": "1000",
                    "measuredW": "1000",
                    "measuredH": mockup_h,
                    "version": "1.0",
                    "calloutsOffset": {"x": 0, "y": 0},
                },
                "groupOffset": {"x": 0, "y": 0},
                "dependencies": [],
                "projectID": project_id,
                "_raw_description": raw,  # pour debug
            }

        except (InternalServerError, RateLimitError) as e:
            last_error = e
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            last_error = e
            break

    raise ValueError(f"Erreur Groq: {last_error}")


def extract_components(mockup_json: Dict) -> List[Dict]:
    TYPE_LABELS = {
        "Title":"🔤 Titre", "SubTitle":"🔤 Sous-titre", "Label":"🏷️ Label",
        "Link":"🔗 Lien", "TextInput":"✏️ Champ texte", "TextArea":"📄 Zone texte",
        "Button":"🔘 Bouton", "ButtonBar":"🔘 Barre boutons",
        "CheckBox":"☑️ Case à cocher", "RadioButton":"🔘 Radio",
        "NavBar":"🧭 Navigation", "Image":"🖼️ Image",
        "Rectangle":"▭ Rectangle", "HRule":"— Séparateur",
    }
    controls = mockup_json.get("mockup",{}).get("controls",{}).get("control",[])
    result = []
    for c in controls:
        tid = c.get("typeID","Rectangle")
        props = c.get("properties",{})
        text = props.get("text","") if isinstance(props,dict) else ""
        result.append({
            **c,
            "label": TYPE_LABELS.get(tid, f"▭ {tid}"),
            "description": str(text)[:60] if text else "",
            "x": int(c.get("x",0)), "y": int(c.get("y",0)),
            "w": int(c.get("w", c.get("measuredW",100))),
            "h": int(c.get("h", c.get("measuredH",20))),
            "measuredW": int(c.get("measuredW",100)),
            "measuredH": int(c.get("measuredH",20)),
        })
    return result
