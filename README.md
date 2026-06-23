# Screenshot → Wireframe Balsamiq

Convertit un screenshot PNG/JPG/WEBP/GIF en fichier `.bmml` importable dans Balsamiq Wireframes.

## Important

Le copier-coller direct de XML/JSON dans Balsamiq Confluence colle souvent le contenu comme un bloc de texte.
La méthode fiable est donc :

1. générer le `.bmml` ;
2. télécharger le fichier ;
3. dans Balsamiq : `Project / Import / Import BMML` ;
4. sélectionner le fichier `.bmml`.

## Lancement local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Ouvrir ensuite : `http://localhost:8001`.

## Structure

```text
app/main.py              API FastAPI
app/opencv_analyzer.py   Détection OpenCV
app/bmml_builder.py      Génération BMML XML
app/templates/index.html Interface web
```
