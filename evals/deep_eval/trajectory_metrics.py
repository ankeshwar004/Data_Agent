from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

CORRECTNESS_CRITERIA = (
    "Determine whether the actual output answers the question with the same result as "
    "the expected output. Numeric values must match within rounding; units and scale "
    "(thousands, millions, billions) must agree; percentages must match to about 1%. "
    "Yes/No answers must agree. An output that says the request could not be processed, "
    "or that gives no value, is incorrect."
)


def build_trajectory_metrics(judge, threshold: float = 0.7) -> list:
    """Trace-scope metrics. They score the whole ordered trajectory (graph, node,
    LLM and tool spans), not just a node count. Trace-only: pass them to
    `dataset.evals_iterator(metrics=...)`."""
    from deepeval.metrics import StepEfficiencyMetric, TaskCompletionMetric

    return [
        TaskCompletionMetric(threshold=threshold, model=judge, include_reason=True),
        StepEfficiencyMetric(threshold=threshold, model=judge, include_reason=True),
    ]


def build_correctness_metric(judge, threshold: float = 0.7):
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    return GEval(
        name="Answer Correctness",
        criteria=CORRECTNESS_CRITERIA,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=threshold,
        model=judge,
    )


# ------------------------------------------------------------ deterministic check
_NUM = re.compile(
    r"(-?\$?\s*\d[\d,]*(?:\.\d+)?)\s*(trillion|billion|million|thousand|tn|bn|b|m|k|%)?",
    re.IGNORECASE,
)
_SCALE = {
    "trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3,
}


def extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for raw, suffix in _NUM.findall(text or ""):
        try:
            value = float(raw.replace("$", "").replace(",", "").replace(" ", ""))
        except ValueError:
            continue
        suffix = (suffix or "").lower()
        numbers.append(value)
        if suffix in _SCALE:
            numbers.append(value * _SCALE[suffix])
    return numbers


def numeric_match(actual_text: str, expected, rel_tol: float = 0.01) -> bool:
    """True if the answer text contains the expected value (number or boolean)."""
    text = (actual_text or "").lower()
    if isinstance(expected, bool):
        positive = re.search(r"\b(yes|true|profit(?:able)?|greater|higher|exceeds?)\b", text)
        negative = re.search(r"\b(no|false|loss|not|less|lower|did not)\b", text)
        if expected:
            return bool(positive) and not (negative and not positive)
        return bool(negative)
    for number in extract_numbers(actual_text):
        if expected == 0:
            if abs(number) < 1e-9:
                return True
        elif abs(number - expected) <= abs(expected) * rel_tol:
            return True
    return False


# ------------------------------------------------------------------ trace recorder
@dataclass
class Span:
    run_id: UUID
    parent_run_id: UUID | None
    name: str
    kind: str
    start: float
    end: float | None = None
    error: str | None = None
    node: str | None = None


@dataclass(eq=False)  # keep identity hash: callbacks are stored in sets
class TraceRecorder(BaseCallbackHandler):
    """Records every chain/tool/LLM run so nesting can be asserted and printed."""

    spans: dict[UUID, Span] = field(default_factory=dict)
    order: list[UUID] = field(default_factory=list)

    raise_error = False

    def _start(self, kind, run_id, parent_run_id, serialized, kwargs, metadata=None):
        name = (
            kwargs.get("name")
            or (serialized or {}).get("name")
            or ((serialized or {}).get("id") or [kind])[-1]
        )
        node = (metadata or {}).get("langgraph_node")
        self.spans[run_id] = Span(run_id, parent_run_id, str(name), kind, time.time(), node=node)
        self.order.append(run_id)

    def _end(self, run_id, error=None):
        span = self.spans.get(run_id)
        if span:
            span.end = time.time()
            span.error = str(error) if error else None

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, metadata=None, **kwargs):
        self._start("chain", run_id, parent_run_id, serialized, kwargs, metadata)

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self._end(run_id)

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, metadata=None, **kwargs):
        self._start("tool", run_id, parent_run_id, serialized, kwargs, metadata)

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._end(run_id)

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, metadata=None, **kwargs):
        self._start("llm", run_id, parent_run_id, serialized, kwargs, metadata)

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, metadata=None, **kwargs):
        self._start("llm", run_id, parent_run_id, serialized, kwargs, metadata)

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._end(run_id)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    # -- queries
    def ancestors(self, run_id: UUID) -> list[Span]:
        chain, current = [], self.spans.get(run_id)
        while current and current.parent_run_id in self.spans:
            current = self.spans[current.parent_run_id]
            chain.append(current)
        return chain

    def names_under(self, ancestor_name: str) -> list[str]:
        """Names of all spans that have an ancestor (or node tag) named `ancestor_name`."""
        found = []
        for run_id in self.order:
            span = self.spans[run_id]
            if any(a.name == ancestor_name or a.node == ancestor_name for a in self.ancestors(run_id)):
                found.append(span.name)
        return found

    def tree(self) -> str:
        children: dict[UUID | None, list[UUID]] = {}
        for run_id in self.order:
            parent = self.spans[run_id].parent_run_id
            children.setdefault(parent if parent in self.spans else None, []).append(run_id)
        lines: list[str] = []

        def walk(parent, depth):
            for run_id in children.get(parent, []):
                span = self.spans[run_id]
                ms = f"{(span.end - span.start) * 1000:.0f}ms" if span.end else "?"
                err = f" ERROR={span.error}" if span.error else ""
                lines.append(f"{'  ' * depth}[{span.kind}] {span.name} ({ms}){err}")
                walk(run_id, depth + 1)

        walk(None, 0)
        return "\n".join(lines)


SQL_SPANS = {"curate_ques", "generate_sql", "is_safe_sql", "execute_sql", "represent_final_answer", "canceled_sql"}
ETL_SPANS = {"execute_task", "financial_etl", "company_profile_etl", "llm_node", "tool_node"}


def check_trace(recorder: TraceRecorder, final_state: dict | None) -> dict:
    """Verify nested SQL/ETL execution is visible in the captured trace."""
    final_state = final_state or {}
    sql = [n for n in recorder.names_under("sql_node") if n in SQL_SPANS]
    etl = [n for n in recorder.names_under("etl_node") if n in ETL_SPANS]
    etl_needed = bool(final_state.get("etl_attempt_results"))
    sql_needed = bool(final_state.get("sql_attempt_results"))
    kinds = [s.kind for s in recorder.spans.values()]
    return {
        "sql_traced": bool(sql) or not sql_needed,
        "etl_traced": bool(etl) or not etl_needed,
        "sql_spans": sql,
        "etl_spans": etl,
        "llm_calls": kinds.count("llm"),
        "tool_calls": kinds.count("tool"),
        "total_spans": len(recorder.spans),
    }
