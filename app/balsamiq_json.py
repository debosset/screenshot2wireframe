"""
Génère le JSON format presse-papier Balsamiq.
Format : BMLF + zlib(JSON) encodé base64
C'est le format natif utilisé par Balsamiq quand on copie-colle des composants.
"""
import json
import zlib
import base64
from typing import List, Dict, Any


TYPE_MAP = {
    "com.balsamiq.mockups::Button":        "com.balsamiq.mockups::Button",
    "com.balsamiq.mockups::TextInput":     "com.balsamiq.mockups::TextInput",
    "com.balsamiq.mockups::Label":         "com.balsamiq.mockups::Label",
    "com.balsamiq.mockups::CheckBox":      "com.balsamiq.mockups::CheckBox",
    "com.balsamiq.mockups::Image":         "com.balsamiq.mockups::Image",
    "com.balsamiq.mockups::NavigationBar": "com.balsamiq.mockups::NavBar",
    "com.balsamiq.mockups::Rectangle":     "com.balsamiq.mockups::Rectangle",
}


def _make_control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    type_id = TYPE_MAP.get(comp["type"], "com.balsamiq.mockups::Rectangle")
    properties = {}
    if "Button" in type_id:      properties["text"] = "Button"
    elif "TextInput" in type_id: properties["text"] = ""
    elif "Label" in type_id:     properties["text"] = "Label"
    elif "CheckBox" in type_id:  properties["text"] = "Option"
    elif "NavBar" in type_id:    properties["text"] = "Home, About, Contact"
    return {
        "ID": str(index + 1),
        "typeID": type_id,
        "zOrder": index,
        "locked": "false",
        "isInGroup": "-1",
        "x": str(comp["x"]),
        "y": str(comp["y"]),
        "w": str(comp["w"]),
        "h": str(comp["h"]),
        "measuredW": str(comp.get("measuredW", comp["w"])),
        "measuredH": str(comp.get("measuredH", comp["h"])),
        "properties": properties,
    }


def to_clipboard_json(components: List[Dict[str, Any]]) -> str:
    """
    Retourne le JSON lisible (pour affichage/debug dans l'UI).
    """
    controls = [_make_control(c, i) for i, c in enumerate(components)]
    return json.dumps({"controls": controls}, indent=2)


def to_clipboard_bmlf(components: List[Dict[str, Any]]) -> str:
    """
    Retourne la chaîne BMLF prête à coller dans Balsamiq (Ctrl+V).
    Format : 'BMLF' + base64(zlib(JSON))
    """
    controls = [_make_control(c, i) for i, c in enumerate(components)]
    payload = {"controls": controls}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    b64 = base64.b64encode(compressed).decode("ascii")
    return "BMLF" + b64
