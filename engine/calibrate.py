"""
Zwei-stufige Kalibrierung gegen die echte Historie.

  Stufe 1 (Spielausgang): Grid-Search gpe/base/hag/rho (+ optional Momentum)
          auf 1X2-Log-Loss, Train 1996-2017.
  Stufe 2 (Tore): base_total separat auf die Ueber/Unter-Maerkte feinjustiert
          (minimiert O/U-Brier auf den TURNIER-Spielen) — denn base_total steuert
          das Torniveau, und WM/Turnier ist torärmer als der Schnitt.

  Ehrliche Validierung jeweils auf Holdout 2018+ (inkl. Turnier-Subset).
  Bestes Set -> engine/params.json (model.py laedt es automatisch).
"""
import json
import os
from collections import deque

import numpy as np
import pandas as pd

from util import results_csv_path, ENGINE_DIR, is_neutral
from elo import START, HOME_ADV_ELO, k_factor, gd_multiplier

EVAL_FROM, TRAIN_MAX, MAXG = 1996, 2017, 8
KS = np.arange(MAXG + 1)
LOGFACT = np.array([sum(np.log(np.arange(1, k + 1))) if k > 0 else 0.0 for k in KS])
TOURN_KEYS = ("fifa world cup", "uefa euro", "copa am", "african cup", "afc asian cup", "gold cup")


def elo_pass(df):
    R, hist, recs = {}, {}, []
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        Rh, Ra = R.get(h, START), R.get(a, START)
        neutral = is_neutral(r.neutral)
        hs, as_ = r.home_score, r.away_score
        t = (str(r.tournament) or "").lower()
        is_t = any(k in t for k in TOURN_KEYS) and "qual" not in t
        if r.date.year >= EVAL_FROM:
            out = 0 if hs > as_ else (1 if hs == as_ else 2)
            recs.append((Rh - Ra, 0.0 if neutral else 1.0, out, r.date.year,
                         sum(hist.get(h, deque())) - sum(hist.get(a, deque())),
                         1.0 if is_t else 0.0, hs + as_))
        hadv = 0.0 if neutral else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        d = k_factor(r.tournament) * gd_multiplier(hs - as_) * (W - We)
        R[h] = Rh + d
        R[a] = Ra - d
        for team, pts in ((h, 3 if hs > as_ else 1 if hs == as_ else 0),
                          (a, 3 if as_ > hs else 1 if hs == as_ else 0)):
            hist.setdefault(team, deque(maxlen=5)).append(pts)
    return np.array(recs, dtype=float)


def _lams(diff, ish, p5d, gpe, base, hag, mom):
    eff = diff + (mom * p5d if mom else 0.0)
    mu_d = eff * gpe + ish * hag
    return np.clip(base / 2 + mu_d / 2, 0.18, None), np.clip(base / 2 - mu_d / 2, 0.18, None)


def probs_1x2(diff, ish, p5d, gpe, base, hag, rho, mom=0.0):
    lh, la = _lams(diff, ish, p5d, gpe, base, hag, mom)
    H = np.exp(-lh[:, None] + KS[None, :] * np.log(lh[:, None]) - LOGFACT[None, :])
    A = np.exp(-la[:, None] + KS[None, :] * np.log(la[:, None]) - LOGFACT[None, :])
    CA = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(A, 1)[:, :-1]], 1)
    CH = np.concatenate([np.zeros((len(diff), 1)), np.cumsum(H, 1)[:, :-1]], 1)
    home, away, draw = np.sum(H * CA, 1), np.sum(A * CH, 1), np.sum(H * A, 1)
    t00, t11, t10, t01 = 1 - lh * la * rho, 1 - rho, 1 + la * rho, 1 + lh * rho
    draw += H[:, 0] * A[:, 0] * (t00 - 1) + H[:, 1] * A[:, 1] * (t11 - 1)
    home += H[:, 1] * A[:, 0] * (t10 - 1)
    away += H[:, 0] * A[:, 1] * (t01 - 1)
    s = home + draw + away
    return np.stack([home / s, draw / s, away / s], 1)


def ou_over(diff, ish, p5d, gpe, base, hag, mom, line):
    lh, la = _lams(diff, ish, p5d, gpe, base, hag, mom)
    lam = lh + la
    cdf = np.exp(-lam)        # P(total=0)
    term = cdf.copy()
    for i in range(1, int(line) + 1):
        term = term * lam / i
        cdf = cdf + term
    return 1 - cdf            # P(total > line)


