"""
Live-Bilanz ('schwarz auf weiss') auf Basis der WETT-MÄRKTE.

Gewertet werden ausschliesslich Tipps, die VOR Anpfiff im Ledger eingefroren
wurden; Markt-Tipps gespielter Partien werden aus den eingefrorenen Lambdas
rekonstruiert (siehe predict.apply_ledger). Retro-Tipps (Spiel war schon vorbei)
zaehlen nicht.

Kennzahlen: Trefferquote der 3 Top-Tipps · bester Top-Tipp · 1X2 · Doppelte Chance.
Zusaetzlich (sekundaer) die alte exakte Kicktipp-Wertung.

Output: predictions/scorecard.json
"""
import json
import os
from datetime import datetime, timezone

from util import PRED_DIR
import markets as mk


def grade_exact(pick, res):
    ph, pa = pick["home"], pick["away"]
    rh, ra = res["home"], res["away"]
    if (ph, pa) == (rh, ra):
        return "exakt", 4
    if ph - pa == rh - ra:
        return "tordifferenz", 3
    if (ph > pa) == (rh > ra) and (ph == pa) == (rh == ra):
        return "tendenz", 2
    return "daneben", 0


def main():
    allp = json.load(open(os.path.join(PRED_DIR, "all.json"), encoding="utf-8"))

    graded, retro = [], []
    for p in allp["predictions"]:
        if not p.get("played") or not p.get("result"):
            continue
        rh, ra = p["result"]["home"], p["result"]["away"]
        m = p.get("markets", {})
        row = {
            "date": p["date"], "match": f"{p['home']} vs {p['away']}",
            "result": f"{rh}:{ra}", "source": p["source"], "locked_at": p.get("locked_at"),
        }
        if p.get("retro"):
            row["note"] = "ungewertet (Tipp nach Spielende)"
            retro.append(row)
            continue

        tips = []
        for t in p.get("top_tips", []):
            hit = mk.market_hit(t["key"], rh, ra)
            tips.append({"label": t["label"], "key": t["key"], "p": t["p"], "hit": hit})
        row["tips"] = tips
        row["best_hit"] = tips[0]["hit"] if tips else None

        # Einzelmärkte
        if m:
            k1x2 = max(("1", "X", "2"), key=lambda k: m.get(k, 0))
            kdc = max(("1X", "X2", "12"), key=lambda k: m.get(k, 0))
            row["hit_1x2"] = mk.market_hit(k1x2, rh, ra)
            row["hit_dc"] = mk.market_hit(kdc, rh, ra)
        # exakt (sekundär)
        cat, pts = grade_exact(p["pick"], p["result"])
        row["exact_cat"], row["exact_pts"] = cat, pts
        graded.append(row)

    n = len(graded)
    all_tips = [t for g in graded for t in g.get("tips", []) if t["hit"] is not None]
    tip_hits = sum(1 for t in all_tips if t["hit"])
    best_hits = [g["best_hit"] for g in graded if g.get("best_hit") is not None]

    def q(vals):
        v = [x for x in vals if x is not None]
        return round(sum(bool(x) for x in v) / len(v), 3) if v else None

    summary = {
        "gewertet": n,
        "tipps_gesamt": len(all_tips), "tipps_treffer": tip_hits,
        "tipps_quote": round(tip_hits / len(all_tips), 3) if all_tips else None,
        "bester_tipp_quote": round(sum(bool(x) for x in best_hits) / len(best_hits), 3) if best_hits else None,
        "markt_1x2_quote": q([g.get("hit_1x2") for g in graded]),
        "markt_dc_quote": q([g.get("hit_dc") for g in graded]),
        "exakt": sum(1 for g in graded if g["exact_cat"] == "exakt"),
        "kicktipp_pts": sum(g["exact_pts"] for g in graded),
        "kicktipp_avg": round(sum(g["exact_pts"] for g in graded) / n, 2) if n else None,
        "retro_ungewertet": len(retro),
    }

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "integrity": ("Nur vor Anpfiff eingefrorene Tipps zaehlen (predictions/ledger.json). "
                      "Markt-Tipps gespielter Spiele aus eingefrorenen Lambdas rekonstruiert."),
        "summary": summary, "games": graded, "retro": retro,
    }
    json.dump(out, open(os.path.join(PRED_DIR, "scorecard.json"), "w"), ensure_ascii=False, indent=1)

    print(f"Gewertet: {n} Spiele | retro/ungewertet: {len(retro)}")
    if n:
        print(f"  Top-Tipps: {tip_hits}/{len(all_tips)} = {summary['tipps_quote']*100:.0f}% "
              f"| bester Tipp/Spiel: {(summary['bester_tipp_quote'] or 0)*100:.0f}% "
              f"| 1X2: {(summary['markt_1x2_quote'] or 0)*100:.0f}% "
              f"| Doppelte Chance: {(summary['markt_dc_quote'] or 0)*100:.0f}%")
    for g in graded:
        marks = " ".join(("✅" if t["hit"] else "❌") for t in g.get("tips", []))
        print(f"  {g['date']} {g['match']} {g['result']}: {marks}")
    print("-> predictions/scorecard.json")


if __name__ == "__main__":
    main()
