# WM 2026 — KI-Prediction-System ("Orakel")

> **Persönliche Vorhersage-Website für die FIFA WM 2026.**
> Ziel: durch tiefe, KI-gesteuerte Analyse auf Basis historischer Daten bessere
> Vorhersagen treffen als der Rest der Familie — und damit das Familien-Tippspiel
> gewinnen. Diese Datei ist die **Implementierungs-Spezifikation**: Sie ist so
> geschrieben, dass Codex (oder ein anderer Coding-Agent) sie direkt umsetzen kann.

---

## 0. Leitprinzip (das Wichtigste zuerst)

Das System ist **NICHT maschinell/statistisch**, sondern **AI-gesteuert**:

> **Die KI ist das Gehirn. Die Statistik ist ihr Werkzeug.**

Klassische Tippspiel-Modelle rechnen mechanisch (Elo → Poisson → Ergebnis). Wir
drehen das um: Mehrere **LLM-Subagenten** analysieren je eine Dimension des Spiels
(Form, Historie, Kader, Taktik, Kontext) und ein **Synthese-Agent ("Bundestrainer")**
trifft die eigentliche Entscheidung — er *liest* die statistischen Modelle wie ein
Werkzeug, gewichtet sie gegen qualitative Faktoren (Verletzungen, Motivation,
Reise, Höhe, Stil-Duelle) und begründet seinen Tipp in Klartext.

Der **Vorsprung gegenüber der Familie** entsteht aus drei Dingen, die ein Mensch
am Küchentisch nicht leisten kann:
1. **Tiefe** — jedes der 104 Spiele wird mit derselben Sorgfalt analysiert.
2. **Kalibrierung** — die KI wird gegen echte WM-Historie getestet und ist
   weder über- noch unterheblich selbstsicher (kein "Bauchgefühl").
3. **Überraschungs-Radar** — ein eigener "Advocatus Diaboli"-Agent sucht aktiv
   nach dem Außenseiter-Szenario, das andere übersehen.

---

## 1. Was die Website kann (Scope)

- **Kein Login.** Eigenständige, private Website (nur für dich).
- **Alle 104 Spiele** der WM 2026 (Gruppenphase + komplette K.-o.-Runde inkl. neuem
  Sechzehntelfinale/Round of 32).
- Pro Spiel:
  - **Wahrscheinlichstes Ergebnis** (z. B. 2:1) als Haupt-Tipp.
  - **Sieg/Unentschieden/Niederlage-Wahrscheinlichkeiten** (z. B. 54 % / 26 % / 20 %).
  - **Konfidenz-Level** (wie sicher ist die KI? „Bank" vs. „Münzwurf").
  - **Begründung in Klartext** — warum dieser Tipp? Welche Faktoren waren
    ausschlaggebend? (Das ist der entscheidende Mehrwert.)
  - **Top-3-Alternativergebnisse** mit Wahrscheinlichkeit.
- **Turnier-Ebene:**
  - Projizierte **Gruppentabellen** (wer kommt weiter, wer wird Gruppendritter).
  - **K.-o.-Baum** mit prognostiziertem Verlauf.
  - **Weltmeister-Wahrscheinlichkeiten** für alle 48 Teams (aus Monte-Carlo-Simulation).
- **Aktualisierung pro Spieltag** — vor jedem Spieltag werden die anstehenden
  Spiele neu durchgerechnet (mit den neuesten Ergebnissen, Aufstellungen, Verletzungen).

> ⏰ **Zeitkritisch:** Die WM läuft bereits (Anstoß 11.06.2026, Finale 19.07.2026).
> Deshalb ist der Plan so phasiert, dass schnell ein nutzbares MVP für den
> **nächsten Spieltag** steht (siehe Roadmap, Abschnitt 10).

---

## 2. Systemarchitektur (Überblick)

Vier sauber getrennte Schichten. Die teure KI-Analyse läuft **batchweise im
Hintergrund** (pro Spieltag), die Website liest nur fertige Ergebnisse — dadurch
ist sie schnell und verursacht keine KI-Kosten beim Aufruf.

