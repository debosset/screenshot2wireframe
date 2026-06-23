"""
Bridge WSGI pour Plesk (Phusion Passenger).
Plesk cherche un fichier passenger_wsgi.py à la racine du projet.
"""
import sys
import os

# Ajoute le dossier courant au path Python
sys.path.insert(0, os.path.dirname(__file__))

# Active le virtualenv si présent
venv_path = os.path.join(os.path.dirname(__file__), "venv")
if os.path.exists(venv_path):
    activate = os.path.join(venv_path, "bin", "activate_this.py")
    if os.path.exists(activate):
        exec(open(activate).read(), {"__file__": activate})

from app.main import app
from asgiref.wsgi import WsgiToAsgi

# Passenger attend une variable 'application' WSGI
application = app
