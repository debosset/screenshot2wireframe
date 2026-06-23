"""Classification des composants OpenCV vers des contrôles Balsamiq."""

BALSAMIQ_COMPONENTS = {
    "Button": (61, 27),
    "CheckBox": (78, 23),
    "TextInput": (79, 27),
    "TextArea": (200, 100),
    "ComboBox": (120, 27),
    "NavBar": (300, 30),
    "TabBar": (300, 42),
    "Label": (100, 17),
    "Title": (200, 30),
    "Image": (200, 150),
    "Rectangle": (200, 150),
    "FieldSet": (300, 200),
    "DataGrid": (300, 150),
    "HRule": (200, 5),
    "SearchBox": (200, 27),
}


def _short_type(opencv_type: str) -> str:
    if not opencv_type:
        return "Rectangle"
    if "::" in opencv_type:
        opencv_type = opencv_type.split("::", 1)[1]
    if opencv_type == "NavigationBar":
        return "NavBar"
    return opencv_type


def classify(opencv_type: str, x: int, y: int, w: int, h: int, img_w: int = 1000, img_h: int = 800) -> str:
    """Retourne un type court compatible avec bmml_builder.TYPE_MAP."""
    existing = _short_type(opencv_type)
    if existing in BALSAMIQ_COMPONENTS:
        return existing

    ratio = w / h if h > 0 else 1
    area = w * h
    rel_y = y / img_h if img_h else 0

    if rel_y < 0.10 and w > img_w * 0.6 and h < 60:
        return "NavBar"
    if rel_y < 0.20 and w > img_w * 0.5 and 30 <= h <= 55:
        return "TabBar"
    if w > img_w * 0.4 and h < 35 and ratio > 8:
        return "Title"
    if ratio > 20 and h <= 5:
        return "HRule"
    if 4.0 <= ratio <= 14.0 and 20 <= h <= 38:
        return "SearchBox" if w > 250 else "TextInput"
    if 0.8 <= ratio <= 3.5 and 60 <= h <= 200 and 150 <= w <= 500:
        return "TextArea"
    if 1.5 <= ratio <= 5.0 and 20 <= h <= 42 and w <= 200:
        return "Button"
    if 0.6 <= ratio <= 1.8 and area < 2500 and w < 90:
        return "CheckBox"
    if 3.0 <= ratio <= 8.0 and 20 <= h <= 35 and 80 <= w <= 200:
        return "ComboBox"
    if 0.5 <= ratio <= 2.5 and area > 15000:
        return "Image"
    if ratio > 2.0 and h > 80 and w > 200:
        return "DataGrid"
    if area > 30000:
        return "FieldSet"
    if ratio > 5.0 and h < 25:
        return "Label"
    return "Rectangle"
