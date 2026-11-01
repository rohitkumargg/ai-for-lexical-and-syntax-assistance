# tests/test_green_engine.py
"""
Comprehensive Unit & Integration Test Suite for Phase 11: Green Metrics Engine.

Tests cover:
1. LocalGreenMetricsEngine initialization, stage lifecycle, and resource sampling.
2. Direct hardware measurements vs statistical energy & CO2 estimations.
3. Linear power model calculations (Joules, Watt-hours, grams and kg CO2-eq).
4. Energy & latency per successfully validated repair.
5. Green Metrics Score (0 to 100) normalization against configurable baselines.
6. Avoided redundant computation bonuses (rule-first repair, zero retries, bounded context).
7. Unconditional preservation of security checks and validation rigor (QualityIntegrityTradeoff).
8. Legacy build_green_report interface compatibility.
9. Flask REST endpoints (/api/green/config, /api/green/measure, /api/green/history).
"""
import pytest
from app import app
from compiler.green_engine import (
    LocalGreenMetricsEngine,
    GreenMetricsReport,
    EnergyAndEmissions,
    GreenBaseline,
    GreenScoreConfig,
    QualityIntegrityTradeoff,
    ModelResourceMetrics,
    MeasurementType,
    GREEN_METRICS_DISCLAIMER,
)
from compiler.green_scorer import build_green_report
from compiler.green_logger import GreenLogger


def test_engine_initialization_and_weights_validation():
    """Validates baseline and configuration weights sum constraint."""
    engine = LocalGreenMetricsEngine()
    assert engine.baseline.baseline_latency_ms == 1200.0
    assert engine.baseline.baseline_energy_j == 40.0

    # Custom valid config
    valid_cfg = GreenScoreConfig(
        weight_time=0.4,
        weight_resource=0.2,
        weight_energy=0.2,
        weight_avoided_computation=0.2,
    )
    valid_cfg.validate()
    custom_engine = LocalGreenMetricsEngine(config=valid_cfg)
    assert custom_engine.config.weight_time == 0.4

    # Invalid config weights
    invalid_cfg = GreenScoreConfig(weight_time=0.5, weight_resource=0.5, weight_energy=0.5, weight_avoided_computation=0.5)
    with pytest.raises(ValueError, match="must sum to 1.0"):
        invalid_cfg.validate()


def test_stage_timing_and_resource_lifecycle():
    """Tests start_run, start_stage, end_stage, and sample_resources."""
    engine = LocalGreenMetricsEngine()
    engine.start_run()
    engine.start_stage("lexical")
    engine.end_stage("lexical")
    engine.start_stage("syntax_repair")
    engine.end_stage("syntax_repair")

    assert "lexical" in engine._stage_durations
    assert "syntax_repair" in engine._stage_durations
    assert engine._peak_rss > 0

    report = engine.build_report(
        repair_success=True,
        validated_repairs_count=1,
    )
    assert isinstance(report, GreenMetricsReport)
    assert report.total_latency_ms >= 0.0
    assert 0.0 <= report.green_score <= 100.0
    assert report.hotspot in ("lexical", "syntax_repair", "overall pipeline")


def test_energy_and_emissions_calculations():
    """
    Verifies that the linear power model accurately computes energy in Joules,
    Watt-hours, and CO2 emissions in grams and kilograms.
    """
    engine = LocalGreenMetricsEngine(
        idle_power_w=10.0,
        cpu_tdp_w=40.0,
        gpu_power_w=30.0,
        grid_carbon_intensity=500.0,  # 500 g CO2 / kWh
    )

    # 1 second total runtime with zero retries
    report = engine.build_report(
        total_runtime_ms=1000.0,
        stage_ms={"analysis": 500.0, "validation": 500.0},
        validated_repairs_count=1,
        repair_success=True,
    )
    energy = report.energy_metrics

    # Check units consistency: 1 Wh = 3600 Joules
    assert energy.energy_joules > 0.0
    assert abs(energy.energy_wh - (energy.energy_joules / 3600.0)) < 0.0001
    assert abs(energy.energy_kwh - (energy.energy_wh / 1000.0)) < 0.000001

    # Check emissions: CO2 grams = kWh * 500.0, CO2 kg = grams / 1000
    expected_grams = energy.energy_kwh * 500.0
    assert abs(energy.co2_grams - expected_grams) < 0.001
    assert abs(energy.co2_kg - (expected_grams / 1000.0)) < 0.00001

    # Energy per validated repair
    assert energy.energy_per_validated_repair_j is not None
    assert energy.energy_per_validated_repair_j == pytest.approx(energy.energy_joules, rel=1e-3)
    assert energy.latency_per_validated_repair_ms == pytest.approx(1000.0, rel=1e-3)


