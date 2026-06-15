"""
WM-Backtest (Blind, kein Look-ahead): Die Engine tippt WM 2018 + 2022 mit dem
Elo-Stand vom Tag vor jedem Spiel und den kalibrierten Parametern.

Bewertet wird BEIDES:
  A) das alte Format: exaktes Ergebnis (Kicktipp 4/3/2/0)
  B) die Wett-Maerkte (BWIN-Stil): 1X2, Ueber/Unter 2,5, Beide treffen,
     Doppelte Chance — plus die Trefferquote der 3 Top-Tipps.

Output: predictions/backtest.json
"""
import json
import math
import os
from datetime import datetime, timezone

import pandas as pd

from util import results_csv_path, PRED_DIR, is_neutral
from elo import START, HOME_ADV_ELO, k_factor, gd_multiplier
from predict import pick_scoreline
import model
import markets as mk


def grade_exact(pick, res):
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
            m = mk.markets_from_matrix(M)
            outcome_pick = max(range(3), key=lambda k: (ph, pd_, pa)[k])
            pi, pj = pick_scoreline(M, outcome_pick)
            cat, pts = grade_exact((pi, pj), (hs, as_))

            # Markt-Tipps
            tip_1x2 = ["1", "X", "2"][outcome_pick]
            tip_ou = "O25" if m["O25"] >= 0.5 else "U25"
            tip_btts = "BTTS_yes" if m["BTTS_yes"] >= 0.5 else "BTTS_no"
            tip_dc = max(("1X", "X2", "12"), key=lambda k: m[k])
            tops = mk.top_tips(m, h, a)

            targets[r.date.year].append({
                "cat": cat, "pts": pts,
                "hit_1x2": mk.market_hit(tip_1x2, hs, as_),
                "hit_ou": mk.market_hit(tip_ou, hs, as_),
                "hit_btts": mk.market_hit(tip_btts, hs, as_),
                "hit_dc": mk.market_hit(tip_dc, hs, as_),
                "top_hits": sum(1 for t in tops if mk.market_hit(t["key"], hs, as_)),
                "top_n": len(tops),
                "top1_hit": mk.market_hit(tops[0]["key"], hs, as_),
            })

        hadv = 0.0 if neutral else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        K = k_factor(r.tournament) * gd_multiplier(hs - as_)
        d = K * (W - We)
        R[h] = Rh + d
        R[a] = Ra - d

    def rate(games, field):
        vals = [g[field] for g in games if g[field] is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    out_tour = {}
    allg = []
    for year, games in targets.items():
        allg += games
        n = len(games)
        out_tour[str(year)] = {
            "n": n,
            "exakt": sum(1 for g in games if g["cat"] == "exakt"),
            "kicktipp_pts": sum(g["pts"] for g in games),
            "kicktipp_avg": round(sum(g["pts"] for g in games) / n, 2),
            "hit_1x2": rate(games, "hit_1x2"),
            "hit_ou25": rate(games, "hit_ou"),
            "hit_btts": rate(games, "hit_btts"),
            "hit_dc": rate(games, "hit_dc"),
            "top1": rate(games, "top1_hit"),
            "top3_avg": round(sum(g["top_hits"] for g in games) / sum(g["top_n"] for g in games), 3),
        }

    n = len(allg)
    total = {
        "n": n,
        "hit_1x2": rate(allg, "hit_1x2"),
        "hit_ou25": rate(allg, "hit_ou"),
        "hit_btts": rate(allg, "hit_btts"),
        "hit_dc": rate(allg, "hit_dc"),
        "top1": rate(allg, "top1_hit"),
        "top3_avg": round(sum(g["top_hits"] for g in allg) / sum(g["top_n"] for g in allg), 3),
        "kicktipp_avg": round(sum(g["pts"] for g in allg) / n, 2),
        "exakt_quote": round(sum(1 for g in allg if g["cat"] == "exakt") / n, 3),
    }

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "method": "Blind-Backtest WM 2018+2022 (Pre-Match-Elo, kalibriertes Modell)",
        "params": model.CALIBRATION,
        "tournaments": out_tour, "total": total,
    }
    json.dump(out, open(os.path.join(PRED_DIR, "backtest.json"), "w"), ensure_ascii=False, indent=1)

    print(f"WM 2018+2022 — {n} echte Spiele, blind getippt:\n")
    print(f"  WETT-MÄRKTE (BWIN-Stil) — Trefferquote:")
    print(f"    Doppelte Chance (1X/X2/12):  {total['hit_dc']*100:.1f}%")
    print(f"    Über/Unter 2,5 Tore:         {total['hit_ou25']*100:.1f}%")
    print(f"    Beide treffen (BTTS):        {total['hit_btts']*100:.1f}%")
    print(f"    Spielausgang (1X2):          {total['hit_1x2']*100:.1f}%")
    print(f"    Bester Top-Tipp je Spiel:    {total['top1']*100:.1f}%")
    print(f"    Alle 3 Top-Tipps gemittelt:  {total['top3_avg']*100:.1f}%")
    print(f"\n  Zum Vergleich — exaktes Ergebnis: nur {total['exakt_quote']*100:.1f}% "
          f"(Kicktipp Ø {total['kicktipp_avg']}/Spiel)")
    print("\n-> predictions/backtest.json")


if __name__ == "__main__":
    main()
