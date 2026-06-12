"""
Schneller Selbsttest / Smoke-Test der Engine (reine Standardbibliothek,
keine externen Abhaengigkeiten noetig). Prueft, dass der Wissensspeicher da ist
und das Modell konsistente Wahrscheinlichkeiten liefert.

Aufruf:  python3 engine/selfcheck.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util import DATA_PROC  # noqa: E402
import model  # noqa: E402


def main():
    elo = json.load(open(os.path.join(DATA_PROC, "elo.json"), encoding="utf-8"))
    fixtures = json.load(open(os.path.join(DATA_PROC, "fixtures_2026.json"), encoding="utf-8"))
    assert len(fixtures) >= 72, f"Erwarte >=72 Fixtures, habe {len(fixtures)}"
    assert "Spain" in elo and "Curaçao" in elo, "Teams im Elo-Speicher fehlen"

    lh, la = model.elo_to_lambdas(elo["Spain"]["elo"], elo["Curaçao"]["elo"], True)
    M = model.score_matrix(lh, la)
    ph, pd_, pa = model.outcome_probs(M)
    s = ph + pd_ + pa
    assert abs(s - 1.0) < 1e-6, f"Wahrscheinlichkeiten summieren nicht zu 1: {s}"
    assert ph > pa, "Spanien sollte gegen Curaçao klar favorisiert sein"
    assert model.CALIBRATION is not None, "Kalibrierung (params.json) nicht geladen"

    print(f"OK · Spain–Curaçao P {ph:.0%}/{pd_:.0%}/{pa:.0%} · Summe {s:.4f} · "
          f"Fixtures {len(fixtures)} · kalibriert (LogLoss {model.CALIBRATION.get('holdout_logloss')})")


if __name__ == "__main__":
    main()
