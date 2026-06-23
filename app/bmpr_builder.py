"""
Construit un fichier .bmpr valide (format Balsamiq Mockups 3 / Wireframes).
Le format .bmpr est une base SQLite avec une table 'resources' contenant
du JSON compressé en zlib (base64).
"""
import json
import sqlite3
import zlib
import base64
import time
from typing import List, Dict, Any


# ── Template d'un mockup Balsamiq ────────────────────────────────────────────

MOCKUP_TEMPLATE = {
    "version": "1.0",
    "attributes": {
        "name": "mockup",
        "order": 0,
        "parentID": "__root__",
        "notes": "",
    },
    "mockup": {
        "measuredW": 1000,
        "measuredH": 800,
        "version": "1.0",
        "controls": {
            "control": []
        }
    }
}

PROJECT_TEMPLATE = {
    "version": "1.0",
    "attributes": {
        "name": "New Project",
        "order": 0,
    },
    "mockups": []
}


def _make_control(comp: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Convertit un composant détecté en contrôle Balsamiq."""
    ctrl = {
        "ID": str(index + 1),
        "typeID": comp["type"],
        "x": comp["x"],
        "y": comp["y"],
        "w": comp["w"],
        "h": comp["h"],
        "measuredW": comp.get("measuredW", comp["w"]),
        "measuredH": comp.get("measuredH", comp["h"]),
        "zOrder": index,
        "locked": False,
        "isInGroup": -1,
    }

    # Propriétés par défaut selon le type
    type_id = comp["type"]
    if type_id == "com.balsamiq.mockups::Button":
        ctrl["properties"] = {"text": "Button"}
    elif type_id == "com.balsamiq.mockups::TextInput":
        ctrl["properties"] = {"text": "", "hint": "Placeholder..."}
    elif type_id == "com.balsamiq.mockups::Label":
        ctrl["properties"] = {"text": "Label", "size": "14"}
    elif type_id == "com.balsamiq.mockups::CheckBox":
        ctrl["properties"] = {"text": "Option", "selected": False}
    elif type_id == "com.balsamiq.mockups::NavigationBar":
        ctrl["properties"] = {"text": "Nav Item 1, Nav Item 2, Nav Item 3"}
    elif type_id == "com.balsamiq.mockups::Image":
        ctrl["properties"] = {}
    else:
        ctrl["properties"] = {}

    return ctrl


def _compress_json(data: dict) -> str:
    """Sérialise en JSON puis compresse en zlib base64 (format Balsamiq)."""
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.b64encode(compressed).decode("ascii")


def build_bmpr(
    components: List[Dict[str, Any]],
    output_path: str,
    project_name: str = "Wireframe",
) -> None:
    """
    Génère un fichier .bmpr à partir d'une liste de composants.

    Args:
        components: liste produite par opencv_analyzer.analyze_screenshot()
        output_path: chemin absolu du fichier .bmpr à créer
        project_name: nom du projet affiché dans Balsamiq
    """
    # ── Construction du mockup ───────────────────────────────────────────────
    controls = [_make_control(c, i) for i, c in enumerate(components)]

    mockup = dict(MOCKUP_TEMPLATE)
    mockup["attributes"] = {**MOCKUP_TEMPLATE["attributes"], "name": project_name}
    mockup["mockup"] = {
        **MOCKUP_TEMPLATE["mockup"],
        "controls": {"control": controls},
    }

    # ── Ressources SQLite ────────────────────────────────────────────────────
    # Balsamiq stocke chaque mockup comme une ligne dans la table 'resources'
    # La colonne 'data' contient le JSON compressé zlib + encodé base64

    project_data = {
        "version": "1.0",
        "attributes": {
            "name": project_name,
            "lastUsedTheme": "sketch",
        }
    }

    mockup_resource_id = "mockups/mockup1.bmml"
    project_resource_id = "project.bmpr"

    conn = sqlite3.connect(output_path)
    cur = conn.cursor()

    # Schéma officiel Balsamiq .bmpr
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            ID          TEXT PRIMARY KEY,
            branchID    TEXT NOT NULL DEFAULT 'master',
            parentID    TEXT,
            name        TEXT,
            kind        TEXT,
            data        BLOB,
            thumbnail   BLOB,
            ts          INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            ID      TEXT PRIMARY KEY,
            name    TEXT,
            ts      INTEGER
        )
    """)

    now = int(time.time() * 1000)

    cur.execute(
        "INSERT OR REPLACE INTO branches VALUES (?, ?, ?)",
        ("master", "master", now)
    )

    # Ligne projet
    cur.execute(
        "INSERT OR REPLACE INTO resources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_resource_id,
            "master",
            None,
            project_name,
            "project",
            _compress_json(project_data),
            None,
            now,
        )
    )

    # Ligne mockup
    cur.execute(
        "INSERT OR REPLACE INTO resources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mockup_resource_id,
            "master",
            "__root__",
            project_name,
            "mockup",
            _compress_json(mockup),
            None,
            now,
        )
    )

    conn.commit()
    conn.close()
