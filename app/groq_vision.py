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
                    "fillColor": {"type": "string"},
                },
                "required": ["id", "typeID", "x", "y", "w", "h", "text", "selected", "fillColor"],
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
- PRIORITÉ ABSOLUE : détecte TOUS les éléments visibles de haut en bas, sans exception. Une analyse incomplète (élément oublié) est pire qu'une analyse avec un détail imparfait. Avant de finir, repasse mentalement l'image de haut en bas et vérifie que chaque texte, titre, champ et bouton a bien un contrôle correspondant.
- Piège fréquent à ne PAS reproduire : le nom de l'organisme/app en haut à gauche en gros caractères (ex: "ÉTAT DE VAUD") est un "Title" à PART ENTIÈRE, même s'il est juste en dessous ou à côté d'une bande colorée décorative -- ce n'est pas la même chose que le bandeau, ne l'omets jamais.
- Choisis le typeID le plus PRÉCIS possible (ex : menu déroulant -> "ComboBox" pas "Rectangle" ; barre de progression -> "ProgressBar" pas "HRule").
- TypeIDs valides (casse exacte, exclusivement ceux-ci) : {_TYPE_ID_LIST}
- Mappings fréquents : nav horizontale -> "LinkBar" (jamais "NavBar") ; fil d'Ariane -> "BreadCrumbs" (jamais "BreadCrumb") ; pagination -> "ButtonBar" (pas de type dédié) ; tableau -> "DataGrid" ; liste -> "List" ; arborescence -> "Tree" ; select -> "ComboBox" ; onglets -> "TabBar" ; accordéon -> "Accordion" ; recherche -> "SearchBox" ; date -> "DateChooser" ; icône -> "Icon"/"IconLabel" ; paragraphe long -> "Paragraph" (pas "Label").
- x/y/w/h sont des ENTIERS base 1000px large. w/h : 0 si taille par défaut suffit, sinon valeur explicite (surtout pour TextInput/TextArea/Rectangle/Image).
- "id" entier séquentiel depuis 0. "text" = texte affiché ("" si aucun). "selected" booléen (CheckBox/RadioButton uniquement, false sinon).
- "fillColor" (hex, ex "#4CAF50") : à UTILISER pour tout bandeau/bloc de couleur unie clairement visible dans l'image (typeID "Rectangle", peu importe, converti auto) -- ex: bande décorative colorée en haut de page, bloc de fond gris clair derrière un lien de fil d'Ariane + titre. Ne l'omets pas si tu vois clairement ces blocs, mesure juste leur hauteur RÉELLE (souvent une fine bande 15-30px pour un bandeau d'en-tête, ne l'étends pas artificiellement). Si ce bloc englobe PLUSIEURS lignes de texte (ex: un lien ET un titre l'un sous l'autre), sa hauteur "h" doit couvrir les DEUX lignes avec leur espacement, pas juste la première -- ne le laisse jamais trop court par rapport à son contenu réel. Laisse "" (vide) uniquement si tu ne vois AUCUN aplat de couleur net, ou pour la ligne de connexion du stepper (cas spécifique ci-dessous). Place chaque bloc de couleur en PREMIER dans "controls".

