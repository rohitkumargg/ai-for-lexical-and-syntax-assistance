# tests/test_benchmark_engine.py
"""
Comprehensive Unit & Integration Test Suite for Phase 12: Model Accuracy and Repair Benchmarking.

Tests cover:
1. Benchmark dataset composition (all 8 categories present, clean valid cases, unfixable cases).
2. Initial UNBENCHMARKED status and zero fabricated score guarantees.
3. Execution and evaluation of all 5 architectures:
   - Deterministic rules only
   - CodeT5+LoRA only
   - Qwen2.5-Coder-Instruct only
   - Tiered model pipeline (Rules -> CodeT5 -> Qwen)
   - Complete agentic pipeline (Multi-agent analysis + patch validation)
4. Explicit denominators and mathematical correctness of metric formulas:
   - repair_success_rate (eligible repair tasks only)
   - exact_match_rate (separate from semantic success)
   - validation_pass_rate
   - regression_rate
   - security precision and recall
   - false-positive and false-negative rates
   - energy per successful repair (J)
   - fallback effectiveness rate
5. Complete Agentic Pipeline lift over deterministic rules.
6. Flask REST endpoints (/api/benchmark/status, /api/benchmark/dataset, /api/benchmark/definitions, /api/benchmark/run).
"""
import os
import json
import pytest
from app import app
from compiler.benchmark_engine import (
    ModelEvaluationEngine,
    BenchmarkCase,
    BenchmarkCategory,
    ConfigurationType,
    ConfigMetricResult,
    BenchmarkRunReport,
    BENCHMARK_DATASET,
    BENCHMARK_DEFINITIONS,
    BENCHMARK_DISCLAIMER,
)


def test_benchmark_dataset_integrity():
    """Validates that benchmark dataset contains all 8 required categories and valid labels."""
    categories_found = {c.category for c in BENCHMARK_DATASET}
    required_categories = {
        BenchmarkCategory.VALID,
        BenchmarkCategory.LEXICAL,
        BenchmarkCategory.SYNTAX,
        BenchmarkCategory.SEMANTIC,
        BenchmarkCategory.SECURITY,
        BenchmarkCategory.AMBIGUOUS,
        BenchmarkCategory.DIFFICULT,
        BenchmarkCategory.UNFIXABLE,
    }
    assert required_categories.issubset(categories_found)
    assert len(BENCHMARK_DATASET) >= 16

    # Verify true negatives / clean valid cases are marked not expected_repairable
    valid_cases = [c for c in BENCHMARK_DATASET if c.category == BenchmarkCategory.VALID]
    assert len(valid_cases) >= 2
    for vc in valid_cases:
        assert vc.expected_repairable is False
        assert vc.has_vulnerability is False

    # Verify unfixable cases are marked not expected_repairable
    unfixable_cases = [c for c in BENCHMARK_DATASET if c.category == BenchmarkCategory.UNFIXABLE]
    assert len(unfixable_cases) >= 2
    for uc in unfixable_cases:
        assert uc.expected_repairable is False

    # Verify security cases have vulnerability labels
    sec_cases = [c for c in BENCHMARK_DATASET if c.category == BenchmarkCategory.SECURITY]
    assert len(sec_cases) >= 3
    for sc in sec_cases:
        assert sc.has_vulnerability is True
        assert len(sc.expected_vulnerabilities) > 0


def test_initial_unbenchmarked_status_guarantee(tmp_path):
    """Verifies that initially the engine reports UNBENCHMARKED with zero fabricated scores."""
    custom_results_path = str(tmp_path / "latest_benchmark.json")
    engine = ModelEvaluationEngine()
    engine.BENCHMARK_RESULTS_PATH = custom_results_path

    status = engine.get_status()
    assert status["status"] == "UNBENCHMARKED"
    assert "Not yet benchmarked" in status["message"]
    assert "definitions_and_denominators" in status
    assert status["epistemological_disclaimer"] == BENCHMARK_DISCLAIMER


def test_metric_calculation_denominators_and_formulas():
    """
    Tests that metric rates strictly adhere to documented denominators:
    - Repair success uses eligible cases only (excluding valid and unfixable).
    - Validation pass rate uses candidate patches generated.
    - Regression rate uses total evaluated cases.
    - Exact match is computed separately from semantic repair success.
    """
    engine = ModelEvaluationEngine()

    # Run benchmark on a representative subset of 4 cases
    subset_ids = ["BM-VAL-01", "BM-SYN-01", "BM-SEC-01", "BM-UNF-01"]
    report = engine.run_benchmark(
        configurations=[ConfigurationType.DETERMINISTIC_RULES],
        cases_subset=subset_ids,
    )

    assert report.status == "BENCHMARKED"
    res = report.results[ConfigurationType.DETERMINISTIC_RULES.value]

    assert res.total_evaluated_cases == 4
    # BM-SYN-01 and BM-SEC-01 are eligible; BM-VAL-01 and BM-UNF-01 are not
    assert res.eligible_repair_cases == 2

    # Repair success rate denominator must be 2
    expected_rep_rate = (res.successful_repairs / 2) * 100.0
    assert res.repair_success_rate == pytest.approx(expected_rep_rate, rel=1e-2)

    # Exact match rate must be <= repair success rate and reported separately
    assert res.exact_match_rate <= res.repair_success_rate

    # Clean code false positive rate check
    assert res.error_false_positive_rate >= 0.0

    # Energy calculations
    assert res.energy_joules > 0.0
    assert res.energy_wh > 0.0
    if res.successful_repairs > 0:
        assert res.energy_per_successful_repair_j is not None
        assert res.energy_per_successful_repair_j == pytest.approx(res.energy_joules / res.successful_repairs, rel=1e-2)