```
┌──────────────────────────────────────────────────────────────────────┐
│  (1) DATENSCHICHT — Supabase (Postgres)                                │
│  Historische Spiele · Elo-Verlauf · Teams · Fixtures 2026 · Features · │
│  Predictions · Agenten-Berichte · Turnier-Simulation                   │
└───────────────▲───────────────────────────────────────┬───────────────┘
                │ schreibt Features & Predictions        │ liest Predictions
                │                                        │
┌───────────────┴───────────────┐        ┌───────────────▼───────────────┐
│  (2) ETL- & FEATURE-PIPELINE   │        │  (4) FRONTEND — Next.js/Vercel │
│  Python · pandas · numpy       │        │  React · Tailwind · kein Login │
│  Lädt Datenquellen → Supabase  │        │  Match-Karten · Bracket · Odds │
│  Berechnet Elo, Poisson-       │        └────────────────────────────────┘
│  Parameter, Form, Monte-Carlo  │
└───────────────┬────────────────┘
                │ liefert "Daten-Dossier" pro Spiel
                ▼
┌────────────────────────────────────────────────────────────────────────┐
│  (3) KI-PREDICTION-ENGINE — Python + Claude API (Multi-Agenten-System)   │
│                                                                          │
│   Daten-Dossier (geteilt, gecacht)                                       │
│        │                                                                 │
│        ├─► Form-Analyst ──────┐                                          │
│        ├─► Historien-Analyst ─┤                                          │
│        ├─► Kader/Taktik-Analyst ─┤  (Subagenten, parallel)               │
│        ├─► Quant-Analyst ─────┤                                          │
│        ├─► Kontext-Analyst ───┘                                          │
│        │            │                                                    │
│        │            ▼                                                    │
│        │     ┌──────────────┐     ┌──────────────────┐                  │
│        └────►│ BUNDESTRAINER │◄───►│ Advocatus Diaboli │                 │
│              │  (Synthese)   │     │  (Red-Team)       │                 │
│              └──────┬───────┘     └──────────────────┘                  │
│                     ▼                                                     │
│        Finaler Tipp + Wahrscheinlichkeiten + Konfidenz + Begründung      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Die Datenlage (das "super komplexe" Fundament)

Genau hier liegt der Rohstoff für den Vorsprung. Alle Quellen werden in Supabase
zusammengeführt und normalisiert.

| Quelle | Was sie liefert | Verwendung |
|---|---|---|
| **Kaggle: International football results 1872–2026** (martj42) | Jedes Männer-Länderspiel der Geschichte (Datum, Teams, Ergebnis, Turnier, Ort, neutral ja/nein) | Rückgrat für H2H, Form, Leistung auf neutralem Boden |
| **World Football Elo** (eloratings.net / Kaggle-Mirror) | Elo-Verlauf jeder Nation + Vor-Turnier-Elo 2026 aller 48 Teams | Quantitative Stärke-Basisrate |
| **jfjelstul/worldcup** (GitHub) | Komplette WM-Datenbank 1930–heute: Spiele, Tore, Kader, Turnierstruktur | Turnier-Pedigree, historische Muster, K.-o.-Verhalten |
| **API-Football** (api-sports.io) *oder* **football-data.org** | Aktuelle Fixtures 2026, Live-Ergebnisse, Aufstellungen, xG, Quoten | Aktueller Turnierstand, Lineups, Marktquoten als Sanity-Check |
| **FIFA-Weltrangliste** | Offizielles Ranking | Ergänzende Stärke-Information |
| *(optional, Phase 2)* **StatsBomb Open Data** | Event-Level-Daten, tiefes xG | Feinanalyse Schlüsselspiele |

**Abgeleitete Features** (von der Pipeline berechnet, pro Team/Spiel):
- Elo-Differenz, FIFA-Rang-Differenz
- Form: Punkte/Tore/Gegentore der letzten N Spiele, gewichtet (jüngere & wichtigere Spiele zählen mehr)
- H2H-Bilanz der Paarung (gesamt + auf neutralem Boden + bei Turnieren)
- Erwartete Tore (xG-Lambda) je Team via Elo→Tor-Mapping
- Poisson-/Dixon-Coles-Ergebnismatrix (Wahrscheinlichkeit jedes Ergebnisses 0:0 … 5:5)
- Monte-Carlo-Turnierstand (Aufstiegs-/Titelwahrscheinlichkeiten, 10 000+ Simulationen)
- Reise/Ruhe: Tage seit letztem Spiel, Distanz zwischen Spielorten
- Stadion/Kontext: Ort, Höhe (Mexiko-Stadt 2 240 m!), Klima, Heimvorteil (USA/MEX/CAN)

---

## 4. Das KI-Herzstück: Multi-Agenten-System

Pro Spiel läuft folgender Ablauf (orchestriert in Python über die Claude API):

### 4.1 Das geteilte Daten-Dossier
Die Pipeline baut pro Spiel ein **kompaktes, strukturiertes Dossier** (~6–10k Tokens):
alle Features, Form-Tabellen, H2H, Kaderinfos, statistische Modell-Outputs, Kontext.
Dieses Dossier wird **allen Subagenten als gecachter System-Prompt** übergeben
(Prompt Caching, siehe 4.4) — es wird also nur einmal "bezahlt", nicht 7-mal.

### 4.2 Die Subagenten (Analyse, parallel)
Jeder Subagent ist ein fokussierter Claude-Aufruf mit eigenem System-Prompt und
einer klaren Aufgabe. Output jeweils strukturiert (JSON): Einschätzung + Begründung
+ ein Vektor von Tor-Erwartungen + Unsicherheit.

| Subagent | Fokus | Modell | Warum dieses Modell |
|---|---|---|---|
| **Form-Analyst** | Letzte Ergebnisse, Momentum, Müdigkeit, Reise | `claude-haiku-4-5` | Datennah, wenig Abwägung |
| **Historien-Analyst** | H2H, Turnierhistorie, Muster auf neutralem Boden | `claude-sonnet-4-6` | Braucht Kontext-Reasoning |
| **Kader & Taktik-Analyst** | Kaderstärke, Verletzungen/Sperren, Stil-Duell (z. B. Pressing vs. Konter) | `claude-sonnet-4-6` | Anspruchsvolle Abwägung |
| **Quant-Analyst** | Liest Elo/Poisson/Monte-Carlo + Marktquoten, übersetzt sie in Basisraten | `claude-haiku-4-5` | Strukturiert, regelhaft |
| **Kontext-Analyst** | Stadion, Wetter, Höhe, Heimvorteil, Einsatz/Motivation (Muss-Sieg vs. bedeutungsloses Spiel) | `claude-haiku-4-5` | Faktensammlung |

### 4.3 Synthese & Gegenprüfung (Entscheidung)
- **Bundestrainer (Synthese-Agent)** — `claude-opus-4-8`.
  Bekommt das Dossier **plus** alle fünf Subagenten-Berichte. Er ist der eigentliche
  Entscheider: wägt widersprüchliche Signale ab, gewichtet Statistik gegen Qualitatives,
  und produziert den **finalen Tipp**: wahrscheinlichstes Ergebnis, S/U/N-Wahrscheinlichkeiten,
  Konfidenz, Top-3-Ergebnisse und eine **lesbare Begründung**.
  Nutzt **Adaptive Thinking** (`thinking: {type: "adaptive"}`) + `effort: "high"`.
  Bekommt die statistischen Modelle zusätzlich als **Tools** (Tool Use), damit er
  bei Bedarf gezielt nachfragen kann ("zeig mir die Poisson-Matrix für dieses xG").
- **Advocatus Diaboli (Red-Team-Agent)** — `claude-sonnet-4-6`.
  Bekommt den Entwurf des Bundestrainers und argumentiert bewusst dagegen: Wo ist
  die KI zu selbstsicher? Welches Außenseiter-Szenario wird unterschätzt? Der
  Bundestrainer bekommt diese Gegenrede und **revidiert** seinen Tipp final.
  → Das verbessert die **Kalibrierung** spürbar und ist der Kern des
  "Überraschungs-Radars".

### 4.4 Prompt Caching = niedrige Kosten
Das große Daten-Dossier wird als System-Prompt mit
`cache_control: {type: "ephemeral"}` markiert. Der erste Subagent schreibt den
Cache (~1,25× Kosten), alle weiteren Agenten lesen ihn (~0,1× Kosten). Ohne das
würde man die ~8k Token 7-mal voll bezahlen.

> Architektur-Tier: Das ist ein **code-orchestrierter Workflow** (Claude API +
> Tool Use), kein server-managed Agent — wir kontrollieren die Schleife selbst,
> was für eine deterministische Batch-Pipeline genau richtig (und am günstigsten) ist.
> Konzeptionell entspricht es dem Subagenten-Muster des Claude Agent SDK
> (Hauptloop = Opus, günstige Subagenten = Haiku).

---

## 5. Statistik als Werkzeug (nicht als Entscheider)

Diese Modelle laufen in der Pipeline und liefern dem Quant-Analysten/Bundestrainer
ihre Zahlen — sie *entscheiden* aber nichts:

- **Elo-Modell** — Stärke jeder Nation, kontinuierlich aus der Historie aktualisiert
  (Siege gegen starke Gegner bei wichtigen Spielen zählen mehr als Freundschaftsspiele).
- **Elo → erwartete Tore (λ)** — Mapping der Elo-Differenz auf Tor-Erwartungswerte.
- **Poisson / Dixon-Coles** — Wahrscheinlichkeit jedes konkreten Ergebnisses; Dixon-Coles
  korrigiert die bekannte Unterschätzung knapper Unentschieden (0:0, 1:1).
- **Monte-Carlo-Turniersimulation** — simuliert den kompletten Turnierbaum 10 000+ mal
  → Aufstiegs- und Titelwahrscheinlichkeiten.

Bewährte, in der Forschung etablierte Methodik — aber bei uns nur **Input** für die KI.

---

## 6. Datenmodell (Supabase / Postgres)

Vorgeschlagenes Schema (RLS: öffentlicher **Lese**-Zugriff für die Website, Schreiben
nur via Service-Key aus der Pipeline):

```
teams(id, name, fifa_code, confederation, fifa_rank, elo_current, ...)
historical_matches(id, date, home_team, away_team, home_score, away_score,
                   tournament, neutral, city, country)
