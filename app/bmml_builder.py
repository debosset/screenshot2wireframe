"""
Génère un fichier .bmml (XML Balsamiq Mockups 2).
Le même XML est renvoyé au navigateur pour pouvoir être copié.
"""
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Any, Dict, List

TYPE_MAP = {
    "NavBar": "com.balsamiq.mockups::NavBar",
    "NavigationBar": "com.balsamiq.mockups::NavBar",
    "TabBar": "com.balsamiq.mockups::TabBar",
    "Button": "com.balsamiq.mockups::Button",
    "ButtonBar": "com.balsamiq.mockups::ButtonBar",
    "CheckBox": "com.balsamiq.mockups::CheckBox",
    "TextInput": "com.balsamiq.mockups::TextInput",
    "TextArea": "com.balsamiq.mockups::TextArea",
    "ComboBox": "com.balsamiq.mockups::ComboBox",
    "Label": "com.balsamiq.mockups::Label",
    "Title": "com.balsamiq.mockups::Title",
    "Image": "com.balsamiq.mockups::Image",
    "Rectangle": "com.balsamiq.mockups::Rectangle",
    "FieldSet": "com.balsamiq.mockups::FieldSet",
    "DataGrid": "com.balsamiq.mockups::DataGrid",
    "HRule": "com.balsamiq.mockups::HRule",
    "SearchBox": "com.balsamiq.mockups::SearchBox",
    "Paragraph": "com.balsamiq.mockups::Paragraph",
    "Icon": "com.balsamiq.mockups::Icon",
    "Link": "com.balsamiq.mockups::Link",
}

PROPS = {
    "com.balsamiq.mockups::Button": {"text": "Button"},
    "com.balsamiq.mockups::TextInput": {"text": "", "hint": "Placeholder..."},
    "com.balsamiq.mockups::TextArea": {"text": ""},
    "com.balsamiq.mockups::Label": {"text": "Label"},
    "com.balsamiq.mockups::Title": {"text": "Title"},
    "com.balsamiq.mockups::NavBar": {"text": "Home, About, Contact"},
    "com.balsamiq.mockups::TabBar": {"text": "Tab 1, Tab 2, Tab 3"},
    "com.balsamiq.mockups::CheckBox": {"text": "Option"},
    "com.balsamiq.mockups::ComboBox": {"text": "Option 1\nOption 2\nOption 3"},
    "com.balsamiq.mockups::SearchBox": {"text": "", "hint": "Search..."},
}


def _normalise_type(type_id: str) -> str:
    if not type_id:
        return "com.balsamiq.mockups::Rectangle"
    if type_id.startswith("com.balsamiq.mockups::"):
        short = type_id.split("::", 1)[1]
        return TYPE_MAP.get(short, type_id)
    return TYPE_MAP.get(type_id, "com.balsamiq.mockups::Rectangle")


def build_bmml_string(components: List[Dict[str, Any]], name: str = "Wireframe") -> str:
    mockup_w = max((int(c["x"]) + int(c["w"]) for c in components), default=1000)
    mockup_h = max((int(c["y"]) + int(c["h"]) for c in components), default=800)

    root = ET.Element(
        "mockup",
        {
            "version": "1.0",
            "skin": "sketch",
            "measuredW": str(mockup_w),
            "measuredH": str(mockup_h),
            "mockupW": str(mockup_w),
            "mockupH": str(mockup_h),
        },
    )
    controls = ET.SubElement(root, "controls")

    for i, comp in enumerate(components):
        tid_long = _normalise_type(comp.get("typeID") or comp.get("type") or "Rectangle")
        ctrl = ET.SubElement(
            controls,
            "control",
            {
                "controlID": str(i + 1),
                "controlTypeID": tid_long,
                "x": str(int(comp["x"])),
                "y": str(int(comp["y"])),
                "w": str(int(comp["w"])),
                "h": str(int(comp["h"])),
                "measuredW": str(int(comp.get("measuredW", comp["w"]))),
                "measuredH": str(int(comp.get("measuredH", comp["h"]))),
                "zOrder": str(i),
                "locked": "false",
                "isInGroup": "-1",
            },
        )

        props = PROPS.get(tid_long, {})
        if props:
            props_el = ET.SubElement(ctrl, "controlProperties")
            for k, v in props.items():
                el = ET.SubElement(props_el, k)
                el.text = v

    ET.indent(root, space="  ")
    buffer = BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    return buffer.getvalue().decode("utf-8")


def build_bmml(components: List[Dict[str, Any]], output_path: str, name: str = "Wireframe") -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(build_bmml_string(components, name))
