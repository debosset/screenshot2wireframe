# Screenshot → Clipboard Balsamiq

Cette version ne génère ni BMML ni BMPR.
Elle génère le JSON `text/plain` utilisé par Balsamiq lors d'un `Ctrl+C` sur un composant.

Workflow :

1. Importer/coller un screenshot.
2. Renseigner le `projectID` Balsamiq.
3. Cliquer sur **Copier pour Balsamiq**.
4. Aller dans la page Balsamiq existante et faire `Ctrl+V`.

Le format généré suit l'exemple réel :

```json
{
  "mockup": {
    "controls": { "control": [] },
    "attributes": { "name": "New Wireframe 1", "order": 123, "parentID": null, "notes": null },
    "branchID": "Master",
    "resourceID": "UUID",
    "mockupH": "...",
    "mockupW": "...",
    "measuredW": "...",
    "measuredH": "...",
    "version": "1.0",
    "calloutsOffset": { "x": 0, "y": 0 }
  },
  "groupOffset": { "x": 0, "y": 0 },
  "dependencies": [],
  "projectID": "..."
}
```
