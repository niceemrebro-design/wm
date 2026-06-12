"""
Baut das kompakte "Daten-Dossier" fuer EIN Spiel — die relevante Scheibe des
Wissensspeichers, ueber die das KI-Orakel urteilt. Liest NUR data/processed/
(kein Rohdaten-Zugriff), darum token-sparend und in jeder frischen Session nutzbar.

CLI:  python3 engine/dossier.py <fixture_id|home_team>
"""
import json
import os
import sys

from util import DATA_PROC
import model


def _load(name):
    return json.load(open(os.path.join(DATA_PROC, name), encoding="utf-8"))


def build(fixture_id):
    fixtures = _load("fixtures_2026.json")
    elo = _load("elo.json")
    forms = _load("forms.json")
    h2h = _load("h2h.json")

    fx = next((f for f in fixtures if f["id"] == fixture_id), None)
    if fx is None:  # erlaube Suche per Heim-Team
        fx = next((f for f in fixtures if f["home"] == fixture_id and not f["played"]), None)
    if fx is None:
        raise SystemExit(f"Fixture nicht gefunden: {fixture_id}")

    h, a = fx["home"], fx["away"]
    eh = elo.get(h, {}).get("elo", 1500.0)
    ea = elo.get(a, {}).get("elo", 1500.0)
    lh, la = model.elo_to_lambdas(eh, ea, fx["neutral"])
    M = model.score_matrix(lh, la)
    ph, pd_, pa = model.outcome_probs(M)
    tops = [{"score": f"{i}:{j}", "p": round(p, 3)}
            for (i, j), p in model.top_scorelines(M, 4)]

    return {
        "fixture": fx,
        "elo": {h: round(eh, 1), a: round(ea, 1), "diff": round(eh - ea, 1)},
        "stat_model": {
            "lambda_home": round(lh, 2), "lambda_away": round(la, 2),
            "p_home": round(ph, 3), "p_draw": round(pd_, 3), "p_away": round(pa, 3),
            "top_scorelines": tops,
        },
        "form": {h: forms.get(h, []), a: forms.get(a, [])},
        "h2h": h2h.get(fx["id"], {}),
    }


if __name__ == "__main__":
    fid = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(build(fid), ensure_ascii=False, indent=2))