elo_history(team_id, date, elo)
fixtures_2026(id, matchday, stage, group, date_utc, venue_id, home_team, away_team,
              status, home_score, away_score)
venues(id, city, country, altitude_m, climate)
features(fixture_id, json)              -- berechnetes Daten-Dossier pro Spiel
agent_reports(fixture_id, agent, model, json, created_at)
predictions(fixture_id, predicted_home, predicted_away, p_home, p_draw, p_away,
            confidence, top3 json, reasoning text, model_version, created_at)
tournament_sim(run_at, team_id, p_advance, p_quarter, p_semi, p_final, p_winner)
```

---

## 7. Tech-Stack (konkret)

- **Datenbank:** Supabase (Postgres + Auto-REST + JS-Client).
- **ETL/Feature-Pipeline:** Python 3.11+, `pandas`, `numpy`, `scipy`, `supabase-py`.
- **Statistik:** eigenes Elo-Modul, `scipy.stats` (Poisson/Dixon-Coles), Monte-Carlo (numpy).
- **KI-Engine:** Python + `anthropic` SDK.
  - Synthese/Entscheidung: `claude-opus-4-8`
  - Reasoning-Subagenten: `claude-sonnet-4-6`
  - Daten-/Struktur-Subagenten: `claude-haiku-4-5`
  - Adaptive Thinking + `effort` + Prompt Caching + strukturierte Outputs (`output_config.format`).
- **Frontend:** Next.js (React) + TypeScript + Tailwind, Deployment auf **Vercel**.
  Liest Predictions direkt aus Supabase (anon read-only Key). Kein Login.
- **Orchestrierung/Scheduling:** Pipeline läuft on-demand oder per **GitHub Actions**
  (Cron) vor jedem Spieltag; schreibt fertige Predictions nach Supabase.
- **Secrets (ENV):** `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
  (Pipeline) bzw. `NEXT_PUBLIC_SUPABASE_ANON_KEY` (Frontend), `FOOTBALL_API_KEY`.

