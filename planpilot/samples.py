"""Load the frozen demo projects in data/sample/."""

import json
from pathlib import Path

import pandas as pd
from pydantic import TypeAdapter

from planpilot.models import Option, Project

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
OPTIONS_DIR = SAMPLE_DIR / "options"  # a subfolder, so available_samples() never lists it


def available_samples() -> list[str]:
    return sorted(p.stem for p in SAMPLE_DIR.glob("*.json"))


def load_sample(environment: str) -> Project:
    path = SAMPLE_DIR / f"{environment}.json"
    return Project.model_validate(json.loads(path.read_text(encoding="utf-8")))


def progress_path(environment: str) -> Path:
    return SAMPLE_DIR / f"{environment}_progress.csv"


def load_progress(environment: str) -> pd.DataFrame:
    return pd.read_csv(progress_path(environment), encoding="utf-8")


def load_options(environment: str) -> list[Option]:
    path = OPTIONS_DIR / f"{environment}.json"
    return TypeAdapter(list[Option]).validate_json(path.read_text(encoding="utf-8"))


def demo_options(project: Project) -> list[Option] | None:
    """The hand-written options for a project that is an unmodified frozen demo, else None
    (their task and risk ids mean something else in any other plan)."""
    try:
        frozen = load_sample(project.environment)
    except FileNotFoundError:
        return None
    return load_options(project.environment) if project == frozen else None
