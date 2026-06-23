# SnapWire — Screenshot vers Clipboard Balsamiq

Version v6.

- Génère un JSON `text/plain` compatible avec le presse-papier Balsamiq.
- Ajoute un mode **Tous les composants Balsamiq connus**.
- Garde un **mode sûr** si certains `typeID` sont refusés par Balsamiq Cloud/Confluence.

## Utilisation

1. Ouvrir Balsamiq et copier un composant existant pour récupérer le `projectID`.
2. Coller le `projectID` dans SnapWire.
3. Importer ou coller un screenshot.
4. Cliquer sur **Analyser le screenshot**.
5. Cliquer sur **Copier pour Balsamiq** puis `Ctrl+V` dans la page Balsamiq cible.

## Conseil

Si le collage échoue avec le mode complet, sélectionner **Mode sûr testé**.
