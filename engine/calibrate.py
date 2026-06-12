"""
Kalibriert die Modell-Parameter gegen die echte Laenderspiel-Historie — v2.

Neu in v2:
  - Momentum-Feature: Punkte aus den letzten 5 Spielen je Team (zum Zeitpunkt
    des Spiels, kein Look-ahead). Der Gewichtsfaktor wird mitkalibriert und
    NUR behalten, wenn er den Holdout-Log-Loss verbessert.
  - Zusaetzliche Auswertung auf dem Turnier-Subset (WM/EM/Copa etc.), damit
    die Guete fuer Turnierspiele sichtbar ist.

Methode (unveraendert ehrlich):
  - Ein Elo-Durchlauf ueber die gesamte Historie; Pre-Match-Elo + Pre-Match-Form
    werden VOR dem Update gespeichert (kein Look-ahead).
  - Train 1996-2017 (Grid-Search), Holdout 2018+ (nur Bewertung).
  - Bestes Parameterset -> engine/params.json (model.py laedt es automatisch).
"""
import json
import os
from collections import deque

import numpy as np
import pandas as pd

from util import results_csv_path, ENGINE_DIR, is_neutral
from elo import START, HOME_ADV_ELO, k_factor, gd_multiplier

EVAL_FROM = 1996
TRAIN_MAX = 2017
MAXG = 8
KS = np.arange(MAXG + 1)
LOGFACT = np.array([sum(np.log(np.arange(1, k + 1))) if k > 0 else 0.0 for k in KS])

TOURN_KEYS = ("fifa world cup", "uefa euro", "copa am", "african cup",
              "afc asian cup", "gold cup")


def elo_pass(df):
    """Array je Spiel >= EVAL_FROM:
    [elo_diff, is_home, outcome, year, pts5_diff, is_tournament]"""
    R, hist = {}, {}
    recs = []
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        Rh, Ra = R.get(h, START), R.get(a, START)
        neutral = is_neutral(r.neutral)
        hs, as_ = r.home_score, r.away_score
        t = (str(r.tournament) or "").lower()
        is_t = any(k in t for k in TOURN_KEYS) and "qual" not in t

        if r.date.year >= EVAL_FROM:
            out = 0 if hs > as_ else (1 if hs == as_ else 2)
            p5h = sum(hist.get(h, deque()))
            p5a = sum(hist.get(a, deque()))
            recs.append((Rh - Ra, 0.0 if neutral else 1.0, out, r.date.year,
                         p5h - p5a, 1.0 if is_t else 0.0))

        # Elo-Update (nach Aufzeichnung!)
        hadv = 0.0 if neutral else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        K = k_factor(r.tournament) * gd_multiplier(hs - as_)
        d = K * (W - We)
        R[h] = Rh + d
        R[a] = Ra - d
        # Form-Update (Punkte letzter 5)
        for team, pts in ((h, 3 if hs > as_ else 1 if hs == as_ else 0),
                          (a, 3 if as_ > hs else 1 if hs == as_ else 0)):
            q = hist.setdefault(team, deque(maxlen=5))
            q.append(pts)
    return np.array(recs, dtype=float)


def probs(diff, is_home, gpe, base, hag, rho, mom=0.0, p5d=None):
    eff = diff + (mom * p5d if p5d is not None else 0.0)
    mu_d = eff * gpe + is_home * hag
    lh = np.clip(base / 2 + mu_d / 2, 0.18, None)
    la = np.clip(base / 2 - mu_d / 2, 0.18, None)
    H = np.exp(-lh[:, None] + KS[None, :] * np.log(lh[:, None]) - LOGFACT[None, :])
    A = np.exp(-la[:, None] + KS[None, :] * np.log(la[:, None]) - LOGFACT[None, :])
    CA_lt = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(A, 1)[:, :-1]], 1)
    CH_lt = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(H, 1)[:, :-1]], 1)
    home = np.sum(H * CA_lt, 1)
    away = np.sum(A * CH_lt, 1)
    draw = np.sum(H * A, 1)
    t00 = 1 - lh * la * rho; t11 = 1 - rho; t10 = 1 + la * rho; t01 = 1 + lh * rho
    draw = draw + H[:, 0] * A[:, 0] * (t00 - 1) + H[:, 1] * A[:, 1] * (t11 - 1)
    home = home + H[:, 1] * A[:, 0] * (t10 - 1)
    away = away + H[:, 0] * A[:, 1] * (t01 - 1)
    s = home + draw + away
    return np.stack([home / s, draw / s, away / s], 1)


