"""
Monte-Carlo-Turniersimulation fuer die WM 2026.

- Gruppen werden automatisch aus dem Spielplan abgeleitet (Zusammenhangs-
  komponenten der Gruppenspiele -> 12 Gruppen a 4).
- Pro Lauf: Gruppenphase exakt simuliert (Ergebnisse aus dem kalibrierten
  Poisson-Modell), Tabellen mit Tiebreak Punkte > Tordifferenz > Tore.
  Es kommen Top 2 jeder Gruppe + die 8 besten Gruppendritten weiter (Format 2026).
- K.o.-Phase als zufaelliges Bracket, ueber N Laeufe gemittelt -> Titel-Odds
  unabhaengig von Auslosungs-Glueck. Remis in K.o. via Staerke-gewichtetem
  Elfmeterschiessen aufgeloest.

Output: predictions/tournament.json

CLI:  python3 engine/montecarlo.py [N=10000]
"""
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

from util import DATA_PROC, PRED_DIR
import model


def _load(n):
    return json.load(open(os.path.join(DATA_PROC, n), encoding="utf-8"))


def derive_groups(fixtures, participants):
    parent = {t: t for t in participants}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for f in fixtures:
        parent[find(f["home"])] = find(f["away"])
    comp = defaultdict(list)
    for t in participants:
        comp[find(t)].append(t)
    return [sorted(v) for v in comp.values()]


def pois(lam):
    """Knuth-Sampler — schnell fuer kleine lambda."""
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def main(N=10000, seed=2026):
    random.seed(seed)  # deterministisch -> reproduzierbare Odds, keine Commit-Noise
    elo = _load("elo.json")
    fixtures = _load("fixtures_2026.json")
    parts = sorted(set([f["home"] for f in fixtures] + [f["away"] for f in fixtures]))
    groups = derive_groups(fixtures, parts)
    assert len(groups) == 12, f"{len(groups)} Gruppen statt 12 — Spielplan unvollstaendig?"
    group_of = {t: gi for gi, g in enumerate(groups) for t in g}

    by_group = defaultdict(list)
    for f in fixtures:
        gi = group_of[f["home"]]
        lh, la = model.elo_to_lambdas(elo[f["home"]]["elo"], elo[f["away"]]["elo"], f["neutral"])
        by_group[gi].append((f["home"], f["away"], lh, la))

    def E(t):
        return elo[t]["elo"]

    cnt = defaultdict(lambda: defaultdict(int))
    sumpts = defaultdict(float)
    firsts = defaultdict(int)
    seconds = defaultdict(int)
    rounds = ["r16", "qf", "sf", "final", "winner"]

    for _ in range(N):
        qualifiers, thirds = [], []
        for gi, gms in by_group.items():
            tbl = {t: [0, 0, 0] for t in groups[gi]}  # pts, gd, gf
            for (h, a, lh, la) in gms:
                hg, ag = pois(lh), pois(la)
                if hg > ag:
                    tbl[h][0] += 3
                elif ag > hg:
                    tbl[a][0] += 3
                else:
                    tbl[h][0] += 1; tbl[a][0] += 1
                tbl[h][1] += hg - ag; tbl[a][1] += ag - hg
                tbl[h][2] += hg; tbl[a][2] += ag
            ranked = sorted(groups[gi], key=lambda t: (tbl[t][0], tbl[t][1], tbl[t][2], random.random()),
                            reverse=True)
            for t in groups[gi]:
                sumpts[t] += tbl[t][0]
            firsts[ranked[0]] += 1
            seconds[ranked[1]] += 1
            qualifiers += [ranked[0], ranked[1]]
            t3 = ranked[2]
            thirds.append(((tbl[t3][0], tbl[t3][1], tbl[t3][2], random.random()), t3))
        thirds.sort(reverse=True)
        qualifiers += [t for _, t in thirds[:8]]
        for t in qualifiers:
            cnt[t]["advance"] += 1

        random.shuffle(qualifiers)
        cur = qualifiers
        ri = 0
        while len(cur) > 1:
            nxt = []
            for i in range(0, len(cur), 2):
                A, B = cur[i], cur[i + 1]
                lh, la = model.elo_to_lambdas(E(A), E(B), True)
                hg, ag = pois(lh), pois(la)
                if hg > ag:
                    w = A
                elif ag > hg:
                    w = B
                else:  # Elfmeterschiessen, leicht staerke-gewichtet
                    share = 0.5 + 0.5 * ((E(A) - E(B)) / (abs(E(A) - E(B)) + 200))
                    w = A if random.random() < share else B
                nxt.append(w)
            cur = nxt
            for t in cur:
                cnt[t][rounds[ri]] += 1
            ri += 1

    teams = []
    for t in parts:
        c = cnt[t]
        teams.append({
            "team": t, "group": chr(65 + group_of[t]), "elo": round(E(t), 1),
            "avg_pts": round(sumpts[t] / N, 2),
            "p_first": round(firsts[t] / N, 3), "p_second": round(seconds[t] / N, 3),
            "p_advance": round(c["advance"] / N, 3), "p_r16": round(c["r16"] / N, 3),
            "p_qf": round(c["qf"] / N, 3), "p_sf": round(c["sf"] / N, 3),
            "p_final": round(c["final"] / N, 3), "p_winner": round(c["winner"] / N, 4),
        })
    teams.sort(key=lambda x: -x["p_winner"])

    gt = {}
    for gi, g in enumerate(groups):
        gt[chr(65 + gi)] = [{
            "team": t, "avg_pts": round(sumpts[t] / N, 2),
            "p_advance": round(cnt[t]["advance"] / N, 3),
        } for t in sorted(g, key=lambda t: -sumpts[t])]

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "sims": N,
        "method": ("Monte-Carlo: kalibriertes Poisson-Modell, Gruppenphase exakt "
                   "(Top 2 + 8 beste Dritte), K.o. als zufälliges Bracket über alle Läufe gemittelt"),
        "teams": teams, "groups": gt,
    }
    json.dump(out, open(os.path.join(PRED_DIR, "tournament.json"), "w"), ensure_ascii=False, indent=1)

    print(f"{N} Simulationen. Titel-Favoriten:")
    for t in teams[:10]:
        print(f"  {t['p_winner']*100:5.1f}%  {t['team']:<14} (Gruppe {t['group']}, Elo {t['elo']:.0f}, "
              f"Achtelfinale {t['p_advance']*100:.0f}%)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10000)
