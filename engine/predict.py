"""
Erzeugt fuer JEDES WM-2026-Spiel eine Vorhersage mit transparentem Basis-Block.

Architektur:
  - Engine-Baseline: aus dem Wissensspeicher (Elo, Form, H2H) + kalibriertem
    Statistik-Modell (Poisson/Dixon-Coles) wird Tipp, Wahrscheinlichkeiten,
    Konfidenz und eine offengelegte Berechnungs-Basis erzeugt.
  - Orakel-Verfeinerung: predictions/oracle_*.json liefern handverlesene Urteile
    (Form-/Taktik-/Kontext-Lesart, die das reine Modell schlaegt). Diese
    ueberschreiben Tipp/Wahrscheinlichkeit/Begruendung — die Basis bleibt sichtbar.

Output: predictions/all.json  (Quelle fuer die Website)

CLI:  python3 engine/predict.py
"""
import glob
import json
import os
from datetime import datetime, timezone

from util import DATA_PROC, PRED_DIR
import model


def _load(name):
    return json.load(open(os.path.join(DATA_PROC, name), encoding="utf-8"))


def form_summary(games):
    def pts(gs):
        return sum(3 if g["res"] == "W" else 1 if g["res"] == "D" else 0 for g in gs)
    last5 = games[-5:]
    return {
        "seq5": "".join(g["res"] for g in last5),
        "pts5": pts(last5), "gf5": sum(g["gf"] for g in last5),
        "ga5": sum(g["ga"] for g in last5), "pts10": pts(games[-10:]), "n": len(games),
    }


def pick_scoreline(M, outcome):
    best = None
    for i in range(len(M)):
        for j in range(len(M)):
            if outcome == 0 and not i > j:
                continue
            if outcome == 1 and i != j:
                continue
            if outcome == 2 and not i < j:
                continue
            if best is None or M[i][j] > best[1]:
                best = ((i, j), M[i][j])
    return best[0]


def confidence(pmax):
    if pmax >= 0.60:
        return "hoch"
    if pmax >= 0.50:
        return "mittel-hoch"
    if pmax >= 0.42:
        return "mittel"
    if pmax >= 0.36:
        return "niedrig-mittel"
    return "niedrig"


def load_overrides():
    ov = {}
    for path in glob.glob(os.path.join(PRED_DIR, "oracle_*.json")):
        doc = json.load(open(path, encoding="utf-8"))
        for p in doc.get("predictions", []):
            ov[p["fixture_id"]] = p
    return ov


def engine_reasoning(home, away, b):
    ph, pd_, pa = b["model"]["p_home"], b["model"]["p_draw"], b["model"]["p_away"]
    if ph >= pa and ph >= pd_:
        lead = f"{home} ist nach Elo und Form favorisiert"
    elif pa >= ph and pa >= pd_:
        lead = f"{away} ist nach Elo und Form favorisiert"
    else:
        lead = "ein enges, ausgeglichenes Spiel ohne klaren Favoriten"
    return (f"Modellbasierte Einschätzung: {lead}. " + b["basis_text"])


