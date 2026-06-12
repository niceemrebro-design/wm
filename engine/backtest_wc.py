"""
WM-Backtest: Die Engine tippt die WM 2018 und WM 2022 'blind' — mit exakt dem
Elo-Stand vom Tag vor jedem Spiel (kein Look-ahead) und den kalibrierten
Parametern. Danach wird gegen die echten Ergebnisse gewertet.

Wertung je Spiel (Tipp = wahrscheinlichstes Ergebnis des Modells):
  exakt getroffen / richtige Tordifferenz / richtige Tendenz / daneben
  + Kicktipp-Punkte (4/3/2/0) + Brier/LogLoss der Wahrscheinlichkeiten.

Output: predictions/backtest.json  (Track Record fuer die Website)
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

from util import results_csv_path, PRED_DIR, is_neutral
from elo import START, HOME_ADV_ELO, k_factor, gd_multiplier
from predict import pick_scoreline
import model


def grade(pick, res):
    ph, pa = pick
    rh, ra = res
    if (ph, pa) == (rh, ra):
        return "exakt", 4
    if ph - pa == rh - ra:
        return "tordifferenz", 3
    if (ph > pa) == (rh > ra) and (ph == pa) == (rh == ra):
        return "tendenz", 2
    return "daneben", 0


def main():
    df = pd.read_csv(results_csv_path())
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"]).sort_values("date")
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    targets = {2018: [], 2022: []}
    R = {}
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        Rh, Ra = R.get(h, START), R.get(a, START)
        neutral = is_neutral(r.neutral)
        hs, as_ = r.home_score, r.away_score

        if r.tournament == "FIFA World Cup" and r.date.year in targets:
            lh, la = model.elo_to_lambdas(Rh, Ra, neutral)
            M = model.score_matrix(lh, la)
            ph, pd_, pa = model.outcome_probs(M)
            # identische Strategie wie predict.py: wahrscheinlichste TENDENZ,
            # darin das wahrscheinlichste Ergebnis
            outcome_pick = max(range(3), key=lambda k: (ph, pd_, pa)[k])
            pi, pj = pick_scoreline(M, outcome_pick)
            out = 0 if hs > as_ else (1 if hs == as_ else 2)
            p_out = (ph, pd_, pa)[out]
            cat, pts = grade((pi, pj), (hs, as_))
            tend_ok = [ph, pd_, pa].index(max(ph, pd_, pa)) == out
            targets[r.date.year].append({
                "match": f"{h} {hs}:{as_} {a}", "pick": f"{pi}:{pj}",
                "probs": [round(ph, 3), round(pd_, 3), round(pa, 3)],
                "cat": cat, "pts": pts, "tend_ok": tend_ok, "p_out": p_out,
            })

        hadv = 0.0 if neutral else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        K = k_factor(r.tournament) * gd_multiplier(hs - as_)
        d = K * (W - We)
        R[h] = Rh + d
        R[a] = Ra - d

    import math
    tournaments = {}
    for year, games in targets.items():
        n = len(games)
        summary = {
            "n": n,
            "exakt": sum(1 for g in games if g["cat"] == "exakt"),
            "tordifferenz": sum(1 for g in games if g["cat"] == "tordifferenz"),
            "tendenz": sum(1 for g in games if g["cat"] == "tendenz"),
            "daneben": sum(1 for g in games if g["cat"] == "daneben"),
            "tendenz_quote": round(sum(g["tend_ok"] for g in games) / n, 3),
            "kicktipp_pts": sum(g["pts"] for g in games),
            "kicktipp_avg": round(sum(g["pts"] for g in games) / n, 2),
            "logloss": round(-sum(math.log(max(g["p_out"], 1e-9)) for g in games) / n, 4),
        }
        tournaments[str(year)] = {"summary": summary, "games": games}
        print(f"WM {year} ({n} Spiele): exakt {summary['exakt']} | TD {summary['tordifferenz']} "
              f"| Tendenz {summary['tendenz']} | daneben {summary['daneben']} "
              f"|| Tendenz-Quote {summary['tendenz_quote']*100:.1f}% "
              f"| Kicktipp {summary['kicktipp_pts']} Pkt (Ø {summary['kicktipp_avg']}/Spiel)")

    both = [g for t in tournaments.values() for g in t["games"]]
    n = len(both)
    total = {
        "n": n,
        "tendenz_quote": round(sum(g["tend_ok"] for g in both) / n, 3),
        "exakt_quote": round(sum(1 for g in both if g["cat"] == "exakt") / n, 3),
        "kicktipp_avg": round(sum(g["pts"] for g in both) / n, 2),
    }
    print(f"GESAMT: Tendenz {total['tendenz_quote']*100:.1f}% | exakt {total['exakt_quote']*100:.1f}% "
          f"| Ø {total['kicktipp_avg']} Kicktipp-Punkte/Spiel")

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "method": ("Blind-Backtest: Pre-Match-Elo (kein Look-ahead), kalibriertes Modell, "
                   "Tipp = wahrscheinlichstes Ergebnis, gewertet gegen echte Resultate"),
        "params": model.CALIBRATION,
        "tournaments": {y: t["summary"] for y, t in tournaments.items()},
        "total": total,
        "games": {y: t["games"] for y, t in tournaments.items()},
    }
    json.dump(out, open(os.path.join(PRED_DIR, "backtest.json"), "w"),
              ensure_ascii=False, indent=1)
    print("-> predictions/backtest.json")


if __name__ == "__main__":
    main()