---

## 8. Kosten (realistisch)

Dank Prompt Caching und Modell-Mix (viel Haiku, gezielt Sonnet/Opus):

- **Pro Spiel:** grob **0,10–0,30 $** (7 Agenten-Aufrufe, geteiltes gecachtes Dossier).
- **Komplettes Turnier (104 Spiele):** **wenige bis ~20–30 $**, selbst wenn pro
  Spieltag mehrfach neu gerechnet wird.

Aktuelle Modellpreise (pro 1 Mio Tokens In/Out): Opus 4.8 $5/$25 · Sonnet 4.6 $3/$15
· Haiku 4.5 $1/$5. → Für einen echten Vorteil im Familien-Tippspiel
vernachlässigbar.

---

## 9. Kalibrierung & Qualität (woher der echte Vorsprung kommt)

Eine Vorhersage ist nur dann ein Vorteil, wenn sie *gut kalibriert* ist. Deshalb:

- **Backtesting:** System gegen WM 2018 & 2022 (und EMs) laufen lassen, Ergebnisse
  mit den echten Resultaten vergleichen.
- **Metriken:** **Brier-Score** und **Log-Loss** für die Wahrscheinlichkeiten,
  Trefferquote für Tendenz/Ergebnis, Kalibrierungs-Diagramm (sagt die KI „60 %",
  passiert es auch in ~60 % der Fälle?).
