"""
Génère un fichier .bmml (XML Balsamiq Mockups 2) — format garanti importable.
File > Import > Import Mockup JSON/BMML dans Balsamiq Wireframes.
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import os

TYPE_MAP = {
    "NavBar":      "com.balsamiq.mockups::NavBar",
    "TabBar":      "com.balsamiq.mockups::TabBar",
    "Button":      "com.balsamiq.mockups::Button",
    "ButtonBar":   "com.balsamiq.mockups::ButtonBar",
    "CheckBox":    "com.balsamiq.mockups::CheckBox",
    "TextInput":   "com.balsamiq.mockups::TextInput",
    "TextArea":    "com.balsamiq.mockups::TextArea",
    "ComboBox":    "com.balsamiq.mockups::ComboBox",
    "Label":       "com.balsamiq.mockups::Label",
    "Title":       "com.balsamiq.mockups::Title",
    "Image":       "com.balsamiq.mockups::Image",
    "Rectangle":   "com.balsamiq.mockups::Rectangle",
    "FieldSet":    "com.balsamiq.mockups::FieldSet",
    "DataGrid":    "com.balsamiq.mockups::DataGrid",
    "HRule":       "com.balsamiq.mockups::HRule",
    "SearchBox":   "com.balsamiq.mockups::SearchBox",
    "Paragraph":   "com.balsamiq.mockups::Paragraph",
    "Icon":        "com.balsamiq.mockups::Icon",
    "Link":        "com.balsamiq.mockups::Link",
}

PROPS = {
    "com.balsamiq.mockups::Button":    {"text": "Button"},
    "com.balsamiq.mockups::TextInput": {"hint": "Placeholder..."},
    "com.balsamiq.mockups::Label":     {"text": "Label"},
    "com.balsamiq.mockups::Title":     {"text": "Title"},
    "com.balsamiq.mockups::NavBar":    {"text": "Home, About, Contact"},
    "com.balsamiq.mockups::TabBar":    {"text": "Tab 1, Tab 2, Tab 3"},
    "com.balsamiq.mockups::CheckBox":  {"text": "Option"},
    "com.balsamiq.mockups::ComboBox":  {"text": "Option 1\nOption 2\nOption 3"},
    "com.balsamiq.mockups::SearchBox": {"hint": "Search..."},
}

def build_bmml(components: List[Dict[str, Any]], output_path: str, name: str = "Wireframe") -> None:
    root = ET.Element("mockup", {
        "version": "1.0",
        "skin": "sketch",
        "measuredW": "1000",
        "measuredH": "800",
        "mockupW": "1000",
        "mockupH": "800",
    })
    controls = ET.SubElement(root, "controls")

    for i, comp in enumerate(components):
        tid_short = comp.get("typeID", comp.get("type", "Rectangle"))
        # Si c'est un type OpenCV, on le classifie
        if "::" not in tid_short and "com." not in tid_short:
            tid_long = TYPE_MAP.get(tid_short, "com.balsamiq.mockups::Rectangle")
        else:
            tid_long = tid_short

        ctrl = ET.SubElement(controls, "control", {
            "controlID": str(i),
            "controlTypeID": tid_long,
            "x": str(comp["x"]),
            "y": str(comp["y"]),
            "w": str(comp["w"]),
            "h": str(comp["h"]),
            "measuredW": str(comp.get("measuredW", comp["w"])),
            "measuredH": str(comp.get("measuredH", comp["h"])),
            "zOrder": str(i),
            "locked": "false",
            "isInGroup": "-1",
        })

        props = PROPS.get(tid_long, {})
        if props:
            props_el = ET.SubElement(ctrl, "controlProperties")
            for k, v in props.items():
                el = ET.SubElement(props_el, k)
                el.text = v

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with open(output_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
