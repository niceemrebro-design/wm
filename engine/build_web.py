"""
Baut web/data.js (self-contained) aus predictions/all.json + Wissensspeicher.
Wird als <script> geladen -> funktioniert lokal per Doppelklick UND statisch
gehostet (Vercel), ohne CORS/Build-Schritt.

CLI:  python3 engine/build_web.py
"""
import json
import os

from util import DATA_PROC, PRED_DIR, REPO_ROOT
import kombi

WEB = os.path.join(REPO_ROOT, "web")


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    os.makedirs(WEB, exist_ok=True)
    allp = _load(os.path.join(PRED_DIR, "all.json"))
    elo = _load(os.path.join(DATA_PROC, "elo.json"))
    fixtures = _load(os.path.join(DATA_PROC, "fixtures_2026.json"))

    parts = sorted(set([f["home"] for f in fixtures] + [f["away"] for f in fixtures]))
    elo_top = [{"team": t, "elo": elo.get(t, {}).get("elo")}
               for t in sorted(parts, key=lambda t: -elo.get(t, {}).get("elo", 0))]

    def _opt(name):
        p = os.path.join(PRED_DIR, name)
        return _load(p) if os.path.exists(p) else None

    tour = _opt("tournament.json")
    scorecard = _opt("scorecard.json")
    backtest = _opt("backtest.json")
    if backtest:
        backtest.pop("games", None)  # Detail-Listen nicht in die Web-Daten

    upcoming = [p for p in allp.get("predictions", []) if not p.get("played")]
    kombis = kombi.build_kombis(upcoming)

    data = {
        "meta": allp.get("data", {}),
        "params": allp.get("params"),
        "generated_at": allp.get("generated_at"),
        "oracle": allp.get("oracle"),
        "n_oracle_refined": allp.get("n_oracle_refined"),
        "predictions": allp.get("predictions", []),
        "elo_top": elo_top,
        "tournament": tour,
        "scorecard": scorecard,
        "backtest": backtest,
        "kombis": kombis,
    }
    with open(os.path.join(WEB, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.WM_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"web/data.js: {len(data['predictions'])} Vorhersagen, {len(elo_top)} Teams"
          + (" + Turniersimulation" if tour else ""))


if __name__ == "__main__":
    main()
