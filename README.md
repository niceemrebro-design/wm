# WM 2026 — KI-Prediction-System ("Orakel")

Persönliche, KI-gesteuerte Vorhersage-Website für die **FIFA WM 2026** — gebaut, um
das Familien-Tippspiel zu gewinnen. Mehrere LLM-Subagenten analysieren jedes der
104 Spiele auf Basis historischer Daten; ein Synthese-Agent ("Bundestrainer")
trifft die Entscheidung und begründet sie.

**Leitprinzip:** Die KI ist das Gehirn, die Statistik ist ihr Werkzeug — nicht umgekehrt.

📄 **Der vollständige Plan / die Spezifikation steht in [`PLAN.md`](./PLAN.md).**

---

### Kurzüberblick

| Schicht | Technologie |
|---|---|
| Daten | Supabase (Postgres) — Historie, Elo, Fixtures, Features, Predictions |
| ETL & Statistik | Python (pandas, numpy, scipy) — Elo, Poisson/Dixon-Coles, Monte-Carlo |
| KI-Engine | Python + Claude API — Multi-Agenten-System (Opus 4.8 / Sonnet 4.6 / Haiku 4.5) |
| Frontend | Next.js + Tailwind auf Vercel — kein Login |

Status: **Planungsphase.** Siehe Roadmap in `PLAN.md` (Phase 0 = schnell nutzbares
MVP für den nächsten Spieltag, da die WM bereits läuft).