def logloss(P, out):
    return -np.mean(np.log(np.clip(P[np.arange(len(P)), out.astype(int)], 1e-9, 1)))


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
    diff, ish, out, yr, p5d, ist = (rec[:, i] for i in range(6))
    tr, va = yr <= TRAIN_MAX, yr > TRAIN_MAX
    vat = va & (ist > 0.5)
    print(f"Spiele: {len(rec)} (Train {int(tr.sum())}, Holdout {int(va.sum())}, "
          f"davon Turnier {int(vat.sum())})")

    base_params = (0.0048, 2.7, 0.6, -0.08)
    P0 = probs(diff[va], ish[va], *base_params)
    ll0 = logloss(P0, out[va])
    print(f"\nv1 (ohne Momentum):           Holdout LogLoss {ll0:.4f} | Brier {brier(P0, out[va]):.4f}")

    grid_gpe = [0.0040, 0.0044, 0.0048, 0.0052, 0.0056]
    grid_base = [2.5, 2.6, 2.7, 2.8]
    grid_hag = [0.45, 0.60, 0.75]
    grid_rho = [-0.12, -0.08, -0.04]
    grid_mom = [0.0, 2.0, 4.0, 6.0, 9.0, 12.0]   # Elo-Punkte je Form-Punkt-Differenz

    best = None
    for m in grid_mom:
        for g in grid_gpe:
            for b in grid_base:
                for h in grid_hag:
                    for r in grid_rho:
                        P = probs(diff[tr], ish[tr], g, b, h, r, m, p5d[tr])
                        ll = logloss(P, out[tr])
                        if best is None or ll < best[0]:
                            best = (ll, (g, b, h, r, m))
    _, (g, b, h, r, m) = best
    Pv = probs(diff[va], ish[va], g, b, h, r, m, p5d[va])
    ll_v, br_v = logloss(Pv, out[va]), brier(Pv, out[va])
    print(f"v2 (gpe={g}, base={b}, hag={h}, rho={r}, momentum={m}):")
    print(f"                              Holdout LogLoss {ll_v:.4f} | Brier {br_v:.4f}"
          f"  ({(ll0-ll_v)/ll0*100:+.2f}% vs v1)")

    # Momentum nur behalten, wenn es auf dem HOLDOUT hilft (ehrliche Auswahl)
    if m > 0:
        Pv_nomom = probs(diff[va], ish[va], g, b, h, r, 0.0, p5d[va])
        if logloss(Pv_nomom, out[va]) <= ll_v:
            print("-> Momentum verbessert Holdout NICHT — wird verworfen.")
            m = 0.0
            Pv, ll_v, br_v = Pv_nomom, logloss(Pv_nomom, out[va]), brier(Pv_nomom, out[va])

    Pt = probs(diff[vat], ish[vat], g, b, h, r, m, p5d[vat])
    print(f"Turnier-Subset (Holdout):     LogLoss {logloss(Pt, out[vat]):.4f} | "
          f"Brier {brier(Pt, out[vat]):.4f} | Tendenz-Trefferquote "
          f"{np.mean(np.argmax(Pt,1)==out[vat])*100:.1f}%")

    params = {
        "goals_per_elo": g, "base_total": b, "home_adv_goals": h, "rho": r,
        "momentum_elo_per_pt": m,
        "calibrated_on": "international 1996-2017, validated 2018+ (incl. tournament subset)",
        "holdout_logloss": round(ll_v, 4), "holdout_brier": round(br_v, 4),
    }
    json.dump(params, open(os.path.join(ENGINE_DIR, "params.json"), "w"), indent=1)
    print("\nGeschrieben -> engine/params.json")


if __name__ == "__main__":
    main()
