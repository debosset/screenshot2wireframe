# Screenshot → Wireframe Balsamiq

Version corrigée : le bouton de copie ne copie plus le JSON custom, mais le BMML XML généré.

## Lancer en local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Ouvrir : http://localhost:8001

## Correction principale

- `main.py` renvoie maintenant `clipboard_bmml`.
- `bmml_builder.py` expose `build_bmml_string()`.
- `index.html` copie le BMML XML.
- `opencv_analyzer.py` retourne des types courts cohérents (`NavBar`, `Button`, etc.).

Pour Balsamiq Cloud/Confluence, l'import du `.bmml` reste la méthode la plus fiable.
