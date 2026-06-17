"""
Kombiwetten (Akkumulator/Parlay) aus den Markt-Wahrscheinlichkeiten — BWIN-konform:
ein Leg pro Spiel (verschiedene Partien sind ~unabhängig, also
Gesamt-Wahrscheinlichkeit = Produkt der Einzel-Wahrscheinlichkeiten).

Drei Charaktere mit unterschiedlichem Risiko/Quote:
  - Sicher-Kombi  : Doppelte Chance (der Banker) — hohe Chance, kleine Quote.
  - Sieger-Kombi  : die klarsten Favoriten gewinnen — solide Quote.
  - Mutig·Jackpot : viele Favoriten-Siege — hohe Quote.

Faire Quote = 1 / Gesamt-Wahrscheinlichkeit (Break-even). Echte BWIN-Quoten
liegen wegen der Buchmacher-Marge etwas darunter.
"""
from functools import reduce

import markets as mk


def _leg(p, key):
    return {"fixture_id": p["fixture_id"], "date": p["date"],
            "match": f'{p["home"]} – {p["away"]}', "key": key,
            "label": mk.LABELS[key].format(h=p["home"], a=p["away"]),
            "p": round(p["markets"][key], 3)}


def _combine(legs, name, risk, desc):
    cp = reduce(lambda acc, l: acc * l["p"], legs, 1.0)
    return {"name": name, "risk": risk, "desc": desc, "legs": legs,
            "combined_p": round(cp, 4), "fair_odds": round(1.0 / cp, 2) if cp > 0 else None}


def build_kombis(upcoming):
    ups = [p for p in upcoming if p.get("markets")]
    if len(ups) < 2:
        return []

    # Beste Doppelte Chance je Spiel
    dc = sorted((_leg(p, max(("1X", "X2", "12"), key=lambda k: p["markets"][k])) for p in ups),
                key=lambda l: -l["p"])
    # Klarer Sieger je Spiel (nur echte Favoriten)
    win = []
    for p in ups:
        m = p["markets"]
        key = "1" if m["1"] >= m["2"] else "2"
        if m[key] >= 0.55:
            win.append(_leg(p, key))
    win.sort(key=lambda l: -l["p"])

    out = []

    # Sicher: Doppelte-Chance-Legs, solange Gesamtchance >= 0.55 (max 5)
    sel, cp = [], 1.0
    for l in dc:
        if len(sel) >= 5 or (sel and cp * l["p"] < 0.55):
            break
        sel.append(l)
        cp *= l["p"]
    if len(sel) >= 2:
        out.append(_combine(sel, "Sicher-Kombi", "sicher",
                             "Doppelte Chance — der Banker. Hohe Gesamtchance, kleine Quote."))

    # Sieger: die 5 klarsten Favoriten
    if len(win) >= 3:
        out.append(_combine(win[:5], "Sieger-Kombi", "mittel",
                             "Die klarsten Favoriten gewinnen — solide Quote."))

    # Mutig: 8 Favoriten-Siege
    if len(win) >= 6:
        out.append(_combine(win[:8], "Mutig · Jackpot", "riskant",
                             "Acht Favoriten-Siege in einem Schein — hohe Quote."))

    return out
