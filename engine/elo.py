"""
World-Football-Elo (nach Methodik von eloratings.net, leicht vereinfacht).

Die Elo-Zahl ist die quantitative Staerke-Basisrate, die spaeter dem
Quant-Analysten und dem Bundestrainer als *Werkzeug* dient — sie entscheidet
nichts, sie informiert.
"""
from util import is_neutral

START = 1500.0
HOME_ADV_ELO = 100.0  # Elo-Punkte Heimvorteil (0 bei neutralem Platz)


def k_factor(tournament):
    t = (str(tournament) or "").lower()
    if "world cup" in t and "qual" not in t:
        return 60
    if any(x in t for x in (
        "uefa euro", "copa am", "african cup", "afc asian cup",
        "gold cup", "confederations", "nations league",
    )):
        return 50
    if "qual" in t:
        return 40
    if "friendly" in t:
        return 20
    return 30


def gd_multiplier(gd):
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    if gd == 3:
        return 1.75
    return 1.75 + (gd - 3) / 8.0


def compute_elo(rows):
    """rows: iterable von dicts mit home_team, away_team, home_score, away_score,
    tournament, neutral (chronologisch sortiert). Liefert (elo, counts)."""
    R = {}
    counts = {}

    def get(t):
        return R.get(t, START)

    for r in rows:
        h, a = r["home_team"], r["away_team"]
        hs, as_ = r["home_score"], r["away_score"]
        Rh, Ra = get(h), get(a)
        hadv = 0.0 if is_neutral(r["neutral"]) else HOME_ADV_ELO
        We = 1.0 / (10 ** (-(Rh - Ra + hadv) / 400) + 1)
        W = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        K = k_factor(r["tournament"]) * gd_multiplier(hs - as_)
        delta = K * (W - We)
        R[h] = Rh + delta
        R[a] = Ra - delta
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1

    return R, counts
