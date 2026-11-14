from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import config
from agents.data_agent import build_data_agent_graph
from database.connection import db_connection

from evals.deep_eval.dataset_adaptor import DEFAULT_DATASET_PATH, build_dataset
from evals.deep_eval.judge import OpenRouterJudge
from evals.deep_eval.trajectory_metrics import (
    TraceRecorder,
    build_correctness_metric,
    build_trajectory_metrics,
    check_trace,
    numeric_match,
)

logger = logging.getLogger(__name__)

_STATE_KEYS = (
    "final_answer", "generated_sql_query", "sql_attempts", "attempts",
    "etl_attempt_results", "sql_attempt_results", "observations",
)


def run_agent(graph, golden, callback_cls) -> dict:
    """Invoke the agent once. Callbacks are passed via the RunnableConfig, which the
    nodes forward into nested SQL/ETL subgraphs, so all spans land in both traces."""
    meta = golden.additional_metadata or {}
    recorder = TraceRecorder()
    handler = callback_cls(
        name="data_agent",
        tags=["eval"],
        metadata={"case_id": meta.get("case_id")},
    )
    row = {
        "case_id": meta.get("case_id"),
        "question": golden.input,
        "expected": golden.expected_output,
        "expected_value": meta.get("expected_value"),
        "tags": meta.get("tags", []),
        "error": None,
    }
    state: dict = {}
    try:
        state = graph.invoke(
            {"user_query": golden.input},
            config={"callbacks": [handler, recorder]},
        )
    except Exception as exc:  # a crashed run is a failed case, not a crashed eval
        logger.exception("Agent crashed on %s", row["case_id"])
        row["error"] = f"{type(exc).__name__}: {exc}"
    for key in _STATE_KEYS:
        row[key] = state.get(key)
    row["actual_output"] = (state.get("final_answer") or "").strip()
    row["trace"] = check_trace(recorder, state)
    row["trace_tree"] = recorder.tree()
    row["numeric_match"] = numeric_match(row["actual_output"], row["expected_value"])
    return row


def score_correctness(rows: list[dict], judge, threshold: float) -> None:
    from deepeval.test_case import LLMTestCase

    for row in rows:
        row["correct_score"], row["correct_reason"] = None, None
        if not row["actual_output"]:
            row["correct"] = False
            row["correct_reason"] = row["error"] or "agent produced no answer"
            continue
        metric = build_correctness_metric(judge, threshold)
        try:
            metric.measure(
                LLMTestCase(
                    input=row["question"],
                    actual_output=row["actual_output"],
                    expected_output=row["expected"],
                )
            )
            row["correct_score"] = metric.score
            row["correct_reason"] = metric.reason
            row["correct"] = bool(metric.is_successful())
        except Exception as exc:
            row["correct"] = False
            row["correct_reason"] = f"judge error: {exc}"


def _mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 4) if values else None


def summarize(rows: list[dict], trajectory: dict) -> dict:
    n = len(rows) or 1
    by_tag: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        for tag in r["tags"] or ["untagged"]:
            by_tag[tag].append(bool(r.get("correct")))
    return {
        "cases": len(rows),
        "crashed": sum(1 for r in rows if r["error"]),
        "answer_correctness_geval": round(sum(bool(r.get("correct")) for r in rows) / n, 4),
        "answer_correctness_numeric": round(sum(r["numeric_match"] for r in rows) / n, 4),
        "trace_coverage": round(
            sum(r["trace"]["sql_traced"] and r["trace"]["etl_traced"] for r in rows) / n, 4
        ),
        "mean_spans": _mean([r["trace"]["total_spans"] for r in rows]),
        "task_completion_mean": trajectory.get("Task Completion", {}).get("mean"),
        "task_completion_pass_rate": trajectory.get("Task Completion", {}).get("pass_rate"),
        "step_efficiency_mean": trajectory.get("Step Efficiency", {}).get("mean"),
        "step_efficiency_pass_rate": trajectory.get("Step Efficiency", {}).get("pass_rate"),
        "correctness_by_tag": {t: round(sum(v) / len(v), 4) for t, v in by_tag.items()},
    }


