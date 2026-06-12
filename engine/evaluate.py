"""
Live-Bilanz ('schwarz auf weiss'): wertet jede abgeschlossene Partie gegen den
VOR Anpfiff eingefrorenen Tipp (Ledger). Retro-Tipps (Spiel war schon vorbei)
zaehlen ausdruecklich NICHT.

Wertung: exakt (4) / Tordifferenz (3) / Tendenz (2) / daneben (0)  [Kicktipp]
         + Brier-Score der Wahrscheinlichkeiten (Kalibrierungs-Mass).

Output: predictions/scorecard.json
CLI:    python3 engine/evaluate.py
"""
import json
import os
from datetime import datetime, timezone

from util import PRED_DIR


def grade(pick, res):
    ph, pa = pick["home"], pick["away"]
    rh, ra = res["home"], res["away"]
    if (ph, pa) == (rh, ra):
        return "exakt", 4
    if ph - pa == rh - ra:
        return "tordifferenz", 3
    if (ph > pa) == (rh > ra) and (ph == pa) == (rh == ra):
        return "tendenz", 2
    return "daneben", 0


def brier(probs, res):
    out = 0 if res["home"] > res["away"] else (1 if res["home"] == res["away"] else 2)
    y = [0.0, 0.0, 0.0]
    y[out] = 1.0
    p = [probs["home"], probs["draw"], probs["away"]]
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y))


def main():
    allp = json.load(open(os.path.join(PRED_DIR, "all.json"), encoding="utf-8"))
    preds = allp["predictions"]

    graded, retro = [], []
    for p in preds:
        if not p.get("played") or not p.get("result"):
            continue
        row = {
            "fixture_id": p["fixture_id"], "date": p["date"],
            "match": f"{p['home']} vs {p['away']}",
            "pick": f"{p['pick']['home']}:{p['pick']['away']}",
            "result": f"{p['result']['home']}:{p['result']['away']}",
            "source": p["source"], "locked_at": p.get("locked_at"),
        }
        if p.get("retro"):
            row["cat"] = "ungewertet (Tipp nach Spielende)"
            retro.append(row)
            continue
        cat, pts = grade(p["pick"], p["result"])
        row.update(cat=cat, pts=pts, brier=round(brier(p["probs"], p["result"]), 3))
        graded.append(row)

    n = len(graded)
    summary = {
        "gewertet": n,
        "exakt": sum(1 for g in graded if g["cat"] == "exakt"),
        "tordifferenz": sum(1 for g in graded if g["cat"] == "tordifferenz"),
        "tendenz": sum(1 for g in graded if g["cat"] == "tendenz"),
        "daneben": sum(1 for g in graded if g["cat"] == "daneben"),
        "kicktipp_pts": sum(g["pts"] for g in graded),
        "kicktipp_avg": round(sum(g["pts"] for g in graded) / n, 2) if n else None,
        "tendenz_quote": round(sum(1 for g in graded if g["pts"] > 0) / n, 3) if n else None,
        "brier_avg": round(sum(g["brier"] for g in graded) / n, 3) if n else None,
        "retro_ungewertet": len(retro),
    }

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "integrity": ("Gewertet werden ausschliesslich Tipps, die VOR Anpfiff im Ledger "
                      "eingefroren wurden (predictions/ledger.json). Nachtraegliche Tipps "
                      "erscheinen als 'ungewertet'."),
        "summary": summary, "games": graded, "retro": retro,
    }
    json.dump(out, open(os.path.join(PRED_DIR, "scorecard.json"), "w"),
              ensure_ascii=False, indent=1)

    print(f"Gewertet: {n} | retro/ungewertet: {len(retro)}")
    if n:
        print(f"  exakt {summary['exakt']} | TD {summary['tordifferenz']} | "
              f"Tendenz {summary['tendenz']} | daneben {summary['daneben']} "
              f"|| {summary['kicktipp_pts']} Pkt (Ø {summary['kicktipp_avg']}) "
              f"| Brier {summary['brier_avg']}")
    for r in retro:
        print(f"  retro: {r['match']} (Tipp {r['pick']}, Ergebnis {r['result']}) — zählt nicht")
    print("-> predictions/scorecard.json")


if __name__ == "__main__":
    main()
