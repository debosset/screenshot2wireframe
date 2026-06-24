import base64, json, re, uuid, io, time
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq, InternalServerError, RateLimitError
from PIL import Image

PROMPT = """Look at this web interface screenshot and generate a Balsamiq wireframe.
Return ONLY a valid JSON object, no text before or after, no markdown, no backticks.

Use this exact format:
{"controls":[{"ID":"0","typeID":"Title","zOrder":"0","measuredW":"300","measuredH":"30","x":"50","y":"20","properties":{"text":"Page title"}},{"ID":"1","typeID":"Label","zOrder":"1","measuredW":"100","measuredH":"17","x":"50","y":"60","properties":{"text":"Name"}},{"ID":"2","typeID":"TextInput","zOrder":"2","measuredW":"79","measuredH":"27","x":"50","y":"78","w":"400"},{"ID":"3","typeID":"Button","zOrder":"3","measuredW":"61","measuredH":"27","x":"50","y":"120","properties":{"text":"Submit"}}],"mockupW":"1000","mockupH":"600"}

Valid typeID values: Title, SubTitle, Label, Link, TextInput, TextArea, Button, ButtonBar, CheckBox, RadioButton, ComboBox, NavBar, Image, Rectangle, HRule

Rules:
- Label y + 15 = TextInput y (label just above its field)
- TextInput always has w attribute
- Button, Label, CheckBox, RadioButton do NOT have w or h
- All numeric values must be strings
- Coordinates based on 1000px wide canvas
- Return pure JSON only, nothing else"""

# Modèles vision disponibles sur Groq, par ordre de préférence
# Seul modèle vision actif sur Groq (juin 2026)
VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
]


def _prepare_image(image_path: str, max_size: int = 800) -> tuple:
    img = Image.open(image_path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    w, h = img.size
    if w > max_size or h > max_size:
        ratio = min(max_size/w, max_size/h)
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=80, optimize=True)
    buf.seek(0)
    return base64.standard_b64encode(buf.read()).decode("utf-8"), "image/jpeg"


def _fix_json(raw: str) -> str:
    start = raw.find('{')
    if start > 0:
        raw = raw[start:]
    depth, end, in_str, esc = 0, 0, False, False
    for i, ch in enumerate(raw):
        if esc: esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if not in_str:
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: end = i + 1; break
    return raw[:end].strip() if end else raw.strip()


def _call_groq(client, model, b64, mime):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        temperature=0.0,
        max_tokens=4096,
    )


def analyze_with_groq(image_path: str, api_key: str, project_id: str = "0:1") -> Dict[str, Any]:
    b64, mime = _prepare_image(image_path)
    client = Groq(api_key=api_key)

    last_error = None
    for model in VISION_MODELS:
        for attempt in range(2):  # 2 tentatives par modèle
            try:
                response = _call_groq(client, model, b64, mime)
                raw = response.choices[0].message.content.strip()
                raw = re.sub(r'```json\s*', '', raw)
                raw = re.sub(r'```\s*', '', raw)
                raw = _fix_json(raw)
                parsed = json.loads(raw)
                controls = parsed.get("controls", [])
                mockup_w = str(parsed.get("mockupW", "1000"))
                mockup_h = str(parsed.get("mockupH", "800"))
                return {
                    "mockup": {
                        "controls": {"control": controls},
                        "attributes": {"name": "New Wireframe 1", "order": 938428.5264654435, "parentID": None, "notes": None},
                        "branchID": "Master",
                        "resourceID": str(uuid.uuid4()).upper(),
                        "mockupH": mockup_h, "mockupW": mockup_w,
                        "measuredW": mockup_w, "measuredH": mockup_h,
                        "version": "1.0",
                        "calloutsOffset": {"x": 0, "y": 0},
                    },
                    "groupOffset": {"x": 0, "y": 0},
                    "dependencies": [],
                    "projectID": project_id,
                }
            except (InternalServerError, RateLimitError) as e:
                last_error = e
                wait = 3 * (attempt + 1)
                time.sleep(wait)
                continue
            except Exception as e:
                last_error = e
                break  # Essayer le modèle suivant

    raise ValueError(f"Tous les modèles Groq sont indisponibles. Réessayez dans quelques secondes. ({last_error})")


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
