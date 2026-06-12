"""
Baut den kompakten Wissensspeicher (data/processed/) aus den Rohdaten.

Output (alles self-contained, committet — kein Rohdaten-Zugriff zur Vorhersagezeit noetig):
  elo.json            -> {team: {elo, matches}}
  fixtures_2026.json  -> Liste aller WM-2026-Spiele (Plan + bereits gespielte Ergebnisse)
  forms.json          -> {team: [letzte 10 echte Spiele]}  (nur die 48 Teilnehmer)
  h2h.json            -> {fixture_id: H2H-Zusammenfassung der Paarung}
  meta.json           -> Stand/Quellen
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

from util import results_csv_path, DATA_PROC, is_neutral
from elo import compute_elo


def _team_perspective_game(row, team):
    home = row.home_team == team
    gf = row.home_score if home else row.away_score
    ga = row.away_score if home else row.home_score
    opp = row.away_team if home else row.home_team
    res = "W" if gf > ga else ("D" if gf == ga else "L")
    return {
        "date": row.date.strftime("%Y-%m-%d"),
        "opp": opp, "gf": int(gf), "ga": int(ga), "res": res,
        "venue": "H" if home else "A", "comp": row.tournament,
    }


def h2h_summary(played, home, away):
    m = played[((played.home_team == home) & (played.away_team == away)) |
               ((played.home_team == away) & (played.away_team == home))]
    w = d = l = gf = ga = 0
    for r in m.itertuples(index=False):
        if r.home_team == home:
            hgf, hga = r.home_score, r.away_score
        else:
            hgf, hga = r.away_score, r.home_score
        gf += hgf; ga += hga
        if hgf > hga: w += 1
        elif hgf == hga: d += 1
        else: l += 1
    last = [{
        "date": r.date.strftime("%Y-%m-%d"),
        "score": f"{int(r.home_score)}:{int(r.away_score)}",
        "home": r.home_team, "away": r.away_team,
    } for r in m.sort_values("date").tail(5).itertuples(index=False)]
    return {"meetings": int(len(m)), "home_persp_w": w, "draw": d, "home_persp_l": l,
            "gf": int(gf), "ga": int(ga), "last": last}


def main():
    os.makedirs(DATA_PROC, exist_ok=True)
    df = pd.read_csv(results_csv_path())
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    played = df.dropna(subset=["home_score", "away_score"]).sort_values("date").copy()
    played["home_score"] = played["home_score"].astype(int)
    played["away_score"] = played["away_score"].astype(int)

    # --- Elo aus kompletter Historie ---
    rows = played[["home_team", "away_team", "home_score", "away_score",
                   "tournament", "neutral"]].to_dict("records")
    elo, counts = compute_elo(rows)
    teams = {t: {"elo": round(elo[t], 1), "matches": int(counts.get(t, 0))}
             for t in sorted(elo)}
    json.dump(teams, open(os.path.join(DATA_PROC, "elo.json"), "w"),
              ensure_ascii=False, indent=1)

    # --- WM-2026-Spiele ---
    wc = df[(df["tournament"] == "FIFA World Cup") &
            (df["date"].dt.year == 2026)].sort_values("date")
    fixtures = []
    for i, r in enumerate(wc.itertuples(index=False)):
        done = pd.notna(r.home_score)
        fixtures.append({
            "id": f"wc2026-{i:03d}",
            "date": r.date.strftime("%Y-%m-%d"),
            "home": r.home_team, "away": r.away_team,
            "city": r.city, "country": r.country, "neutral": is_neutral(r.neutral),
            "played": bool(done),
            "home_score": int(r.home_score) if done else None,
            "away_score": int(r.away_score) if done else None,
        })
    json.dump(fixtures, open(os.path.join(DATA_PROC, "fixtures_2026.json"), "w"),
              ensure_ascii=False, indent=1)

    # --- Form (letzte 10 echte Spiele je Teilnehmer) ---
    participants = sorted(set(wc["home_team"]) | set(wc["away_team"]))
    forms = {}
    for t in participants:
        sub = played[(played.home_team == t) | (played.away_team == t)].tail(10)
        forms[t] = [_team_perspective_game(r, t) for r in sub.itertuples(index=False)]
    json.dump(forms, open(os.path.join(DATA_PROC, "forms.json"), "w"),
              ensure_ascii=False, indent=1)

    # --- H2H je geplanter Paarung ---
    h2h = {f["id"]: h2h_summary(played, f["home"], f["away"]) for f in fixtures}
    json.dump(h2h, open(os.path.join(DATA_PROC, "h2h.json"), "w"),
              ensure_ascii=False, indent=1)

    # --- Meta ---
    json.dump({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "martj42/international_results",
        "n_historical_matches": int(len(played)),
        "history_range": [played["date"].min().strftime("%Y-%m-%d"),
                          played["date"].max().strftime("%Y-%m-%d")],
        "n_fixtures_2026": len(fixtures),
        "n_participants": len(participants),
    }, open(os.path.join(DATA_PROC, "meta.json"), "w"), ensure_ascii=False, indent=1)

    # --- Verifikation ---
    top = sorted(teams.items(), key=lambda kv: -kv[1]["elo"])[:15]
    print("Top 15 Elo (Sanity-Check):")
    for t, v in top:
        print(f"  {v['elo']:.0f}  {t}")
    print(f"\nGeschrieben: elo({len(teams)}) fixtures({len(fixtures)}) "
          f"forms({len(forms)}) h2h({len(h2h)}) -> {DATA_PROC}")


if __name__ == "__main__":
    main()
