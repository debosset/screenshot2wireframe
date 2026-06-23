"""
Génère le JSON format presse-papier Balsamiq.
Dans Balsamiq : Edit > Paste (Ctrl+V) colle directement les composants.
"""
import json
from typing import List, Dict, Any

TYPE_MAP = {
    "com.balsamiq.mockups::Button": "com.balsamiq.mockups::Button",
    "com.balsamiq.mockups::TextInput": "com.balsamiq.mockups::TextInput",
    "com.balsamiq.mockups::Label": "com.balsamiq.mockups::Label",
    "com.balsamiq.mockups::CheckBox": "com.balsamiq.mockups::CheckBox",
    "com.balsamiq.mockups::Image": "com.balsamiq.mockups::Image",
    "com.balsamiq.mockups::NavigationBar": "com.balsamiq.mockups::NavBar",
    "com.balsamiq.mockups::Rectangle": "com.balsamiq.mockups::Rectangle",
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
    Format exact attendu par Balsamiq pour le collage presse-papier.
    Source : https://support.balsamiq.com/resources/mockupjson/
    """
    controls = [_make_control(c, i) for i, c in enumerate(components)]
    payload = {
        "controls": controls,
        "controlsVersion": "1.0",
        "metadata": {
            "clipboardVersion": "1.0"
        }
    }
    return json.dumps(payload, indent=2)
