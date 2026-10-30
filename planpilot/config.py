"""Environment presets, seeds, thresholds and LLM provider settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", encoding="utf-8")


@dataclass(frozen=True)
class Preset:
    label: str
    rates: dict[str, int]  # role -> daily rate in INR
    team: dict[str, int]  # role -> default headcount


PRESETS: dict[str, Preset] = {
    "software": Preset(
        label="Software (college placement portal)",
        rates={
            "pm": 5000,
            "analyst": 4000,
            "designer": 3500,
            "developer": 4000,
            "tester": 3000,
            "devops": 4500,
        },
        team={"pm": 1, "analyst": 1, "designer": 1, "developer": 3, "tester": 1, "devops": 1},
    ),
    "event": Preset(
        label="Event (college tech fest)",
        rates={
            "coordinator": 3000,
            "logistics": 2500,
            "marketing": 2800,
            "designer": 2500,
            "tech_crew": 2500,
            "finance": 3000,
            "volunteer_lead": 1500,
        },
        team={
            "coordinator": 1,
            "logistics": 2,
            "marketing": 2,
            "designer": 1,
            "tech_crew": 2,
            "finance": 1,
            "volunteer_lead": 2,
        },
    ),
    "construction": Preset(
        label="Construction (campus lab renovation)",
        rates={
            "site_engineer": 4500,
            "architect": 5000,
            "supervisor": 3000,
            "mason": 1500,
            "electrician": 2000,
            "plumber": 1800,
            "carpenter": 1700,
        },
        team={
            "site_engineer": 1,
            "architect": 1,
            "supervisor": 1,
            "mason": 3,
            "electrician": 2,
            "plumber": 1,
            "carpenter": 2,
        },
    ),
}

DEFAULT_SEED = 42
N_ITERATIONS = 10_000

# RAG status: green if both SPI and CPI >= GREEN, amber if the lower is >= AMBER, else red.
RAG_GREEN = 0.95
RAG_AMBER = 0.85

# EVM: a reporting week is 5 working days. Synthetic progress defaults per environment
# (slip stretches elapsed time, cost_overrun scales spend); the demo CSVs use these.
WEEK_DAYS = 5
AS_OF_SHARE = 0.55  # default status date: this share of the planned duration
PROGRESS_DEFAULTS: dict[str, dict[str, float]] = {
    # tuned on the frozen demo projects to SPI ~0.82 and CPI ~0.90 at the default status date
    "software": {"slip": 1.26, "cost_overrun": 1.1},
    "event": {"slip": 1.31, "cost_overrun": 1.1},
    "construction": {"slip": 1.19, "cost_overrun": 1.1},
}

# add_resource efficiency (coordination overhead, cf. Brooks's law).
DEFAULT_EFFICIENCY = 0.6

# Decision criteria weights per scenario (keys match engine.decision.CRITERIA); each sums to 1.
WEIGHT_SCENARIOS: dict[str, dict[str, float]] = {
    "balanced": {"p80": 0.35, "prob_on_time": 0.30, "cost": 0.25, "spread": 0.10},
    "schedule-first": {"p80": 0.45, "prob_on_time": 0.35, "cost": 0.10, "spread": 0.10},
    "cost-first": {"p80": 0.20, "prob_on_time": 0.20, "cost": 0.50, "spread": 0.10},
}

# LLM providers (OpenAI-compatible). Groq first; Gemini once Groq's daily quota is used up.
PROVIDERS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b",
        "key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": os.getenv("GEMINI_MODEL") or "models/gemini-flash-lite-latest",
        "key_env": "GEMINI_API_KEY",
    },
}
PROVIDER_ORDER = ["groq", "gemini"]
PROMPT_DIR = ROOT / "prompts"
CACHE_DIR = ROOT / "data" / "cache"


def offline_default() -> bool:
    return os.getenv("PLANPILOT_OFFLINE", "") == "1"