CAS PARTICULIERS À BIEN GÉRER :
- N'invente RIEN qui n'est pas visible (pas de faux menu/lien/bouton). Dans le doute, n'ajoute pas.
- Deux textes empilés proches (ex: nom d'entreprise au-dessus d'un prénom) : y clairement différents, jamais identiques. Vaut aussi horizontalement : deux contrôles sur la même ligne (même y) doivent avoir un écart en x suffisant (x2 >= x1 + largeur du texte 1 + marge) pour ne jamais se chevaucher visuellement -- déjà observé : "ÉTAT DE VAUD" chevauchant un lien juste à côté sur la même ligne.
- Titre de section (gras, plus grand que le texte de formulaire, seul sur sa ligne) -> "SubTitle"/"Title", JAMAIS "Label".
- "Link" seulement si le texte est visuellement coloré/souligné (cliquable). Un texte noir plein à côté d'un lien N'EST PAS un lien -- reste "Title"/"SubTitle". Piège récurrent à éviter : un titre de page en noir gras juste sous un lien de fil d'Ariane coloré (ex: "Déposer un relevé énergétique annuel" sous "Romande Énergie SA") doit être "Title" ou "SubTitle", jamais "Link", même s'ils sont proches et sur un fond commun.
- Jamais fusionner 2 textes visuellement distincts (couleur/taille/police différente) en une seule valeur "text" avec un séparateur inventé ("|", "I"...) : ce sont 2 contrôles séparés.
- Cercles numérotés d'étapes (ex "1 2 3" + "Saisie/Vérification/Transmission") : "RoundButton" (~32x32) pour chaque cercle + "Label" pour le texte dessous, chacun un contrôle INDÉPENDANT. JAMAIS "ProgressBar"/"Rectangle"/"TabBar"/"ButtonBar" ni aucun conteneur qui engloberait plusieurs étapes dans un même cadre/pilule (rendu disgracieux, déjà observé). Cas spécifique uniquement : n'utilise pas non plus "fillColor" pour la ligne de connexion ENTRE les cercles -- omets-la. Ça ne concerne QUE cette ligne de connexion, pas les autres blocs de couleur légitimes ailleurs dans la page (bandeau d'en-tête, fond gris...).
- Label juste AU-DESSUS de son TextInput (y_label + 15 ≈ y_input). Hiérarchie : titres > sous-titres > labels > champs. RadioButton côte à côte : même y, x différents.
- Chaque TextInput/TextArea doit avoir un "h" explicite d'au moins 30px et un espacement vertical d'au moins 15-20px avant le label du champ suivant -- ne laisse jamais deux champs se toucher ou se chevaucher visuellement."""


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

    from groq import BadRequestError

    try:
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
    except BadRequestError as e:
        # Même en mode "strict", Groq peut rejeter SA PROPRE génération si
        # elle ne colle pas exactement au schema (déjà vu : un contrôle sur
        # 26 sans "fillColor"). Plutôt que de perdre tout le travail, on
        # récupère le JSON généré dans l'erreur elle-même (failed_generation)
        # -- il est presque toujours utilisable tel quel, nos champs
        # manquants sont déjà tous gérés avec des valeurs par défaut (.get()
        # avec fallback) dans la reconstruction plus bas.
        body = getattr(e, "body", None) or {}
        error_info = body.get("error", {}) if isinstance(body, dict) else {}
        failed_gen = error_info.get("failed_generation") if isinstance(error_info, dict) else None
        if not failed_gen:
            raise
        raw = failed_gen.strip()

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

        # Un bloc de couleur de fond doit être un "Canvas" (pas "Rectangle" --
        # confirmé buggy en pratique) avec "color" ET "borderColor" identiques
        # pour avoir un aplat plein plutôt qu'un simple contour. On force le
        # typeID indépendamment de ce que le modèle a choisi, dès qu'une
        # fillColor valide est fournie.
        hexcolor = (fc.get("fillColor") or "").strip().lstrip("#")
        is_color_block = len(hexcolor) == 6
        if is_color_block:
            tid = "Canvas"

        mw, mh = estimate_measured(tid, text)
        if tid == "Title":
            properties = {"text": f"*{text}*" if text else text}
            properties["size"] = "20"
        elif tid == "SubTitle":
            properties = {"text": f"*{text}*" if text else text}
            properties["size"] = "16"
        else:
            properties = {"text": text}
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
        if is_color_block:
            try:
                decimal_color = str(int(hexcolor, 16))
                control["properties"]["color"] = decimal_color
                control["properties"]["borderColor"] = decimal_color
            except ValueError:
                pass
        controls.append((is_color_block, control))

    # Forcer les blocs de couleur (Canvas) en arrière-plan (zOrder le plus
    # bas), indépendamment de l'ordre choisi par le modèle -- on ne compte
    # plus sur sa discipline à les mettre en premier dans le tableau, ce qui
    # a déjà causé un Canvas passant devant un titre et le masquant.
    controls.sort(key=lambda item: (not item[0],))
    controls = [c for _, c in controls]
    for new_idx, c in enumerate(controls):
        c["zOrder"] = str(new_idx)

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
