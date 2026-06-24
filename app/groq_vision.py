"""
Analyse un screenshot avec Groq Vision (LLaVA) — gratuit jusqu'à 30 req/min.
Retourne une liste de composants Balsamiq prêts à l'emploi.
"""
import base64
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq


SYSTEM_PROMPT = """Tu es un expert Balsamiq Wireframes. Analyse ce screenshot d'interface web et retourne UNIQUEMENT un JSON valide.

RÈGLES STRICTES :
- Réponds UNIQUEMENT avec du JSON brut, sans markdown, sans explication, sans ```
- Détecte TOUS les éléments visibles de haut en bas
- Utilise ces typeIDs exacts : Title, SubTitle, Label, Link, TextInput, TextArea, Button, ButtonBar, CheckBox, RadioButton, ComboBox, Image, Rectangle, HRule, NavBar, TabBar, BreadCrumb, Pagination, DataGrid
- Les coordonnées x/y/w/h sont en base 1000px de large (hauteur proportionnelle)
- ID commence à 0, zOrder identique à ID
- Tous les champs sont des strings

FORMAT EXACT :
{
  "controls": [
    {"ID":"0","typeID":"Title","zOrder":"0","measuredW":"300","measuredH":"30","x":"50","y":"20","properties":{"text":"Mon titre"}},
    {"ID":"1","typeID":"Label","zOrder":"1","measuredW":"100","measuredH":"17","x":"50","y":"60","properties":{"text":"Nom"}},
    {"ID":"2","typeID":"TextInput","zOrder":"2","measuredW":"79","measuredH":"27","x":"50","y":"78","w":"400","properties":{"text":""}},
    {"ID":"3","typeID":"CheckBox","zOrder":"3","measuredW":"100","measuredH":"23","x":"50","y":"120","properties":{"text":"Option","selected":true}}
  ],
  "mockupW": "1000",
  "mockupH": "800"
}

IMPORTANT pour le placement :
- Label juste AU-DESSUS du TextInput correspondant (y_label + 15 = y_input environ)
- Respecte la hiérarchie visuelle : titres > sous-titres > labels > champs
- Pour les RadioButton côte à côte : même y, x différents
- TextInput a toujours un w (largeur) car il est redimensionné
- Button, Label, CheckBox, RadioButton n'ont PAS de w/h (taille par défaut)"""


def analyze_with_groq(image_path: str, api_key: str, project_id: str = "0:1") -> Dict[str, Any]:
    """Analyse l'image et retourne le JSON Balsamiq complet."""
    # Encoder l'image
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
    suffix = Path(image_path).suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suffix, "image/png")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": "Analyse ce screenshot et retourne le JSON Balsamiq."}
                ]
            }
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    # Nettoyer si markdown
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    parsed = json.loads(raw)
    controls = parsed.get("controls", [])
    mockup_w = parsed.get("mockupW", "1000")
    mockup_h = parsed.get("mockupH", "800")

    import uuid
    return {
        "mockup": {
            "controls": {"control": controls},
            "attributes": {"name": "New Wireframe 1", "order": 938428.5264654435, "parentID": None, "notes": None},
            "branchID": "Master",
            "resourceID": str(uuid.uuid4()).upper(),
            "mockupH": mockup_h,
            "mockupW": mockup_w,
            "measuredW": mockup_w,
            "measuredH": mockup_h,
            "version": "1.0",
            "calloutsOffset": {"x": 0, "y": 0},
        },
        "groupOffset": {"x": 0, "y": 0},
        "dependencies": [],
        "projectID": project_id,
    }


def extract_components(mockup_json: Dict) -> List[Dict]:
    """Extourne la liste de composants pour l'affichage UI."""
    TYPE_LABELS = {
        "Title": "🔤 Titre", "SubTitle": "🔤 Sous-titre", "Label": "🏷️ Label",
        "Link": "🔗 Lien", "TextInput": "✏️ Champ texte", "TextArea": "📄 Zone texte",
        "Button": "🔘 Bouton", "ButtonBar": "🔘 Barre boutons",
        "CheckBox": "☑️ Case à cocher", "RadioButton": "🔘 Radio",
        "NavBar": "🧭 Navigation", "Image": "🖼️ Image",
        "Rectangle": "▭ Rectangle", "HRule": "— Séparateur",
    }
    controls = mockup_json.get("mockup", {}).get("controls", {}).get("control", [])
    result = []
    for c in controls:
        tid = c.get("typeID", "Rectangle")
        props = c.get("properties", {})
        text = props.get("text", "") if isinstance(props, dict) else ""
        result.append({
            **c,
            "label": TYPE_LABELS.get(tid, f"▭ {tid}"),
            "description": str(text)[:60] if text else "",
            "x": int(c.get("x", 0)),
            "y": int(c.get("y", 0)),
            "w": int(c.get("w", c.get("measuredW", 100))),
            "h": int(c.get("h", c.get("measuredH", 20))),
            "measuredW": int(c.get("measuredW", 100)),
            "measuredH": int(c.get("measuredH", 20)),
        })
    return result
