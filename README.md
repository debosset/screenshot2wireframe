# Screenshot → Wireframe Balsamiq

Convertit n'importe quel screenshot en fichier `.bmpr` ouvrable dans Balsamiq Wireframes.  
**Aucun token IA consommé** — analyse 100% locale via OpenCV.

## Fonctionnement

```
PNG/JPG/WEBP  →  OpenCV (détection contours)  →  classification heuristique  →  .bmpr (SQLite)
```

Composants détectés automatiquement :
- `NavigationBar` — barre de navigation (pleine largeur, haut de page)
- `Button` — boutons (ratio large, petite hauteur)
- `TextInput` — champs de saisie (ratio très large, très plat)
- `CheckBox` — cases à cocher (forme carrée)
- `Image` — zones image/placeholder (grande surface peu détaillée)
- `Label` — textes courts (très plats)
- `Rectangle` — tout autre bloc rectangulaire

---

## Installation sur serveur Plesk (Debian 9+)

### 1. Connexion SSH et préparation

```bash
ssh root@VOTRE_IP

# Vérifier Python
python3 --version   # doit être >= 3.9

# Installer les dépendances système
apt update && apt install -y python3-pip python3-venv libgl1
```

### 2. Cloner le projet

```bash
cd /var/www/vhosts/VOTRE_DOMAINE
git clone https://github.com/VOTRE_COMPTE/screenshot2wireframe.git
cd screenshot2wireframe
```

### 3. Environnement virtuel et dépendances

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Créer les dossiers de travail

```bash
mkdir -p uploads outputs
chmod 755 uploads outputs
```

### 5. Service systemd (démarrage automatique)

```bash
# Éditer le fichier service : remplacer VOTRE_DOMAINE par le vrai domaine
sed -i 's/VOTRE_DOMAINE/monsite.com/g' screenshot2wireframe.service

# Installer le service
cp screenshot2wireframe.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable screenshot2wireframe
systemctl start screenshot2wireframe

# Vérifier
systemctl status screenshot2wireframe
```

### 6. Configuration Nginx dans Plesk

Dans Plesk : **Domaines → VOTRE_DOMAINE → Apache & Nginx → Directives Nginx supplémentaires**

Coller le contenu de `nginx_plesk.conf` dans le champ **nginx**.

Puis : **Appliquer les modifications**.

### 7. Tester

```bash
curl http://localhost:8001/
# Doit répondre avec du HTML
```

Ouvrir `https://VOTRE_DOMAINE` dans le navigateur.

---

## Test local (développement)

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8001
# Ouvrir http://localhost:8001
```

---

## Structure du projet

```
screenshot2wireframe/
├── app/
│   ├── main.py              # FastAPI — routes HTTP
│   ├── opencv_analyzer.py   # Détection OpenCV → liste composants
│   ├── bmpr_builder.py      # Composants → fichier .bmpr (SQLite)
│   └── templates/
│       └── index.html       # Interface web
├── uploads/                 # Screenshots temporaires (auto-supprimés)
├── outputs/                 # Fichiers .bmpr générés
├── requirements.txt
├── passenger_wsgi.py        # Bridge WSGI Plesk
├── start.sh                 # Lancement manuel uvicorn
├── nginx_plesk.conf         # Config Nginx à coller dans Plesk
└── screenshot2wireframe.service  # Service systemd
```

---

## Nettoyage automatique des fichiers

Les fichiers `.bmpr` dans `outputs/` s'accumulent. Ajouter un cron :

```bash
crontab -e
# Supprimer les fichiers de plus de 1h
0 * * * * find /var/www/vhosts/VOTRE_DOMAINE/screenshot2wireframe/outputs -name "*.bmpr" -mmin +60 -delete
```

---

## Dépendances

| Package | Rôle |
|---|---|
| `fastapi` | Framework API |
| `uvicorn` | Serveur ASGI |
| `opencv-python-headless` | Analyse d'image (sans GUI) |
| `numpy` | Calcul matriciel pour OpenCV |
| `python-multipart` | Upload de fichiers |
| `jinja2` | Templates HTML |
| `asgiref` | Bridge WSGI pour Passenger |

---

## Amélioration future : mode hybride IA

Pour les images complexes, on peut ajouter un mode optionnel qui envoie les zones ambiguës à Claude Vision.  
Cela consomme des tokens seulement sur demande explicite de l'utilisateur.
