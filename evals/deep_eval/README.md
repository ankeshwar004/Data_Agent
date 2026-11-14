# DeepEval Evaluation Pipeline

Evaluates the Data Agent (`agents/data_agent.py`) on four metrics, using the
generated dataset from `evals/dataset_generator` as ground truth.

| # | Metric | How it is measured |
|---|--------|--------------------|
| 1 | Answer Correctness | Agent's final answer vs. ground truth: DeepEval `GEval` (LLM judge) plus a deterministic numeric check |
| 2 | Execution Tracing | DeepEval `CallbackHandler` trace plus an in-process `TraceRecorder` that asserts nested SQL and ETL spans exist |
| 3 | Task Completion | DeepEval `TaskCompletionMetric`, scored on the full trace |
| 4 | Step Efficiency | DeepEval `StepEfficiencyMetric`, scored on the full trajectory (graph, node, LLM and tool spans), not a node count |

Task Completion and Step Efficiency are trace-only metrics. They are passed to
`dataset.evals_iterator(metrics=...)` and cannot be run on a plain `LLMTestCase`.

## Files

| File | Purpose |
|------|---------|
| `judge.py` | `OpenRouterJudge`, a `DeepEvalBaseLLM` served via OpenRouter. Tries structured output first, then falls back to JSON parsing (free models are unreliable at it) |
| `dataset_adaptor.py` | Loads `evaluation_dataset.json`, converts each case to a `Golden` with a readable expected answer |
| `trajectory_metrics.py` | Metric factories, `numeric_match`, `TraceRecorder`, `check_trace` |
| `run_eval.py` | CLI: runs the agent per golden, scores, writes reports |

## How tracing works

Every node in the three graphs takes `config: RunnableConfig` and forwards it
unchanged into nested calls:

```python
def etl_node(state: DataAgentSchema, config: RunnableConfig) -> DataAgentSchema:
    ...
    response = etl_graph.invoke({...}, config=config)
```

The runner passes both callbacks at the top-level invoke:

```python
graph.invoke({"user_query": q}, config={"callbacks": [deepeval_handler, recorder]})
```

so the SQL subgraph (`curate_ques`, `generate_sql`, `is_safe_sql`,
`execute_sql`, ...) and ETL subgraph (`execute_task`, `financial_etl`, ...)
spans nest under `sql_node` / `etl_node`. Nodes are not decorated and the graphs
are not rewritten. When adding a new node or nested call, accept `config` and
pass it down, otherwise its spans may be missing from the trace.

`check_trace` reports `sql_traced` / `etl_traced` as failed when the final state
shows SQL or ETL attempts but no matching nested spans were recorded.

## Setup

Requires `.env` values `OPENROUTER_API_KEY`, `DATABASE_URL`, `FMP_API_KEY`
(cold-database cases trigger real FMP calls and database writes, so use a
dedicated database if you need runs to be repeatable).

```bash
pip install -r requirements.txt            # includes deepeval
python -m evals.dataset_generator.pipeline # creates eval/datasets/generated/evaluation_dataset.json
```

Optional: `EVAL_JUDGE_MODEL` selects the judge model (default:
`OPENROUTER_MODEL`). Use a stronger model than the free default for numbers you
intend to compare across runs.

## Running

```bash
python -m evals.deep_eval.run_eval --limit 5
python -m evals.deep_eval.run_eval --tags calculation ratio --threshold 0.7 \
    --min-accuracy 0.8 --min-task-completion 0.7
```

| Flag | Meaning |
|------|---------|
| `--dataset` | Path to the dataset JSON (default: generated dataset) |
| `--limit N` | Evaluate only the first N cases |
| `--tags ...` | Only cases with any of these `capability_tags` |
| `--out DIR` | Output directory (default `eval/results/<timestamp>/`) |
| `--threshold` | Per-case pass threshold for all metrics (default 0.7) |
| `--min-accuracy` | Exit code 1 if GEval accuracy is below this |
| `--min-task-completion` | Exit code 1 if mean Task Completion is below this |

Cases run sequentially. A crashed agent run is recorded as a failed case and does
not abort the evaluation.

## Output

Written to the output directory:

- `report.json`: summary plus per-case rows (answer, expected, scores, trace check, attempts)
- `report.md`: human-readable summary, correctness by capability tag, per-case table
- `traces/<case_id>.txt`: indented span tree for each case

Summary fields: `answer_correctness_geval`, `answer_correctness_numeric`,
`trace_coverage`, `mean_spans`, `task_completion_mean/pass_rate`,
`step_efficiency_mean/pass_rate`, `correctness_by_tag`, `crashed`.

Trace-metric scores are also shown in DeepEval's console output.
`collect_trajectory_scores` in `run_eval.py` extracts them best-effort and returns
empty values if the installed DeepEval version exposes results differently. If the
trajectory fields show `null`, adjust that function.

## Tests

```bash
python -m pytest tests/test_eval_helpers.py
```

Offline tests cover the numeric matcher and nested-span capture. The full
pipeline has not been run in CI, since it needs live API keys and a database.

## Limitations

- `numeric_match` is a heuristic (any number in the answer matching within 1%); treat GEval as the headline accuracy and the numeric check as a cross-check.
- Step Efficiency and Task Completion infer the task from the trace root input; they do not use the golden's expected output.
- Judge scores from a weak model are noisy.
