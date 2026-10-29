"""Load the frozen demo projects in data/sample/."""

import json
from pathlib import Path

import pandas as pd

from planpilot.models import Project

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def available_samples() -> list[str]:
    return sorted(p.stem for p in SAMPLE_DIR.glob("*.json"))


def load_sample(environment: str) -> Project:
    path = SAMPLE_DIR / f"{environment}.json"
    return Project.model_validate(json.loads(path.read_text(encoding="utf-8")))


def progress_path(environment: str) -> Path:
    return SAMPLE_DIR / f"{environment}_progress.csv"


def load_progress(environment: str) -> pd.DataFrame:
    return pd.read_csv(progress_path(environment), encoding="utf-8")
