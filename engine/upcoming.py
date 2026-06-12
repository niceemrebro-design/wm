"""
Kompaktes, reasoning-fertiges Briefing fuer die naechsten ungespielten Spiele.
Das Orakel (Claude) liest diese Ausgabe und faellt darauf seine Urteile —
token-sparend, weil nur die relevante Scheibe je Spiel gezeigt wird.

CLI:  python3 engine/upcoming.py [anzahl=10]
"""
import json
import os
import sys

from util import DATA_PROC
import dossier as D


def form_str(games):
    out = []
    for g in games[-5:]:
        arrow = "vs" if g["venue"] == "H" else "@"
        out.append(f"{g['res']}{g['gf']}-{g['ga']} {arrow}{g['opp']}")
    return " | ".join(out) if out else "(keine Daten)"


def main(n=10):
    fixtures = json.load(open(os.path.join(DATA_PROC, "fixtures_2026.json"), encoding="utf-8"))
    upcoming = [f for f in fixtures if not f["played"]][:n]
    for f in upcoming:
        d = D.build(f["id"])
        fx, m, e = d["fixture"], d["stat_model"], d["elo"]
        eh, ea = e[fx["home"]], e[fx["away"]]
        print(f"\n### {fx['id']}  {fx['date']}  {fx['home']} vs {fx['away']}  "
              f"[{fx['city']}, neutral={fx['neutral']}]")
        print(f"Elo {eh:.0f} vs {ea:.0f} (diff {e['diff']:+.0f}) | "
              f"Stat-Modell P {m['p_home']:.0%}/{m['p_draw']:.0%}/{m['p_away']:.0%} | "
              f"lambda {m['lambda_home']}-{m['lambda_away']}")
        print("  Top-Ergebnisse: " + ", ".join(
            f"{t['score']}({t['p']:.0%})" for t in m["top_scorelines"]))
        print(f"  Form {fx['home']}: {form_str(d['form'][fx['home']])}")
        print(f"  Form {fx['away']}: {form_str(d['form'][fx['away']])}")
        h = d["h2h"]
        if h.get("meetings"):
            print(f"  H2H: {h['meetings']} Beg., aus {fx['home']}-Sicht "
                  f"{h['home_persp_w']}-{h['draw']}-{h['home_persp_l']} "
                  f"(Tore {h['gf']}:{h['ga']})")
        else:
            print("  H2H: keine direkten Begegnungen")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
