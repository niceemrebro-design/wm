# WM 2026 — KI-Prediction-System ("Orakel")

Persönliche, KI-gesteuerte Vorhersage-Website für die **FIFA WM 2026** — gebaut, um
das Familien-Tippspiel zu gewinnen. Pro Spiel liefert sie die **3 wahrscheinlichsten
Wett-Tipps (BWIN-Stil)** — Sieger / Doppelte Chance / Über-Unter / Beide treffen —
statt unsicherer exakter Ergebnisse. Mehrere Analyse-Brillen (Form · Historie/H2H ·
Qualität/Elo · Kontext · Statistik-Modell) urteilen, eine Advocatus-Diaboli-Gegenprobe
prüft auf Überraschungen. **Jede Vorhersage legt offen, worauf sie beruht.**

Blind-Backtest (WM 2018+2022, 128 Spiele): **Doppelte Chance 79 % · bester Top-Tipp 78 %**
— gegenüber nur 13 % für exakte Ergebnisse.

**Leitprinzip:** Die KI ist das Gehirn, die Statistik ist ihr Werkzeug — nicht umgekehrt.

📄 Vollständige Spezifikation: **[`PLAN.md`](./PLAN.md)**

---

## Was gebaut ist

| Schicht | Stand |
|---|---|
| **Wissensspeicher** (`data/processed/`) | ✅ 49k Länderspiele 1872–2026 → kompakte Artefakte (Elo, Form, H2H, Fixtures) |
| **Statistik-Engine** (`engine/`) | ✅ Elo · Poisson/Dixon-Coles · **2-stufig kalibriert** (1X2 + Tore separat) · Monte-Carlo-Turniersim |
| **Wett-Märkte** (`engine/markets.py`) | ✅ 1X2 · Doppelte Chance · Über/Unter · BTTS → die 3 wahrscheinlichsten Tipps pro Spiel |
| **Vorhersagen** (`predictions/all.json`) | ✅ alle 72 Gruppenspiele, je 3 Top-Tipps + transparenter `basis`-Block; 22 Orakel-verfeinert |
| **Bilanz** (`predictions/scorecard.json`, `backtest.json`) | ✅ Live-Trefferquote (nur vor Anpfiff eingefrorene Tipps) + Track Record gegen WM 2018/22 |
| **Titel-Odds** (`predictions/tournament.json`) | ✅ Weltmeister-Wahrscheinlichkeiten (Spanien ~28 %, Argentinien ~20 %, …) |
| **Website** (`web/`) | ✅ statisch, kein Login — Top-Tipps + Bilanz + Titel-Odds + Elo-Rangliste |
| **Automatik** (`.github/workflows/`) | ✅ GitHub-Action (alle 2 h): Daten ziehen, neu rechnen, pushen — Vercel deployt selbst |

Die KI (Claude) ist das Orakel **auf Befehl**: Sie zieht pro Spiel nur die relevante
Datenscheibe aus dem Repo, urteilt und schreibt die Vorhersage zurück. Kein
laufender Dienst, kein API-Key, keine Datenbank — token-sparend.

---

## Betrieb

**Neu rechnen (nach neuen Ergebnissen):**
```
python3 engine/refresh.py        # Daten → Store → Vorhersagen → Turniersim → Web
git add -A && git commit -m "Update" && git push
```
Optionen: `--no-fetch` (ohne Download), `--calibrate` (Modell neu kalibrieren).

**Einzelschritte:**
```
python3 engine/ingest.py        # Rohdaten laden (data/raw, gitignored)
python3 engine/build_store.py   # Wissensspeicher neu bauen
python3 engine/calibrate.py     # Modell kalibrieren -> engine/params.json
python3 engine/predict.py       # Vorhersagen -> predictions/all.json
python3 engine/montecarlo.py    # Titel-Odds -> predictions/tournament.json
python3 engine/build_web.py     # Web-Daten -> web/data.js
python3 engine/upcoming.py 10   # Reasoning-Briefing für die nächsten Spiele (für das Orakel)
python3 engine/selfcheck.py     # schneller Smoke-Test
```

**Website ansehen / deployen:** siehe [`web/README.md`](./web/README.md) (lokal
öffnen oder in 2 Min auf Vercel, Root = `web`).

**Frische Sessions:** Ein SessionStart-Hook (`.claude/hooks/session-start.sh`)
installiert die Abhängigkeiten automatisch (async, nicht blockierend).

---

## Wie das Orakel einen Spieltag tippt
1. `python3 engine/refresh.py --no-fetch` (oder gezielt) erzeugt das Briefing.
2. Claude liest `engine/upcoming.py`-Briefing (nur relevante Scheibe je Spiel),
   urteilt durch die Analyse-Brillen + Advocatus Diaboli und legt verfeinerte
   Tipps als `predictions/oracle_*.json` ab.
3. `engine/predict.py` mischt Orakel-Urteile über die Engine-Baseline; `build_web.py`
   aktualisiert die Anzeige.

Nur für den privaten Gebrauch. 🤫