def test_distinguish_directly_measured_vs_estimated():
    """
    Verifies epistemological distinction: energy and CO2 are explicitly
    marked as STATISTICALLY_ESTIMATED, while disclaimers clearly state methodology.
    """
    engine = LocalGreenMetricsEngine()
    report = engine.build_report(total_runtime_ms=300.0)

    # Directly measured system hardware metrics
    assert "cpu_percent" in report.system_metrics
    assert "memory_mb" in report.system_metrics
    assert "peak_memory_mb" in report.system_metrics
    assert report.system_metrics["peak_memory_mb"] > 0

    # Estimated energy metrics
    assert report.energy_metrics.is_energy_measured is False
    assert report.energy_metrics.is_co2_measured is False
    assert report.energy_metrics.measurement_type == MeasurementType.STATISTICALLY_ESTIMATED

    # Disclaimer content check
    assert "NOT a universal environmental standard" in report.disclaimer
    assert "TDP" in report.energy_metrics.estimation_model
    assert GREEN_METRICS_DISCLAIMER == report.disclaimer


def test_repair_failure_and_amortization_safety():
    """When a repair fails validation, energy/repair metrics should be None."""
    engine = LocalGreenMetricsEngine()
    report = engine.build_report(
        total_runtime_ms=400.0,
        validated_repairs_count=0,
        repair_success=False,
    )
    assert report.energy_metrics.energy_per_validated_repair_j is None
    assert report.energy_metrics.energy_per_validated_repair_wh is None
    assert report.energy_metrics.latency_per_validated_repair_ms is None


def test_quality_and_security_tradeoff_preservation():
    """
    Ensures that security checks and validation rigor are never skipped or weakened.
    """
    engine = LocalGreenMetricsEngine()
    report = engine.build_report(
        total_runtime_ms=150.0,
        validation_stages_passed=4,
        repair_success=True,
    )
    tradeoff = report.tradeoff
    assert tradeoff.security_checks_retained is True
    assert tradeoff.validation_quality_maintained is True
    assert tradeoff.validation_stages_passed == 4
    assert "Validation was not weakened" in tradeoff.tradeoff_summary


def test_avoided_computation_bonuses():
    """Tests efficiency score boost from rule-first repairs and zero retries."""
    engine = LocalGreenMetricsEngine()

    # Heavy model escalation run with 2 retries
    heavy_model = ModelResourceMetrics(
        model_calls=3,
        retries_count=2,
        prompt_tokens=800,
        completion_tokens=250,
        total_tokens=1050,
    )
    rep_heavy = engine.build_report(
        total_runtime_ms=2500.0,
        model_metrics=heavy_model,
        rule_fixes_count=0,
        ai_fixes_count=3,
        retries_avoided=0,
    )

    # Lightweight deterministic rule-first run with zero retries
    light_model = ModelResourceMetrics(
        model_calls=0,
        retries_count=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    rep_light = engine.build_report(
        total_runtime_ms=300.0,
        model_metrics=light_model,
        rule_fixes_count=2,
        ai_fixes_count=0,
        retries_avoided=2,
    )

    assert rep_light.green_score > rep_heavy.green_score
    assert rep_light.score_breakdown["avoided_computation"] > rep_heavy.score_breakdown["avoided_computation"]
    assert any("Rule-first" in opt for opt in rep_light.efficiency_optimizations)
    assert any("Zero redundant retries" in opt for opt in rep_light.efficiency_optimizations)


def test_build_green_report_backwards_compatibility():
    """Ensures legacy build_green_report function works seamlessly."""
    metrics = {
        "total_runtime_ms": 250.0,
        "phase_ms": {
            "lexical": 20.0,
            "syntax_repair": 110.0,
            "semantic_phase": 80.0,
            "security_phase": 40.0,
        },
        "counters": {
            "rule_fixes": 1,
            "lex_fixes": 0,
            "ai_fixes": 0,
            "retries_count": 0,
            "retries_avoided": 1,
        },
        "values": {
            "parse_success": True,
        },
    }
    report = build_green_report(metrics)
    assert "green_score" in report
    assert "energy_metrics" in report
    assert "model_metrics" in report
    assert "tradeoff" in report
    assert "values" in report
    assert report["values"]["energy_joules"] > 0
    assert report["values"]["co2_grams"] > 0
    assert report["tradeoff"]["security_checks_retained"] is True


def test_flask_green_api_config():
    """Tests GET /api/green/config endpoint."""
    client = app.test_client()
    resp = client.get("/api/green/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "disclaimer" in data
    assert "baseline" in data
    assert "scoring_weights" in data
    assert "methodology" in data
    assert "linear_power_model" in data["methodology"]
    assert len(data["methodology"]["directly_measured"]) > 0
    assert len(data["methodology"]["statistically_estimated"]) > 0


def test_flask_green_api_measure():
    """Tests POST /api/green/measure endpoint."""
    client = app.test_client()
    payload = {
        "total_runtime_ms": 180.0,
        "phase_ms": {"syntax": 80.0, "security": 100.0},
        "rule_fixes_count": 1,
        "ai_fixes_count": 0,
        "repair_success": True,
    }
    resp = client.post("/api/green/measure", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "green_score" in data
    assert data["green_score"] >= 0.0
    assert "energy_metrics" in data
    assert data["energy_metrics"]["energy_joules"] > 0
    assert data["tradeoff"]["security_checks_retained"] is True


def test_flask_green_api_history(tmp_path):
    """Tests GET /api/green/history endpoint and logger."""
    client = app.test_client()
    resp = client.get("/api/green/history?limit=10")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "count" in data
    assert "records" in data
    assert isinstance(data["records"], list)
