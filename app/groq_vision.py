import base64, json, re, uuid, io, time
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq, InternalServerError, RateLimitError
from PIL import Image

# Groq identifie les éléments et leur texte — on gère le layout nous-mêmes
PROMPT = """Analyze this web form screenshot. For each UI element, write ONE line:
TYPE|TEXT

Rules:
- List elements from TOP to BOTTOM as they appear
- Types: NavBar, Title, SubTitle, Label, TextInput, TextArea, Button, CheckBox, RadioButton, Link, HRule
- TEXT = the visible text label or placeholder
- For TextInput: TEXT = the label above the field (not the value inside)
- For CheckBox/RadioButton: TEXT = the option text
- Keep it simple, one line per element

Example:
NavBar|ÉTAT DE VAUD
Title|Identification du demandeur
SubTitle|Page 2 sur 5
Label|Je fais la demande en tant que
RadioButton|Employeur
RadioButton|Mandataire
SubTitle|Identification de l'employeur
Label|Nom
TextInput|Nom
Label|Prénom
TextInput|Prénom
Button|Suivant"""


MEASURED = {
    "NavBar":      (1000, 40), "Title":       (600, 32), "SubTitle":    (500, 26),
    "Label":       (300, 17),  "Link":        (300, 17), "TextInput":   (79,  27),
    "TextArea":    (200, 80),  "Button":      (61,  27), "ButtonBar":   (159, 27),
    "CheckBox":    (200, 23),  "RadioButton": (200, 23), "HRule":       (800, 5),
}

# Espacement vertical entre chaque type d'élément
SPACING = {
    "NavBar": 20,    "Title": 20,    "SubTitle": 24,
    "Label": 4,      "TextInput": 20, "TextArea": 20,
    "CheckBox": 8,   "RadioButton": 8, "Button": 10,
    "Link": 16,      "HRule": 12,
}

# Largeur par défaut des champs selon leur type
INPUT_WIDTH = 650


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


