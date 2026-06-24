import base64, json, re, uuid, io
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq
from PIL import Image

PROMPT = """Analyse ce screenshot d'interface web et génère un wireframe Balsamiq.
Retourne UNIQUEMENT du JSON valide, sans texte, sans markdown, sans ```.

Format exact :
{"controls":[{"ID":"0","typeID":"Title","zOrder":"0","measuredW":"300","measuredH":"30","x":"50","y":"20","properties":{"text":"Titre"}},{"ID":"1","typeID":"Label","zOrder":"1","measuredW":"100","measuredH":"17","x":"50","y":"60","properties":{"text":"Nom"}},{"ID":"2","typeID":"TextInput","zOrder":"2","measuredW":"79","measuredH":"27","x":"50","y":"78","w":"400"}],"mockupW":"1000","mockupH":"800"}

TypeIDs valides : Title, SubTitle, Label, Link, TextInput, TextArea, Button, ButtonBar, CheckBox, RadioButton, ComboBox, NavBar, Image, Rectangle, HRule
Règles importantes :
- Label placé 15px au-dessus du TextInput correspondant
- TextInput a toujours w (largeur)
- Button, Label, CheckBox, RadioButton : sans w/h
- Coordonnées en base 1000px de large, hauteur proportionnelle
- Tous les champs numériques en string
- JSON pur uniquement, pas de texte autour"""


def _prepare_image(image_path: str, max_size: int = 1200) -> tuple[str, str]:
    """Redimensionne l'image si nécessaire et retourne (base64, mime_type)."""
    img = Image.open(image_path)
    
    # Convertir en RGB si nécessaire
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Redimensionner si trop grande
    w, h = img.size
    if w > max_size or h > max_size:
        ratio = min(max_size/w, max_size/h)
        new_w, new_h = int(w*ratio), int(h*ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Encoder en JPEG (plus léger que PNG)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85, optimize=True)
    buf.seek(0)
    
    b64 = base64.standard_b64encode(buf.read()).decode("utf-8")
    return b64, "image/jpeg"


def analyze_with_groq(image_path: str, api_key: str, project_id: str = "0:1") -> Dict[str, Any]:
    b64, mime = _prepare_image(image_path)
    
    client = Groq(api_key=api_key)
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": PROMPT}
            ]
        }],
        temperature=0.0,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    
    # Nettoyer markdown
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.strip()
    
    # Extraire le JSON
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        raw = m.group(0)

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