def build_one(fx, elo, forms, h2h):
    h, a = fx["home"], fx["away"]
    eh = elo.get(h, {}).get("elo", 1500.0)
    ea = elo.get(a, {}).get("elo", 1500.0)
    lh, la = model.elo_to_lambdas(eh, ea, fx["neutral"])
    M = model.score_matrix(lh, la)
    ph, pd_, pa = model.outcome_probs(M)
    tops = [{"score": f"{i}:{j}", "p": round(p, 3)} for (i, j), p in model.top_scorelines(M, 4)]
    outcome = max(range(3), key=lambda k: (ph, pd_, pa)[k])
    pi, pj = pick_scoreline(M, outcome)

    fh, fa = form_summary(forms.get(h, [])), form_summary(forms.get(a, []))
    hh = h2h.get(fx["id"], {})
    cal = model.CALIBRATION or {}

    basis = {
        "elo": {h: round(eh, 1), a: round(ea, 1), "diff": round(eh - ea, 1)},
        "form": {h: fh, a: fa},
        "h2h": {"meetings": hh.get("meetings", 0),
                "home_persp": f"{hh.get('home_persp_w',0)}-{hh.get('draw',0)}-{hh.get('home_persp_l',0)}",
                "goals": f"{hh.get('gf',0)}:{hh.get('ga',0)}"},
        "model": {"lambda_home": round(lh, 2), "lambda_away": round(la, 2),
                  "p_home": round(ph, 3), "p_draw": round(pd_, 3), "p_away": round(pa, 3),
                  "top_scorelines": tops},
        "context": {"neutral": fx["neutral"], "city": fx.get("city")},
        "calibration": {"goals_per_elo": cal.get("goals_per_elo"),
                        "base_total": cal.get("base_total"),
                        "home_adv_goals": cal.get("home_adv_goals"), "rho": cal.get("rho"),
                        "holdout_logloss": cal.get("holdout_logloss")},
    }
    basis["basis_text"] = (
        f"Berechnet aus: Elo {eh:.0f} vs {ea:.0f} (Δ {eh-ea:+.0f}) · "
        f"Form letzte 5 {fh['seq5'] or '–'} ({fh['gf5']}:{fh['ga5']}) vs "
        f"{fa['seq5'] or '–'} ({fa['gf5']}:{fa['ga5']}) · "
        f"H2H {hh.get('meetings',0)} Begegnungen · "
        f"kalibriertes Poisson/Dixon-Coles-Modell {ph:.0%}/{pd_:.0%}/{pa:.0%}, "
        f"wahrscheinlichstes Ergebnis {tops[0]['score']}.")

    pmax = max(ph, pd_, pa)
    return {
        "fixture_id": fx["id"], "date": fx["date"], "home": h, "away": a,
        "city": fx.get("city"), "neutral": fx["neutral"], "played": fx["played"],
        "result": ({"home": fx["home_score"], "away": fx["away_score"]} if fx["played"] else None),
        "pick": {"home": pi, "away": pj},
        "probs": {"home": round(ph, 3), "draw": round(pd_, 3), "away": round(pa, 3)},
        "confidence": confidence(pmax),
        "source": "Engine",
        "reasoning": engine_reasoning(h, a, basis),
        "key_factors": [
            f"Elo {eh:.0f} vs {ea:.0f} (Δ {eh-ea:+.0f})",
            f"Form L5 {fh['pts5']} vs {fa['pts5']} Punkte",
            (f"H2H {hh.get('meetings')} Spiele" if hh.get("meetings") else "kein direktes H2H"),
        ],
        "upset_watch": None,
        "basis": basis,
        "stat_model": {"p_home": round(ph, 3), "p_draw": round(pd_, 3), "p_away": round(pa, 3),
                       "lambda_home": round(lh, 2), "lambda_away": round(la, 2),
                       "top_scoreline": tops[0]["score"]},
    }


def main():
    elo = _load("elo.json")
    forms = _load("forms.json")
    h2h = _load("h2h.json")
    fixtures = _load("fixtures_2026.json")
    overrides = load_overrides()

    preds = []
    n_oracle = 0
    for fx in fixtures:
        p = build_one(fx, elo, forms, h2h)
        ov = overrides.get(fx["id"])
        if ov:
            n_oracle += 1
            p["source"] = "Orakel (verfeinert)"
            for k in ("pick", "probs", "confidence", "reasoning", "key_factors", "upset_watch"):
                if k in ov and ov[k] is not None:
                    p[k] = ov[k]
        preds.append(p)

    meta = _load("meta.json")
    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "oracle": "Claude (Claude Code) — Multi-Agenten-Orakel + kalibriertes Statistik-Modell",
        "data": meta,
        "params": model.CALIBRATION,
        "n_predictions": len(preds),
        "n_oracle_refined": n_oracle,
        "predictions": preds,
    }
    os.makedirs(PRED_DIR, exist_ok=True)
    json.dump(out, open(os.path.join(PRED_DIR, "all.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"predictions/all.json: {len(preds)} Spiele, davon {n_oracle} Orakel-verfeinert.")


if __name__ == "__main__":
    main()
