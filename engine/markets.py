"""
Wett-Maerkte im BWIN-Stil, abgeleitet aus der Ergebnis-Matrix des Modells
(Poisson/Dixon-Coles). Statt eines unsicheren exakten Ergebnisses liefern wir
die wahrscheinlichsten, gut treffbaren Markt-Tipps.

Maerkte: 1X2 · Doppelte Chance (1X/X2/12) · Ueber/Unter (1,5/2,5/3,5) ·
         Beide treffen (BTTS) · Team ueber 1,5 · Draw-No-Bet.
"""

LINES = (1.5, 2.5, 3.5)

LABELS = {
    "1": "{h} gewinnt", "X": "Unentschieden", "2": "{a} gewinnt",
    "1X": "{h} oder Remis", "X2": "{a} oder Remis", "12": "Kein Remis (einer gewinnt)",
    "BTTS_yes": "Beide Teams treffen", "BTTS_no": "Nicht beide treffen",
    "home_o15": "{h} über 1,5 Tore", "away_o15": "{a} über 1,5 Tore",
    "O15": "Über 1,5 Tore", "U15": "Unter 1,5 Tore",
    "O25": "Über 2,5 Tore", "U25": "Unter 2,5 Tore",
    "O35": "Über 3,5 Tore", "U35": "Unter 3,5 Tore",
    "DNB1": "{h} (Draw No Bet)", "DNB2": "{a} (Draw No Bet)",
}


def markets_from_matrix(M):
    n = len(M)
    p1 = sum(M[i][j] for i in range(n) for j in range(n) if i > j)
    px = sum(M[i][i] for i in range(n))
    p2 = sum(M[i][j] for i in range(n) for j in range(n) if i < j)
    over = {ln: sum(M[i][j] for i in range(n) for j in range(n) if i + j > ln) for ln in LINES}
    btts = sum(M[i][j] for i in range(n) for j in range(n) if i >= 1 and j >= 1)
    h2 = sum(M[i][j] for i in range(n) for j in range(n) if i >= 2)
    a2 = sum(M[i][j] for i in range(n) for j in range(n) if j >= 2)
    d = p1 + p2
    m = {
        "1": p1, "X": px, "2": p2,
        "1X": p1 + px, "X2": px + p2, "12": p1 + p2,
        "DNB1": p1 / d if d else 0.5, "DNB2": p2 / d if d else 0.5,
        "BTTS_yes": btts, "BTTS_no": 1 - btts,
        "home_o15": h2, "away_o15": a2,
    }
    for ln in LINES:
        key = str(ln).replace(".", "")
        m[f"O{key}"] = over[ln]
        m[f"U{key}"] = 1 - over[ln]
    return m


def market_hit(key, rh, ra):
    """True/False, ob der Markt-Tipp eingetreten ist. None = Push (z.B. DNB bei Remis)."""
    tot = rh + ra
    direct = {
        "1": rh > ra, "X": rh == ra, "2": ra > rh,
        "1X": rh >= ra, "X2": ra >= rh, "12": rh != ra,
        "BTTS_yes": rh >= 1 and ra >= 1, "BTTS_no": not (rh >= 1 and ra >= 1),
        "home_o15": rh >= 2, "away_o15": ra >= 2,
    }
    if key in direct:
        return direct[key]
    if key.startswith("O"):
        return tot > float(key[1] + "." + key[2:])
    if key.startswith("U"):
        return tot < float(key[1] + "." + key[2:])
    if key == "DNB1":
        return None if rh == ra else rh > ra
    if key == "DNB2":
        return None if rh == ra else ra > rh
    return None


def _best_in(m, keys, cap=0.93):
    """Hoechste Wahrscheinlichkeit, aber nicht trivial (<= cap, sonst hoechste)."""
    cands = [(k, m[k]) for k in keys]
    pool = [c for c in cands if c[1] <= cap] or cands
    return max(pool, key=lambda c: c[1])


def outcome_tip(m):
    """Klarer Sieger-Tipp wenn deutlich favorisiert, sonst sichere Doppelte Chance."""
    p1, px, p2 = m["1"], m["X"], m["2"]
    if max(p1, p2) >= 0.55:
        key = "1" if p1 >= p2 else "2"
    else:
        least = min((("1", p1), ("X", px), ("2", p2)), key=lambda x: x[1])[0]
        key = {"1": "X2", "X": "12", "2": "1X"}[least]
    return key, m[key]


def top_tips(m, home, away, k=3):
    """Die k wahrscheinlichsten, inhaltlich verschiedenen Tipps (Sieger/Tore/BTTS/Teamtore)."""
    cands = [outcome_tip(m),
             _best_in(m, ["O15", "U15", "O25", "U25", "O35", "U35"]),
             _best_in(m, ["BTTS_yes", "BTTS_no"]),
             _best_in(m, ["home_o15", "away_o15"])]
    cands.sort(key=lambda c: -c[1])
    out = []
    for key, p in cands[:k]:
        out.append({"key": key, "p": round(p, 3),
                    "label": LABELS[key].format(h=home, a=away)})
    return out
