"""LLM consistency check: run the plan and risk chains several times per demo brief with the
cache bypassed and a high temperature, and tabulate how much the outputs vary.

Run: python scripts/consistency_check.py [--runs 3] [--envs software event construction] [--resume]

--resume keeps the runs already in docs/consistency.csv that succeeded and redoes the rest.

Writes docs/consistency.csv and docs/consistency.md, and each generated project to
docs/generated/ (the plans Krish scores in docs/rubric.md). Uses the live LLM, so it needs a key.
"""

import argparse
import csv
import statistics
import time
from pathlib import Path

from planpilot.config import ROOT
from planpilot.engine.schedule import cpm
from planpilot.llm.chains import plan_chain, risk_chain
from planpilot.llm.client import LLMClient, LLMError
from planpilot.samples import available_samples, load_sample

TEMPERATURE = 0.7
RATE_LIMIT_WAIT = 65  # seconds: the free tier limits tokens per minute
RATE_LIMIT_RETRIES = 3
DOCS = ROOT / "docs"
FIELDS = [
    "environment",
    "run",
    "provider",
    "tasks",
    "phases",
    "total_most_likely_days",
    "cpm_days",
    "risks",
    "risk_categories",
    "plan_warnings",
    "error",
]


def run_once(client: LLMClient, env: str, run: int, out_dir: Path) -> dict:
    sample = load_sample(env)
    row = dict.fromkeys(FIELDS, "")
    row.update(environment=env, run=run)
    try:
        project, warnings = plan_chain(
            client,
            env,
            sample.brief,
            sample.start_date,
            sample.deadline,
            use_cache=False,
            temperature=TEMPERATURE,
        )
        project, warnings = risk_chain(client, project, use_cache=False, temperature=TEMPERATURE)
    except LLMError as e:
        row.update(provider=client.provider, error=str(e).replace("\n", " ")[:200])
        return row
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{env}_run{run}.json").write_text(
        project.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    row.update(
        provider=client.provider,
        tasks=len(project.tasks),
        phases=len({t.phase for t in project.tasks}),
        total_most_likely_days=f"{sum(t.most_likely for t in project.tasks):g}",
        cpm_days=f"{cpm(project).duration:g}",
        risks=len(project.risks),
        risk_categories=len({r.category for r in project.risks}),
        plan_warnings=len(warnings),
    )
    return row


def markdown(rows: list[dict]) -> str:
    cols = [c for c in FIELDS if c not in ("provider", "error")]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    lines += ["", "Spread across runs (min - max, mean):", ""]
    for env in dict.fromkeys(r["environment"] for r in rows):
        ok = [r for r in rows if r["environment"] == env and not r["error"]]
        if not ok:
            lines.append(f"- {env}: no successful run")
            continue
        parts = []
        for c in ("tasks", "total_most_likely_days", "cpm_days", "risks"):
            v = [float(r[c]) for r in ok]
            parts.append(f"{c} {min(v):g}-{max(v):g} (mean {statistics.mean(v):.1f})")
        lines.append(f"- {env} ({len(ok)} runs): " + "; ".join(parts))
    failed = [r for r in rows if r["error"]]
    if failed:
        lines += ["", f"{len(failed)} run(s) failed after 3 attempts: see consistency.csv."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--envs", nargs="+", default=available_samples())
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    client = LLMClient(offline=False)
    done: dict[tuple[str, int], dict] = {}
    csv_path = DOCS / "consistency.csv"
    if args.resume and csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            done = {
                (r["environment"], int(r["run"])): r for r in csv.DictReader(f) if not r["error"]
            }
    rows = []
    for env in args.envs:
        for run in range(1, args.runs + 1):
            if (env, run) in done:
                rows.append(done[(env, run)])
                continue
            for attempt in range(RATE_LIMIT_RETRIES + 1):
                row = run_once(client, env, run, DOCS / "generated")
                if "rate limit" not in row["error"] or attempt == RATE_LIMIT_RETRIES:
                    break
                time.sleep(RATE_LIMIT_WAIT)
            rows.append(row)
            print(row, flush=True)

    DOCS.mkdir(exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    table = markdown(rows)
    (DOCS / "consistency.md").write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
