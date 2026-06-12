# Anzeige-Website

Statische Seite — **kein Build-Tooling, kein Login**. Zeigt die Orakel-Vorhersagen
und die Elo-Kraftrangliste an.

## Lokal ansehen
`web/index.html` einfach im Browser öffnen (lädt `web/data.js` per `<script>`,
funktioniert per Doppelklick).

## Daten aktualisieren
Nach neuen Vorhersagen (`predictions/*.json`) oder frischem Wissensspeicher:
```
python3 engine/build_web.py   # schreibt web/data.js neu
```

## Auf Vercel deployen (2 Minuten)
1. Repo auf [vercel.com](https://vercel.com) importieren.
2. **Root Directory** = `web`, **Framework Preset** = „Other", **Build Command** leer,
   **Output Directory** = `.` (also `web` selbst).
3. Deploy. Fertig — private URL, die nur du kennst. 🤫

(Alternativ GitHub Pages: Branch + Ordner `web` als Quelle.)