def collect_trajectory_scores(result) -> dict:
    """Best-effort extraction of per-metric trace scores from evaluate()/iterator results.
    Returns {} if the installed DeepEval does not expose them (scores are still in the
    DeepEval console/Confident AI output)."""
    scores: dict[str, list] = defaultdict(list)
    try:
        for tr in getattr(result, "test_results", None) or []:
            for md in getattr(tr, "metrics_data", None) or []:
                scores[md.name].append((md.score, bool(md.success)))
    except Exception:  # pragma: no cover - API drift
        return {}
    out = {}
    for name, vals in scores.items():
        clean = [s for s, _ in vals if s is not None]
        out[name.replace(" [GEval]", "")] = {
            "mean": _mean(clean),
            "pass_rate": round(sum(ok for _, ok in vals) / len(vals), 4) if vals else None,
        }
    return out


def write_reports(out: Path, rows: list[dict], summary: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces").mkdir(exist_ok=True)
    slim = [{k: v for k, v in r.items() if k != "trace_tree"} for r in rows]
    (out / "report.json").write_text(
        json.dumps({"summary": summary, "cases": slim}, indent=2, default=str), encoding="utf-8"
    )
    for r in rows:
        (out / "traces" / f"{r['case_id']}.txt").write_text(r["trace_tree"] or "(no spans)", encoding="utf-8")

    lines = ["# Data Agent DeepEval report", "", "## Summary", ""]
    lines += [f"- **{k}**: {v}" for k, v in summary.items() if k != "correctness_by_tag"]
    lines += ["", "### Correctness by capability tag", ""]
    lines += [f"- {t}: {v}" for t, v in summary["correctness_by_tag"].items()]
    lines += [
        "", "## Cases", "",
        "| case | correct | numeric | trace ok | sql spans | etl spans | sql tries | etl tries |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        t = r["trace"]
        lines.append(
            f"| {r['case_id']} | {r.get('correct')} | {r['numeric_match']} | "
            f"{t['sql_traced'] and t['etl_traced']} | {len(t['sql_spans'])} | {len(t['etl_spans'])} | "
            f"{r.get('sql_attempts')} | {r.get('attempts')} |"
        )
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tags", nargs="*", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--threshold", type=float, default=0.7, help="per-case metric threshold")
    p.add_argument("--min-accuracy", type=float, default=0.0, help="exit 1 if GEval accuracy is below")
    p.add_argument("--min-task-completion", type=float, default=0.0)
    return p.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    from deepeval.integrations.langchain import CallbackHandler

    judge = OpenRouterJudge()
    dataset = build_dataset(args.dataset, args.limit, args.tags)
    if not dataset.goldens:
        logger.error("No cases selected.")
        return 1
    metrics = build_trajectory_metrics(judge, args.threshold)
    out = Path(args.out or Path(config.PROJECT_ROOT) / "eval/results" / datetime.now().strftime("%Y%m%d_%H%M%S"))

    db_connection.init_db()
    rows: list[dict] = []
    trajectory: dict = {}
    try:
        graph = build_data_agent_graph()
        # Task Completion + Step Efficiency are trace-level: evals_iterator scores each
        # traced run's full trajectory after the loop body returns.
        iterator = dataset.evals_iterator(metrics=metrics)
        for golden in iterator:
            rows.append(run_agent(graph, golden, CallbackHandler))
        trajectory = collect_trajectory_scores(getattr(dataset, "evaluation_result", None) or iterator)
        score_correctness(rows, judge, args.threshold)
    finally:
        db_connection.close_db()

    summary = summarize(rows, trajectory)
    write_reports(out, rows, summary)

    print(json.dumps(summary, indent=2))
    print(f"\nReports written to {out}")

    ok = summary["answer_correctness_geval"] >= args.min_accuracy
    tc = summary.get("task_completion_mean")
    if tc is not None and tc < args.min_task_completion:
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
