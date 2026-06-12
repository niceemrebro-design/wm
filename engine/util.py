"""Gemeinsame Pfade & Helfer für die Engine."""
import os

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ENGINE_DIR)
DATA_RAW = os.path.join(REPO_ROOT, "data", "raw")
DATA_PROC = os.path.join(REPO_ROOT, "data", "processed")
PRED_DIR = os.path.join(REPO_ROOT, "predictions")


def results_csv_path():
    return os.path.join(DATA_RAW, "results.csv")


def is_neutral(val):
    return str(val).strip().upper() == "TRUE" or val is True
