"""
Kalibriert die Modell-Parameter (goals_per_elo, base_total, home_adv_goals, rho)
gegen die echte Laenderspiel-Historie.

Methode:
  - Ein Elo-Durchlauf ueber die gesamte Historie; vor jedem Spiel wird der
    Pre-Match-Elo-Stand als Feature gespeichert (kein Look-ahead).
  - Auswertung ab 1996 (Elo eingeschwungen).
  - Grid-Search der Parameter auf TRAIN (1996-2017),
    ehrliche Validierung auf HOLDOUT (2018+) via Multiklassen-Log-Loss + Brier.
  - Bestes Parameterset -> engine/params.json (model.py laedt es automatisch).

Output ist bewusst transparent: zeigt Baseline vs. kalibriert.
"""
import json
import os

import numpy as np
import pandas as pd

from util import results_csv_path, ENGINE_DIR, is_neutral
from elo import START, HOME_ADV_ELO, k_factor, gd_multiplier

EVAL_FROM = 1996
TRAIN_MAX = 2017          # <= 2017 trainieren
MAXG = 8
KS = np.arange(MAXG + 1)
LOGFACT = np.array([sum(np.log(np.arange(1, k + 1))) if k > 0 else 0.0 for k in KS])


def elo_pass(df):
    """Liefert Array [diff, is_home, outcome(0=H,1=X,2=A), year] je Spiel >= EVAL_FROM."""
    R = {}
    recs = []
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        Rh, Ra = R.get(h, START), R.get(a, START)
        neutral = is_neutral(r.neutral)
        hs, as_ = r.home_score, r.away_score
        if r.date.year >= EVAL_FROM:
            out = 0 if hs > as_ else (1 if hs == as_ else 2)
            recs.append((Rh - Ra, 0.0 if neutral else 1.0, out, r.date.year))
        hadv = 0.0 if neutral else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        K = k_factor(r.tournament) * gd_multiplier(hs - as_)
        d = K * (W - We)
        R[h] = Rh + d
        R[a] = Ra - d
    return np.array(recs, dtype=float)


def probs(diff, is_home, gpe, base, hag, rho):
    mu_d = diff * gpe + is_home * hag
    lh = np.clip(base / 2 + mu_d / 2, 0.18, None)
    la = np.clip(base / 2 - mu_d / 2, 0.18, None)
    H = np.exp(-lh[:, None] + KS[None, :] * np.log(lh[:, None]) - LOGFACT[None, :])
    A = np.exp(-la[:, None] + KS[None, :] * np.log(la[:, None]) - LOGFACT[None, :])
    CA_lt = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(A, 1)[:, :-1]], 1)
    CH_lt = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(H, 1)[:, :-1]], 1)
    home = np.sum(H * CA_lt, 1)
    away = np.sum(A * CH_lt, 1)
    draw = np.sum(H * A, 1)
    # Dixon-Coles-Korrektur (vier niedrige Zellen)
    t00 = 1 - lh * la * rho; t01 = 1 + lh * rho; t10 = 1 + la * rho; t11 = 1 - rho
    draw = draw + H[:, 0] * A[:, 0] * (t00 - 1) + H[:, 1] * A[:, 1] * (t11 - 1)
    home = home + H[:, 1] * A[:, 0] * (t10 - 1)
    away = away + H[:, 0] * A[:, 1] * (t01 - 1)
    s = home + draw + away
    return np.stack([home / s, draw / s, away / s], 1)


def logloss(P, out):
    p = np.clip(P[np.arange(len(P)), out.astype(int)], 1e-9, 1)
    return -np.mean(np.log(p))


def brier(P, out):
    Y = np.zeros_like(P)
    Y[np.arange(len(P)), out.astype(int)] = 1
    return np.mean(np.sum((P - Y) ** 2, 1))


def main():
    df = pd.read_csv(results_csv_path())
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"]).sort_values("date")
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    rec = elo_pass(df)
    diff, ish, out, yr = rec[:, 0], rec[:, 1], rec[:, 2], rec[:, 3]
    tr = yr <= TRAIN_MAX
    va = yr > TRAIN_MAX
    print(f"Auswertungs-Spiele: {len(rec)}  (Train<=2017: {int(tr.sum())}, Holdout 2018+: {int(va.sum())})")

    base_params = (0.0035, 2.6, 0.35, -0.13)
    P0 = probs(diff[va], ish[va], *base_params)
    print(f"\nBASELINE (Default {base_params}):  Holdout LogLoss {logloss(P0, out[va]):.4f} | Brier {brier(P0, out[va]):.4f}")

    grid_gpe = [0.0036, 0.0042, 0.0048, 0.0054, 0.0060, 0.0066, 0.0072]
    grid_base = [2.3, 2.4, 2.5, 2.6, 2.7]
    grid_hag = [0.30, 0.45, 0.60, 0.75]
    grid_rho = [-0.12, -0.08, -0.04, 0.00, 0.04]

    best = None
    for g in grid_gpe:
        for b in grid_base:
            for h in grid_hag:
                for r in grid_rho:
                    P = probs(diff[tr], ish[tr], g, b, h, r)
                    ll = logloss(P, out[tr])
                    if best is None or ll < best[0]:
                        best = (ll, (g, b, h, r))
    _, bp = best
    Pv = probs(diff[va], ish[va], *bp)
    ll_v, br_v = logloss(Pv, out[va]), brier(Pv, out[va])
    print(f"KALIBRIERT {bp}:  Holdout LogLoss {ll_v:.4f} | Brier {br_v:.4f}")
    impr = (logloss(P0, out[va]) - ll_v) / logloss(P0, out[va]) * 100
    print(f"-> Log-Loss-Verbesserung auf Holdout: {impr:+.1f}%")

    params = {"goals_per_elo": bp[0], "base_total": bp[1],
              "home_adv_goals": bp[2], "rho": bp[3],
              "calibrated_on": "international 1996-2017, validated 2018+",
              "holdout_logloss": round(ll_v, 4), "holdout_brier": round(br_v, 4)}
    json.dump(params, open(os.path.join(ENGINE_DIR, "params.json"), "w"), indent=1)
    print("\nGeschrieben -> engine/params.json")


if __name__ == "__main__":
    main()
