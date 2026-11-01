from eval.run_eval import evaluate, load_cases, run_case, summarize


def test_dataset_expands_to_45_repeatable_cases():
    cases = load_cases()
    assert len(cases) == 45
    assert {case["group"] for case in cases} == {"data_exists", "data_missing", "failure"}


def test_missing_data_is_loaded_before_answering():
    case = next(case for case in load_cases() if case["group"] == "data_missing")
    result = run_case(case, autonomous=True)
    assert result["passed"] is True
    assert result["loaded"] is True


def test_failure_is_bounded_and_never_answered_with_a_value():
    case = next(case for case in load_cases() if case["group"] == "failure")
    result = run_case(case, autonomous=True)
    assert result["passed"] is True
    assert result["loaded"] is False
    assert result["fmp_calls"] == 3
    assert result["error"]


def test_summary_uses_separate_financial_and_failure_rates():
    report = evaluate(load_cases())
    assert report["baseline"]["financial_cases"] == 30
    assert report["autonomous"]["failure_cases"] == 15
    assert report["improvement"]["percentage_points"] >= 0
    assert 0 <= report["autonomous"]["sql_first_attempt_success_rate"] <= 100
    assert 0 <= report["autonomous"]["sql_final_execution_success_rate"] <= 100
    assert report["autonomous"]["etl_complete_request_success_rate"] == 100
    assert report["autonomous"]["etl_records_loaded_correctly"] == {
        "loaded": 15,
        "expected": 15,
        "rate": 100.0,
    }