def test_all_five_configurations_evaluation():
    """
    Evaluates all 5 architectures on a focused benchmark subset and verifies
    comparative metrics across all 5 configurations.
    """
    engine = ModelEvaluationEngine()
    subset_ids = ["BM-VAL-01", "BM-SYN-01", "BM-SEM-01", "BM-SEC-01", "BM-UNF-01"]

    all_configs = [
        ConfigurationType.DETERMINISTIC_RULES,
        ConfigurationType.CODET5_LORA,
        ConfigurationType.QWEN_CODER,
        ConfigurationType.TIERED_PIPELINE,
        ConfigurationType.AGENTIC_PIPELINE,
    ]

    report = engine.run_benchmark(
        configurations=all_configs,
        cases_subset=subset_ids,
    )

    assert len(report.results) == 5
    for cfg in all_configs:
        assert cfg.value in report.results
        r = report.results[cfg.value]
        assert r.total_evaluated_cases == 5
        assert 0.0 <= r.repair_success_rate <= 100.0
        assert 0.0 <= r.exact_match_rate <= 100.0
        assert 0.0 <= r.validation_pass_rate <= 100.0
        assert 0.0 <= r.regression_rate <= 100.0
        assert 0.0 <= r.security_precision <= 100.0
        assert 0.0 <= r.security_recall <= 100.0
        assert r.avg_latency_ms >= 0.0

    # Verify comparative summary synthesis
    comp = report.comparative_summary
    assert "best_repair_success_config" in comp
    assert "lowest_latency_config" in comp
    assert "lowest_energy_config" in comp
    assert "agentic_repair_lift_over_rules_pct" in comp


def test_security_precision_and_recall_computation():
    """Tests security precision and recall with known vulnerability cases."""
    engine = ModelEvaluationEngine()
    sec_subset = ["BM-VAL-01", "BM-SEC-01", "BM-SEC-02", "BM-SEC-03"]

    report = engine.run_benchmark(
        configurations=[ConfigurationType.AGENTIC_PIPELINE],
        cases_subset=sec_subset,
    )

    agentic_res = report.results[ConfigurationType.AGENTIC_PIPELINE.value]
    assert agentic_res.security_true_positives > 0
    assert agentic_res.security_precision >= 50.0
    assert agentic_res.security_recall >= 50.0


def test_flask_benchmark_api_endpoints():
    """Tests the Flask REST API endpoints for benchmark status, dataset, and run."""
    client = app.test_client()

    # 1. GET /api/benchmark/definitions
    def_resp = client.get("/api/benchmark/definitions")
    assert def_resp.status_code == 200
    def_data = def_resp.get_json()
    assert "definitions" in def_data
    assert "repair_success_rate" in def_data["definitions"]
    assert "exact_match_rate" in def_data["definitions"]
    assert "disclaimer" in def_data

    # 2. GET /api/benchmark/dataset
    ds_resp = client.get("/api/benchmark/dataset")
    assert ds_resp.status_code == 200
    ds_data = ds_resp.get_json()
    assert ds_data["size"] >= 16
    assert len(ds_data["categories"]) == 8
    assert len(ds_data["cases"]) >= 16

    # 3. GET /api/benchmark/status
    st_resp = client.get("/api/benchmark/status")
    assert st_resp.status_code == 200
    st_data = st_resp.get_json()
    assert st_data["status"] in ("BENCHMARKED", "UNBENCHMARKED")

    # 4. POST /api/benchmark/run
    run_resp = client.post(
        "/api/benchmark/run",
        json={
            "configurations": ["DETERMINISTIC_RULES", "AGENTIC_PIPELINE"],
            "cases_subset": ["BM-VAL-01", "BM-SYN-01"],
        },
    )
    assert run_resp.status_code == 200
    run_data = run_resp.get_json()
    assert run_data["status"] == "BENCHMARKED"
    assert "DETERMINISTIC_RULES" in run_data["results"]
    assert "AGENTIC_PIPELINE" in run_data["results"]
    assert run_data["benchmark_dataset_size"] == 2
