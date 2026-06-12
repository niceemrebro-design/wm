"""
Laedt die Rohdaten (Wissensspeicher-Quelle) neu herunter.
Re-runnable; data/raw/ ist gitignored und wird hierueber wiederhergestellt.

Quelle: martj42/international_results (alle Maenner-Laenderspiele + WM-2026-Plan).
"""
import os
import urllib.request

from util import DATA_RAW

BASE = "https://raw.githubusercontent.com/martj42/international_results/master/"
FILES = ["results.csv", "goalscorers.csv", "shootouts.csv"]


def main():
    os.makedirs(DATA_RAW, exist_ok=True)
    for f in FILES:
        dst = os.path.join(DATA_RAW, f)
        print(f"laden: {f} ...", end=" ", flush=True)
        urllib.request.urlretrieve(BASE + f, dst)
        print(f"OK ({os.path.getsize(dst)//1024} KB)")
    print("Fertig ->", DATA_RAW)


if __name__ == "__main__":
    main()
