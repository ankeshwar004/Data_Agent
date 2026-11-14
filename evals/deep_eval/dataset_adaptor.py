from __future__ import annotations

import json
from pathlib import Path

from deepeval.dataset import EvaluationDataset, Golden

from config import OUTPUT_DIR

DEFAULT_DATASET_PATH = OUTPUT_DIR / "evaluation_dataset.json"


def load_cases(path: Path | str = DEFAULT_DATASET_PATH,limit: int | None = None,tags: list[str] | None = None) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found at {path}. "
            "Generate it with: python -m evals.dataset_generator.pipeline"
        )
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    if tags:
        wanted = set(tags)
        cases = [c for c in cases if wanted & set(c.get("capability_tags", []))]
    return cases[:limit] if limit else cases


def render_expected(case: dict) -> str:
    """Human-readable ground truth so the judge can compare value, unit and scale."""
    
    answer = case["expected"]["answer"]
    value, unit = answer["value"], answer.get("unit")
    year = case.get("year")
    subject = f"{case['ticker']} FY{year}" if year else case["ticker"]
    if isinstance(value, bool):
        details = answer.get("details") or {}
        return f"{'Yes' if value else 'No'} ({subject}; {json.dumps(details, default=str)})"
    unit_text = f" {unit}" if unit else ""
    return f"{value}{unit_text} ({subject}, {case.get('metric')}, {case['expected']['operation']})"


def to_golden(case: dict) -> Golden:
    expected = case["expected"]
    return Golden(
        input=case["question"],
        expected_output=render_expected(case),
        additional_metadata={
            "case_id": case["id"],
            "ticker": case["ticker"],
            "year": case.get("year"),
            "operation": expected["operation"],
            "tags": case.get("capability_tags", []),
            "expected_value": expected["answer"]["value"],
            "unit": expected["answer"].get("unit"),
        },
    )


def build_dataset(
    path: Path | str = DEFAULT_DATASET_PATH,
    limit: int | None = None,
    tags: list[str] | None = None,
) -> EvaluationDataset:
    cases = load_cases(path, limit, tags)
    return EvaluationDataset(goldens=[to_golden(c) for c in cases])
