"""
Voller Refresh-Lauf — der 'rechne neu'-Befehl.

Nach neuen Spielergebnissen einmal ausfuehren; danach sind predictions/ und
web/data.js aktuell (committen + pushen erledigt der Mensch/Claude separat).

Ablauf:  Rohdaten laden -> Wissensspeicher -> [Kalibrieren] -> Vorhersagen
         -> Turniersimulation -> Web-Daten

Aufruf:
  python3 engine/refresh.py                # voller Lauf inkl. Daten-Download
  python3 engine/refresh.py --no-fetch     # ohne erneuten Download
  python3 engine/refresh.py --calibrate    # zusaetzlich Modell neu kalibrieren
"""
import os
import subprocess
import sys

from util import REPO_ROOT


def run(script, *args):
    print(f"\n▶ {script} {' '.join(args)}".rstrip())
    subprocess.check_call([sys.executable, os.path.join("engine", script), *args], cwd=REPO_ROOT)


def main():
    args = set(sys.argv[1:])
    if "--no-fetch" not in args:
        run("ingest.py")
    run("build_store.py")
    if "--calibrate" in args:
        run("calibrate.py")
    run("predict.py")
    run("montecarlo.py", "25000")
    run("build_web.py")
    print("\n✅ Refresh fertig — predictions/ und web/data.js sind aktuell.")


if __name__ == "__main__":
    main()