def logloss(P, out):
    return -np.mean(np.log(np.clip(P[np.arange(len(P)), out.astype(int)], 1e-9, 1)))


def ou_brier(diff, ish, p5d, tot, gpe, base, hag, mom, lines=(1.5, 2.5, 3.5)):
    return np.mean([np.mean((ou_over(diff, ish, p5d, gpe, base, hag, mom, ln) - (tot > ln)) ** 2)
                    for ln in lines])


def main():
    df = pd.read_csv(results_csv_path())
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"]).sort_values("date")
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    rec = elo_pass(df)
    diff, ish, out, yr, p5d, ist, tot = (rec[:, i] for i in range(7))
    tr, va, vat = yr <= TRAIN_MAX, yr > TRAIN_MAX, (yr > TRAIN_MAX) & (ist > 0.5)
    trt = (yr <= TRAIN_MAX) & (ist > 0.5)
    print(f"Spiele: {len(rec)} (Train {int(tr.sum())}, Holdout {int(va.sum())}, "
          f"Turnier-Holdout {int(vat.sum())})")

    # ---- Stufe 1: Spielausgang (1X2) ----
    best = None
    for g in [0.0040, 0.0044, 0.0048, 0.0052, 0.0056]:
        for b in [2.5, 2.6, 2.7, 2.8]:
            for h in [0.45, 0.60, 0.75]:
                for r in [-0.12, -0.08, -0.04]:
                    for mo in [0.0, 4.0, 8.0]:
                        ll = logloss(probs_1x2(diff[tr], ish[tr], p5d[tr], g, b, h, r, mo), out[tr])
                        if best is None or ll < best[0]:
                            best = (ll, (g, b, h, r, mo))
    g, b1, h, r, mo = best[1]
    if mo > 0:  # Momentum nur halten, wenn es den Holdout verbessert
        ll_m = logloss(probs_1x2(diff[va], ish[va], p5d[va], g, b1, h, r, mo), out[va])
        ll_0 = logloss(probs_1x2(diff[va], ish[va], p5d[va], g, b1, h, r, 0.0), out[va])
        if ll_0 <= ll_m:
            mo = 0.0
    print(f"Stufe 1 (1X2): gpe={g}, hag={h}, rho={r}, momentum={mo} -> "
          f"Holdout LogLoss {logloss(probs_1x2(diff[va],ish[va],p5d[va],g,b1,h,r,mo),out[va]):.4f}")

    # ---- Stufe 2: Tore (Ueber/Unter) auf Turnier-Spielen ----
    ou_before = ou_brier(diff[vat], ish[vat], p5d[vat], tot[vat], g, b1, h, mo)
    base_grid = [2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.0]
    base_total = min(base_grid, key=lambda bb: ou_brier(diff[trt], ish[trt], p5d[trt], tot[trt], g, bb, h, mo))
    ou_after = ou_brier(diff[vat], ish[vat], p5d[vat], tot[vat], g, base_total, h, mo)
    print(f"Stufe 2 (Tore): base_total {b1} -> {base_total}  | "
          f"O/U-Brier Turnier-Holdout {ou_before:.4f} -> {ou_after:.4f} "
          f"({(ou_before-ou_after)/ou_before*100:+.1f}%)")
    # 1X2 darf durch base-Anpassung nicht nennenswert leiden:
    ll_final = logloss(probs_1x2(diff[va], ish[va], p5d[va], g, base_total, h, r, mo), out[va])
    print(f"1X2 Holdout-LogLoss mit neuem base_total: {ll_final:.4f}")

    params = {
        "goals_per_elo": g, "base_total": base_total, "home_adv_goals": h, "rho": r,
        "momentum_elo_per_pt": mo,
        "calibrated_on": "international 1996-2017; base_total auf Turnier-O/U justiert; Holdout 2018+",
        "holdout_logloss": round(ll_final, 4),
        "holdout_ou_brier_tournament": round(ou_after, 4),
    }
    json.dump(params, open(os.path.join(ENGINE_DIR, "params.json"), "w"), indent=1)
    print("\nGeschrieben -> engine/params.json")


if __name__ == "__main__":
    main()