- **Anti-Überheblichkeit:** Der Advocatus-Diaboli-Schritt + explizite
  Konfidenz-Ausgabe verhindern, dass die KI Außenseiter chronisch unterschätzt
  (der häufigste Fehler menschlicher Tipper *und* naiver Modelle).
- **Ehrliche Unsicherheit:** Bei echten Münzwurf-Spielen sagt das System das auch
  — und du kannst entscheiden, dort auf Sicherheit zu tippen.

---

## 10. Roadmap (auf die laufende WM zugeschnitten)

**Phase 0 — MVP für den nächsten Spieltag (Priorität: Geschwindigkeit)**
- Supabase aufsetzen, Kern-Tabellen anlegen.
- Historische Ergebnisse + Elo + Fixtures 2026 importieren.
- Minimal-Feature-Dossier + Elo/Poisson berechnen.
- **Einstufige** KI-Vorhersage (nur Bundestrainer-Agent über das Dossier) für die
  anstehenden Spiele.
- Simple Next.js-Seite mit Match-Karten (Ergebnis-Tipp + Wahrscheinlichkeiten +
  Begründung). → **Sofort nutzbar.**

**Phase 1 — Volle Datenlage**
- Alle Quellen anbinden (jfjelstul WM-DB, API-Football für Lineups/xG/Quoten, FIFA-Rang).
- Reichhaltiges Feature-Dossier (Form gewichtet, H2H neutral, Reise, Höhe, Kontext).

**Phase 2 — Multi-Agenten-Tiefe**
- Alle 5 Subagenten + Bundestrainer + Advocatus Diaboli, mit Prompt Caching.
- Statistik-Tools als Tool-Use für den Bundestrainer.

**Phase 3 — Turnier-Ebene & Politur**
- Monte-Carlo-Turniersimulation → Gruppentabellen, Bracket, Weltmeister-Odds.
- Frontend: Bracket-Ansicht, Titel-Odds, Konfidenz-Badges, Filter nach Spieltag.
- Backtesting-Report + Kalibrierungs-Dashboard.

**Phase 4 — Automatisierung**
- GitHub-Action: rechnet automatisch vor jedem Spieltag neu und aktualisiert Supabase.

---

## 11. Wie du damit gewinnst (Zusammenfassung des Edge)

1. **Jedes** der 104 Spiele wird gleich tief analysiert — keine Ermüdung, keine
   Lieblingsmannschafts-Verzerrung.
2. Faktoren, die Menschen am Tisch übersehen: Höhe in Mexiko-Stadt, Reisedistanzen,
   versteckte H2H-Muster, Stil-Duelle, Einsatz-Situationen ("Gruppe schon durch").
3. **Kalibrierte** Wahrscheinlichkeiten statt Bauchgefühl + aktives Außenseiter-Radar.
4. Klartext-Begründung pro Spiel → du verstehst *warum* und kannst souverän tippen.

---

## 12. Risiken & offene Punkte

- **Datenqualität 2026:** Free-Tier-APIs haben Limits/Verzögerungen — ggf. einen
  bezahlten API-Football-Plan (günstig) für Lineups/xG einplanen.
- **Team-Namens-Mapping** zwischen den Quellen muss sauber normalisiert werden.
- **Neue Turnierstruktur 2026** (Round of 32, 8 beste Gruppendritte) korrekt in der
  Monte-Carlo-Simulation abbilden.
- **Nur für dich:** keine öffentliche Verbreitung der Tipps, sonst ist der Vorteil
  gegenüber der Familie weg. 😉

---

## 13. Nächste Schritte

1. **Diesen Plan freigeben / anpassen.**
2. Entscheiden: baue **ich** das MVP (Phase 0) jetzt direkt, oder übergibst du
   diese Spezifikation an Codex?
3. Supabase-Projekt + Anthropic-API-Key + (optional) Football-API-Key bereitstellen.
4. Phase 0 umsetzen → erste Vorhersagen für den nächsten Spieltag.
