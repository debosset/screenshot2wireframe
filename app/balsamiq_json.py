import json, uuid
from typing import List, Dict, Any

MEASURED = {
    "Title":       (300, 30), "SubTitle":    (250, 24), "Label":       (100, 17),
    "Link":        (150, 17), "TextInput":   (79,  27), "TextArea":    (200, 100),
    "Button":      (61,  27), "ButtonBar":   (159, 27), "CheckBox":    (100, 23),
    "RadioButton": (97,  23), "HRule":       (100, 10), "Rectangle":   (200, 150),
    "FieldSet":    (300, 200),"Image":       (200, 150),
}

def to_clipboard_json(components: List[Dict[str, Any]], project_id: str = "0:1", **kwargs) -> str:
    controls = []
    for i, c in enumerate(components):
        tid = c.get("typeID", "Rectangle")
        mw, mh = MEASURED.get(tid, (c.get("w", 100), c.get("h", 20)))
        ctrl = {
            "ID": str(i),
            "typeID": tid,
            "zOrder": str(i),
            "measuredW": str(mw),
            "measuredH": str(mh),
            "x": str(c.get("x", 0)),
            "y": str(c.get("y", 0)),
        }
        if tid in {"TextInput","TextArea","ButtonBar","Rectangle","FieldSet","Image","HRule"}:
            w = c.get("w", mw)
            h = c.get("h", mh)
            if w != mw: ctrl["w"] = str(w)
            if h != mh: ctrl["h"] = str(h)
        # Passer les properties si présentes
        props = c.get("properties")
        if props:
            ctrl["properties"] = props
        controls.append(ctrl)

    max_w = max((int(c.get("x",0)) + int(c.get("w", MEASURED.get(c.get("typeID","Rectangle"),(200,150))[0]))) for c in components) if components else 1000
    max_h = max((int(c.get("y",0)) + int(c.get("h", MEASURED.get(c.get("typeID","Rectangle"),(200,150))[1]))) for c in components) if components else 800

    return json.dumps({
        "mockup": {
            "controls": {"control": controls},
            "attributes": {"name": "New Wireframe 1", "order": 938428.5264654435, "parentID": None, "notes": None},
            "branchID": "Master",
            "resourceID": str(uuid.uuid4()).upper(),
            "mockupH": str(max_h),
            "mockupW": str(max_w),
            "measuredW": str(max_w),
            "measuredH": str(max_h),
            "version": "1.0",
            "calloutsOffset": {"x": 0, "y": 0},
        },
        "groupOffset": {"x": 0, "y": 0},
        "dependencies": [],
        "projectID": project_id,
    }, indent=2)

def classify(*args, **kwargs):
    return "Rectangle"
