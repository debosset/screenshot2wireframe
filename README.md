# Screenshot → Wireframe Balsamiq Clipboard

Version corrigée v5.

Cette version ne génère pas de BMML et ne génère pas de BMPR.
Elle génère le JSON `text/plain` compatible avec le copier/coller Balsamiq.

## Correction importante

Le collage échouait avec des typeID risqués comme `NavBar`, `Rectangle`, `SearchBox`, `DataGrid`.
Cette version force uniquement des composants validés/sûrs :

- `Button`
- `TextInput`
- `CheckBox`
- `RadioButton`
- `Label`

## Utilisation

1. Lancer l'application.
2. Mettre le Project ID Balsamiq : `2178941824:2178942175` ou celui du projet cible.
3. Importer/coller un screenshot.
4. Cliquer sur **Copier pour Balsamiq**.
5. Coller dans la page Balsamiq existante avec `Ctrl+V`.