def _parse_and_layout(text: str) -> List[Dict]:
    """Parse la liste TYPE|TEXT et calcule un layout propre."""
    lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|', 1)
        tid_raw = parts[0].strip()
        label = parts[1].strip() if len(parts) > 1 else ""

        # Normaliser le type
        tid_map = {
            'navbar': 'NavBar', 'nav': 'NavBar',
            'title': 'Title', 'subtitle': 'SubTitle', 'sub': 'SubTitle',
            'label': 'Label', 'text': 'Label',
            'textinput': 'TextInput', 'input': 'TextInput', 'field': 'TextInput',
            'textarea': 'TextArea', 'area': 'TextArea',
            'button': 'Button', 'btn': 'Button',
            'checkbox': 'CheckBox', 'check': 'CheckBox',
            'radiobutton': 'RadioButton', 'radio': 'RadioButton',
            'link': 'Link', 'hrule': 'HRule', 'hr': 'HRule',
        }
        tid = tid_map.get(tid_raw.lower(), tid_raw)
        if tid not in MEASURED:
            tid = 'Label'

        lines.append((tid, label))

    # Calculer le layout vertical
    controls = []
    id_ = 0
    y = 30
    LEFT = 100
    radio_x = LEFT  # Pour aligner les RadioButton côte à côte

    i = 0
    while i < len(lines):
        tid, label = lines[i]
        mw, mh = MEASURED.get(tid, (200, 20))

        # RadioButton côte à côte
        if tid == 'RadioButton':
            radio_group = []
            while i < len(lines) and lines[i][0] == 'RadioButton':
                radio_group.append(lines[i][1])
                i += 1
            rx = LEFT
            for opt in radio_group:
                ctrl = {
                    "ID": str(id_), "typeID": "RadioButton", "zOrder": str(id_),
                    "measuredW": "200", "measuredH": "23",
                    "x": str(rx), "y": str(y),
                    "properties": {"text": opt}
                }
                controls.append(ctrl)
                id_ += 1
                rx += 220
            y += 23 + SPACING.get('RadioButton', 8)
            continue

        # CheckBox — empilées verticalement
        if tid == 'CheckBox':
            ctrl = {
                "ID": str(id_), "typeID": "CheckBox", "zOrder": str(id_),
                "measuredW": "300", "measuredH": "23",
                "x": str(LEFT), "y": str(y),
                "properties": {"text": label}
            }
            controls.append(ctrl)
            id_ += 1
            y += 23 + SPACING.get('CheckBox', 8)
            i += 1
            continue

        # NavBar — pleine largeur
        if tid == 'NavBar':
            ctrl = {
                "ID": str(id_), "typeID": "NavBar", "zOrder": str(id_),
                "measuredW": "300", "measuredH": "30",
                "x": "0", "y": str(y),
                "w": "1000",
                "properties": {"text": label}
            }
            controls.append(ctrl)
            id_ += 1
            y += 30 + SPACING.get('NavBar', 20)
            i += 1
            continue

        # HRule — séparateur pleine largeur
        if tid == 'HRule':
            ctrl = {
                "ID": str(id_), "typeID": "HRule", "zOrder": str(id_),
                "measuredW": "200", "measuredH": "10",
                "x": str(LEFT), "y": str(y),
                "w": "800",
            }
            controls.append(ctrl)
            id_ += 1
            y += 5 + SPACING.get('HRule', 12)
            i += 1
            continue

        # TextInput — avec largeur
        if tid in ('TextInput', 'TextArea'):
            h_field = 27 if tid == 'TextInput' else 80
            ctrl = {
                "ID": str(id_), "typeID": tid, "zOrder": str(id_),
                "measuredW": "79" if tid == 'TextInput' else "200",
                "measuredH": str(h_field),
                "x": str(LEFT), "y": str(y),
                "w": str(INPUT_WIDTH),
            }
            if label:
                ctrl["properties"] = {"text": ""}
            controls.append(ctrl)
            id_ += 1
            y += h_field + SPACING.get(tid, 20)
            i += 1
            continue

        # Button — aligné à droite ou gauche selon position
        if tid == 'Button':
            ctrl = {
                "ID": str(id_), "typeID": "Button", "zOrder": str(id_),
                "measuredW": "61", "measuredH": "27",
                "x": str(LEFT), "y": str(y),
                "properties": {"text": label}
            }
            # Bouton "Suivant" à droite
            if any(w in label.lower() for w in ['suivant', 'next', 'submit', 'envoyer', 'valider']):
                ctrl["x"] = str(LEFT + INPUT_WIDTH - 80)
            controls.append(ctrl)
            id_ += 1
            y += 27 + SPACING.get('Button', 10)
            i += 1
            continue

        # Title, SubTitle, Label, Link — texte simple
        ctrl = {
            "ID": str(id_), "typeID": tid, "zOrder": str(id_),
            "measuredW": str(mw), "measuredH": str(mh),
            "x": str(LEFT), "y": str(y),
            "properties": {"text": label}
        }

        # Espacement avant SubTitle (section)
        if tid == 'SubTitle' and id_ > 0:
            y += 10  # espace supplémentaire avant une section

        controls.append(ctrl)
        id_ += 1

        # Espacement après
        gap = SPACING.get(tid, 10)
        if tid == 'Label':
            # Vérifier si le prochain est un TextInput
            next_tid = lines[i+1][0] if i+1 < len(lines) else ''
            next_norm = {'textinput': 'TextInput', 'input': 'TextInput'}.get(next_tid.lower(), next_tid)
            if next_norm == 'TextInput':
                gap = 2  # label collé au champ
            else:
                gap = 12
        
        y += mh + gap
        i += 1

    return controls


def analyze_with_groq(image_path: str, api_key: str, project_id: str = "0:1") -> Dict[str, Any]:
    b64, mime = _prepare_image(image_path)
    client = Groq(api_key=api_key)

    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": PROMPT}
                ]}],
                temperature=0.0,
                max_tokens=1500,
            )
            raw = response.choices[0].message.content
            controls = _parse_and_layout(raw)

            if not controls:
                raise ValueError("Aucun composant détecté")

            max_y = max(int(c["y"]) + int(c.get("h", c["measuredH"])) for c in controls)
            mockup_h = str(max_y + 60)

            return {
                "mockup": {
                    "controls": {"control": controls},
                    "attributes": {"name": "New Wireframe 1", "order": 938428.5264654435, "parentID": None, "notes": None},
                    "branchID": "Master",
                    "resourceID": str(uuid.uuid4()).upper(),
                    "mockupH": mockup_h, "mockupW": "1000",
                    "measuredW": "1000", "measuredH": mockup_h,
                    "version": "1.0",
                    "calloutsOffset": {"x": 0, "y": 0},
                },
                "groupOffset": {"x": 0, "y": 0},
                "dependencies": [],
                "projectID": project_id,
                "_raw": raw,
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
