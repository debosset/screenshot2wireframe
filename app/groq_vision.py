import base64, json, re, uuid, io, time
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq, InternalServerError, RateLimitError
from PIL import Image

# Prompt court avec exemple — Groq copie le format exactement
PROMPT = """Analyze this web form screenshot and return a Balsamiq wireframe JSON.

Return ONLY raw JSON (no markdown, no backticks), following this exact structure:
{"controls":[{"ID":"0","typeID":"Title","zOrder":"0","measuredW":"300","measuredH":"30","x":"100","y":"20","properties":{"text":"Page Title"}},{"ID":"1","typeID":"SubTitle","zOrder":"1","measuredW":"250","measuredH":"24","x":"100","y":"60","properties":{"text":"Section name"}},{"ID":"2","typeID":"Label","zOrder":"2","measuredW":"100","measuredH":"17","x":"100","y":"100","properties":{"text":"Field label"}},{"ID":"3","typeID":"TextInput","zOrder":"3","measuredW":"79","measuredH":"27","x":"100","y":"118","w":"500"},{"ID":"4","typeID":"CheckBox","zOrder":"4","measuredW":"100","measuredH":"23","x":"100","y":"160","properties":{"text":"Option text"}},{"ID":"5","typeID":"Button","zOrder":"5","measuredW":"61","measuredH":"27","x":"100","y":"200","properties":{"text":"Submit"}}],"mockupW":"1000","mockupH":"400"}

Rules:
- Label always 15px above its TextInput (label y + 15 = input y)
- TextInput must have w (width in px)
- Button/Label/CheckBox/RadioButton: no w or h attributes
- All values are strings
- Max 25 controls total
- Raw JSON only"""


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


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    # Enlever backticks si présents
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Sinon prendre entre premier { et dernier }
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        return raw[start:end+1].strip()
    return raw


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
                max_tokens=3000,
            )
            raw = response.choices[0].message.content
            clean = _extract_json(raw)
            parsed = json.loads(clean)
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
            time.sleep(3 * (attempt + 1))
        except json.JSONDecodeError as e:
            last_error = ValueError(f"JSON invalide: {e}")
            break
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
