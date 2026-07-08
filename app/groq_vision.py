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

from .balsamiq_components import VALID_TYPE_IDS, MEASURED as COMPONENT_MEASURED, get_measured, estimate_measured

# Liste complète et toujours à jour des typeID valides (source unique :
# balsamiq_components.py). On ne restreint plus l'IA à un sous-ensemble —
# elle a accès à tous les composants Balsamiq connus. La sanitation dans
# balsamiq_components.sanitize_components() reste un filet de sécurité qui
# corrige les rares hallucinations, elle ne limite pas ce que l'IA peut choisir.
_TYPE_ID_LIST = ", ".join(sorted(VALID_TYPE_IDS))

# ── Schema JSON strict pour le mode "structured outputs" de Groq ──────────
# Contrairement au simple "json_object" (best-effort + validation a
# posteriori, qui peut encore échouer -- voir historique des bugs), ce mode
# contraint le modèle TOKEN PAR TOKEN à ne produire que du JSON conforme.
# Contraintes du mode strict: tous les champs listés sont obligatoires et
# additionalProperties doit être false, donc le format est volontairement
# PLAT et minimal : pas de "properties" imbriquées, pas de measuredW/H (on
# les déduit nous-mêmes du typeID via balsamiq_components.MEASURED -- le
# modèle n'a pas à connaître les dimensions par défaut de chaque composant
# Balsamiq, c'était une source d'erreurs inutile), pas de zOrder (dérivé
# mécaniquement de la position dans le tableau).
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "controls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "typeID": {"type": "string"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "w": {"type": "integer"},
                    "h": {"type": "integer"},
                    "text": {"type": "string"},
                    "selected": {"type": "boolean"},
                },
                "required": ["id", "typeID", "x", "y", "w", "h", "text", "selected"],
                "additionalProperties": False,
            },
        },
        "mockupW": {"type": "integer"},
        "mockupH": {"type": "integer"},
    },
    "required": ["controls", "mockupW", "mockupH"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""Tu es un expert Balsamiq Wireframes. Analyse ce screenshot d'interface web et retourne un JSON conforme au schema fourni.

RÈGLES :
- Détecte TOUS les éléments visibles de haut en bas, y compris les éléments moins courants (Accordion, Tree, Menu, MenuBar, DataGrid, ProgressBar, Tooltip, TagCloud, Calendar, graphiques, etc.) quand ils sont présents à l'écran — ne te limite pas aux formulaires basiques.
- Choisis le typeID le plus PRÉCIS possible parmi la liste ci-dessous plutôt qu'un générique (ex : un menu déroulant est un "ComboBox" pas un "Rectangle", une barre de progression est un "ProgressBar" pas un "HRule").
- Voici TOUS les typeIDs valides dans Balsamiq (utilise exclusivement ceux-ci, respecte la casse exacte) :
  {_TYPE_ID_LIST}
- Cas fréquents à bien mapper :
  - barre de navigation horizontale (liens en haut de page) -> "LinkBar" (jamais "NavBar", ça n'existe pas)
  - fil d'Ariane -> "BreadCrumbs" au pluriel (jamais "BreadCrumb")
  - pagination -> pas de contrôle natif dédié, utilise "ButtonBar"
  - tableau de données / liste de résultats -> "DataGrid"
  - liste verticale d'éléments simples -> "List"
  - arborescence (fichiers, catégories imbriquées) -> "Tree"
  - menu déroulant / select -> "ComboBox"
  - menu contextuel ou latéral -> "Menu" ou "MenuBar" selon l'orientation
  - onglets -> "TabBar"
  - accordéon / sections repliables -> "Accordion"
  - champ de recherche -> "SearchBox"
  - sélecteur de date -> "DateChooser"
  - icône seule -> "Icon" ; icône + texte -> "IconLabel"
  - groupe de champs encadré -> "FieldSet"
  - bloc de texte long (paragraphe) -> "Paragraph" (pas "Label", réservé aux textes courts)
- Les coordonnées x/y/w/h sont des ENTIERS en base 1000px de large (hauteur proportionnelle). w et h : mets 0 si non pertinent pour ce typeID (taille par défaut Balsamiq), sinon une largeur/hauteur explicite (utile surtout pour TextInput/TextArea/Rectangle/Image).
- "id" est un entier séquentiel commençant à 0.
- "text" est le texte affiché par le contrôle (chaîne vide "" si aucun texte, ex: HRule, Image).
- "selected" est un booléen, pertinent uniquement pour CheckBox/RadioButton (true si coché/sélectionné) ; mets false pour tous les autres types.

IMPORTANT pour le placement :
- Label juste AU-DESSUS du TextInput correspondant (y_label + 15 = y_input environ)
- Respecte la hiérarchie visuelle : titres > sous-titres > labels > champs
- Pour les RadioButton côte à côte : même y, x différents
- Laisse un espacement vertical d'au moins 20-25px entre le bloc d'en-tête (logo, titre principal de l'app) et les éléments qui suivent (breadcrumb, lien de retour...) -- ne les colle jamais l'un contre l'autre même s'ils sont proches dans l'image source

NE JAMAIS FUSIONNER PLUSIEURS ÉLÉMENTS DISTINCTS EN UN SEUL CONTRÔLE :
- INTERDIT d'inventer un séparateur ("|", "I", "/", "-", etc.) pour coller plusieurs textes qui sont visuellement distincts dans l'image en une seule valeur "text". Chaque texte qui a sa propre couleur, taille, poids de police, ou position clairement séparée est un contrôle séparé, avec son propre x/y.
- Exemple concret À NE PAS FAIRE : un texte "Romande Energie SA I Déposer un relevé énergétique annuel" -- ce sont DEUX éléments (un petit lien coloré + un gros titre en dessous), donc DEUX contrôles distincts : un Link ET un Title/SubTitle, à des y différents.
- Indicateur d'étapes numérotées (cercles "1 2 3" avec des labels comme "Saisie / Vérification / Transmission" en dessous, reliés par une ligne) : ne JAMAIS le rendre comme une seule ligne de texte avec des séparateurs. Décompose-le en plusieurs contrôles Label distincts (un par étape), au même y, avec des x différents et bien espacés selon leur position réelle dans l'image."""


def _repair_dangling_keys(raw: str) -> str:
    """
    Répare deux variantes du même bug Groq -- une clé suivie d'une virgule
    au lieu d'un ':valeur' :

    Cas A -- valeur complètement oubliée, ce qui suit est la clé suivante :
        '"measuredW","measuredH":"20"'  ->  '"measuredH":"20"'
        (on supprime la clé orpheline ; nos defaults en aval prennent le relais)

    Cas B -- la valeur est bien là, mais le ':' a été remplacé par une ',' :
        '"y","270"'  ->  '"y":"270"'
        (on réinsère le ':' manquant)

    On distingue les deux en regardant ce qui suit la chaîne candidate : si
    elle est elle-même suivie d'un ':', c'est la clé suivante (cas A) ; sinon
    c'est la valeur du champ courant (cas B).
    """
    pattern = re.compile(
        r'(?<![:\[])"([A-Za-z_][A-Za-z0-9_]*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*(?=([,:}\]]))'
    )

    def repl(m):
        key, val, nextch = m.group(1), m.group(2), m.group(3)
        if nextch == ':':
            return f'"{val}"'          # cas A : `val` est en fait la clé suivante
        return f'"{key}":"{val}"'      # cas B : deux-points manquant réinséré

    return pattern.sub(repl, raw)


def _repair_unescaped_quotes(raw: str) -> str:
    """
    Répare les guillemets internes non échappés dans N'IMPORTE QUELLE chaîne
    JSON (clé ou valeur) -- Groq génère parfois du texte citant des
    guillemets (ex: « Romande Énergie SA ») sans les échapper, ce qui casse
    le JSON strict avec une erreur "Expecting ':' delimiter" au milieu d'une
    ligne. Contrairement à une v1 qui ne ciblait que la clé "text", celle-ci
    est générique : elle suit une chaîne dès son guillemet ouvrant et ne la
    referme que sur un guillemet suivi d'un vrai délimiteur JSON (, : } ]).
    Tout autre guillemet rencontré entre-temps est échappé.
    """
    out = []
    i, n = 0, len(raw)
    in_string = False
    while i < n:
        ch = raw[i]
        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue
        if ch == '\\' and i + 1 < n:
            out.append(raw[i:i + 2]); i += 2; continue
        if ch == '"':
            j = i + 1
            while j < n and raw[j] in ' \t\r\n':
                j += 1
            if j >= n or raw[j] in ',:}]':
                out.append('"'); in_string = False; i += 1; continue
            out.append('\\"'); i += 1; continue
        out.append(ch); i += 1
    return ''.join(out)


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
                    {"type": "text", "text": "Analyse ce screenshot et retourne le JSON conforme au schema."}
                ]
            }
        ],
        temperature=0.1,
        max_tokens=4096,
        # Vrai mode "structured outputs" : contraint le modèle TOKEN PAR
        # TOKEN à ne produire que du JSON conforme au schema (contrairement
        # à {"type":"json_object"} qui n'est qu'un best-effort validé après
        # coup, et qui échouait encore avec des clés cassées). Supporté
        # nativement par meta-llama/llama-4-scout-17b-16e-instruct.
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "balsamiq_mockup", "strict": True, "schema": JSON_SCHEMA},
        },
    )

    raw = response.choices[0].message.content.strip()

    # Le mode structured outputs garantit une syntaxe JSON valide -- ce
    # json.loads() ne devrait plus jamais échouer. On garde quand même les
    # réparations en filet de sécurité au cas où (ex: si Groq change de
    # comportement, ou pour un autre modèle moins strict à l'avenir).
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
        for repair_fn in (_repair_dangling_keys, _repair_unescaped_quotes,
                          lambda s: _repair_unescaped_quotes(_repair_dangling_keys(s))):
            try:
                parsed = json.loads(repair_fn(raw))
                break
            except json.JSONDecodeError:
                continue
        if parsed is None:
            try:
                json.loads(raw)
            except json.JSONDecodeError as e2:
                start = max(0, e2.pos - 80)
                end = min(len(raw), e2.pos + 80)
                snippet = raw[start:end]
                raise ValueError(f"{e2} | extrait autour de l'erreur: ...{snippet!r}...") from e2

    flat_controls = parsed.get("controls", [])
    mockup_w = str(parsed.get("mockupW") or 1000)
    mockup_h = str(parsed.get("mockupH") or 800)

    # Reconstruire le format Balsamiq complet (nested "properties", ID/zOrder
    # en string, measuredW/measuredH) depuis le format plat renvoyé par Groq.
    # measuredW/measuredH ne sont PLUS demandés au modèle : on les déduit
    # nous-mêmes du typeID via balsamiq_components.MEASURED, une source
    # fiable plutôt qu'un nombre halluciné par le LLM.
    controls = []
    for idx, fc in enumerate(flat_controls):
        tid = fc.get("typeID", "Rectangle")
        text = fc.get("text", "")
        mw, mh = estimate_measured(tid, text)
        properties = {"text": text}
        if tid == "Title":
            properties["size"] = "20"
        elif tid == "SubTitle":
            properties["size"] = "16"
        control = {
            "ID": str(fc.get("id", idx)),
            "typeID": tid,
            "zOrder": str(idx),
            "measuredW": str(mw),
            "measuredH": str(mh),
            "x": str(fc.get("x", 0)),
            "y": str(fc.get("y", 0)),
            "properties": properties,
        }
        w, h = fc.get("w", 0), fc.get("h", 0)
        if w:
            control["w"] = str(w)
        if h:
            control["h"] = str(h)
        if tid in ("CheckBox", "RadioButton"):
            control["properties"]["selected"] = bool(fc.get("selected", False))
        controls.append(control)

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


def _safe_int(value, default):
    """
    Conversion int() qui ne plante jamais. Groq met parfois une valeur
    aberrante (ex: le nom d'une clé "measuredH" au lieu d'un nombre, ou une
    chaîne vide, ou un flottant "20.5") dans un champ censé être numérique --
    dans ce cas on retombe sur `default` plutôt que de faire planter toute
    l'analyse pour un seul contrôle mal formé.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


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
        measured_w = _safe_int(c.get("measuredW", 100), 100)
        measured_h = _safe_int(c.get("measuredH", 20), 20)
        result.append({
            **c,
            "label": TYPE_LABELS.get(tid, f"▭ {tid}"),
            "description": str(text)[:60] if text else "",
            "x": _safe_int(c.get("x", 0), 0),
            "y": _safe_int(c.get("y", 0), 0),
            "w": _safe_int(c.get("w", measured_w), measured_w),
            "h": _safe_int(c.get("h", measured_h), measured_h),
            "measuredW": measured_w,
            "measuredH": measured_h,
        })
    return result
