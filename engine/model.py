"""
Statistisches Ergebnis-Modell (Elo -> erwartete Tore -> Poisson/Dixon-Coles).

Dies ist ein WERKZEUG, das dem Orakel Basiswahrscheinlichkeiten liefert.
Die Parameter (base_total, goals_per_elo, home_adv_goals, rho) werden in der
Kalibrierungsphase gegen echte WM-Historie nachjustiert.
"""
import math

# Default-Parameter (Phase 0 — werden per Backtesting kalibriert)
BASE_TOTAL = 2.6        # durchschnittliche Gesamttore international
GOALS_PER_ELO = 0.0035  # Tor-Vorsprung pro Elo-Punkt Differenz
HOME_ADV_GOALS = 0.35   # Heim-Tor-Bonus (0 bei neutralem Platz)
RHO = -0.13             # Dixon-Coles-Korrektur fuer knappe Ergebnisse


def elo_to_lambdas(elo_h, elo_a, neutral,
                   base_total=BASE_TOTAL, goals_per_elo=GOALS_PER_ELO,
                   home_adv_goals=HOME_ADV_GOALS):
    hadv = 0.0 if neutral else home_adv_goals
    mu_d = (elo_h - elo_a) * goals_per_elo + hadv  # erwartete Tordifferenz (Heim - Auswaerts)
    lh = max(0.18, base_total / 2 + mu_d / 2)
    la = max(0.18, base_total / 2 - mu_d / 2)
    return lh, la


def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _dc_tau(x, y, lh, la, rho=RHO):
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh, la, maxg=8):
    M = [[_pois(i, lh) * _pois(j, la) * _dc_tau(i, j, lh, la)
          for j in range(maxg + 1)] for i in range(maxg + 1)]
    s = sum(sum(row) for row in M)
    return [[v / s for v in row] for row in M]


def outcome_probs(M):
    n = len(M)
    ph = sum(M[i][j] for i in range(n) for j in range(n) if i > j)
    pd_ = sum(M[i][i] for i in range(n))
    pa = sum(M[i][j] for i in range(n) for j in range(n) if i < j)
    return ph, pd_, pa


def top_scorelines(M, n=3):
    cells = [((i, j), M[i][j]) for i in range(len(M)) for j in range(len(M))]
    cells.sort(key=lambda x: -x[1])
    return cells[:n]
