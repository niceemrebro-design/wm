"""
Baut web/data.js (self-contained) aus predictions/*.json + data/processed/.
Wird als <script> geladen -> funktioniert lokal per Doppelklick UND auf Vercel
(keine CORS-/Fetch-Probleme).

CLI:  python3 engine/build_web.py
"""
import glob
import json
import os

from util import DATA_PROC, PRED_DIR, REPO_ROOT

WEB = os.path.join(REPO_ROOT, "web")


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    os.makedirs(WEB, exist_ok=True)
    elo = _load(os.path.join(DATA_PROC, "elo.json"))
    meta = _load(os.path.join(DATA_PROC, "meta.json"))
    fixtures = _load(os.path.join(DATA_PROC, "fixtures_2026.json"))
    fx_by_id = {f["id"]: f for f in fixtures}

    participants = sorted(set([f["home"] for f in fixtures] + [f["away"] for f in fixtures]))
    elo_top = sorted(participants, key=lambda t: -elo.get(t, {}).get("elo", 0))
    elo_top = [{"team": t, "elo": elo.get(t, {}).get("elo")} for t in elo_top]

    batches, preds = [], []
    for path in sorted(glob.glob(os.path.join(PRED_DIR, "*.json"))):
        b = _load(path)
        batches.append({k: b.get(k) for k in ("batch", "generated_at", "method", "oracle")})
        for p in b.get("predictions", []):
            f = fx_by_id.get(p["fixture_id"])
            if f and f.get("played"):
                p["result"] = {"home": f["home_score"], "away": f["away_score"]}
            preds.append(p)

    data = {"meta": meta, "batches": batches, "predictions": preds, "elo_top": elo_top}
    out = os.path.join(WEB, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.WM_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"web/data.js geschrieben: {len(preds)} Vorhersagen, {len(elo_top)} Teams")


if __name__ == "__main__":
    main()
