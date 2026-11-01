from __future__ import annotations

from typing import Dict, Any
from compiler.green_engine import (
    LocalGreenMetricsEngine,
    ModelResourceMetrics,
    GREEN_METRICS_DISCLAIMER,
)


def build_green_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
    phase_ms = metrics.get("phase_ms", {})
    counters = metrics.get("counters", {})
    values = metrics.get("values", {})

    total_ms = metrics.get("total_runtime_ms", 0.0)

    # Use LocalGreenMetricsEngine for multi-dimensional cost and normalized scoring
    engine = LocalGreenMetricsEngine()

    model_metrics = ModelResourceMetrics(
        model_calls=counters.get("ai_fixes", 0),
        retries_count=counters.get("retries_count", 0),
        prompt_tokens=counters.get("prompt_tokens", 0),
        completion_tokens=counters.get("completion_tokens", 0),
        total_tokens=counters.get("total_tokens", 0),
        inference_latency_ms=phase_ms.get("model_inference", 0.0),
    )

    is_parse_ok = bool(values.get("parse_success", True))
    engine_report = engine.build_report(
        total_runtime_ms=total_ms,
        stage_ms=phase_ms,
        model_metrics=model_metrics,
        validated_repairs_count=1 if is_parse_ok else 0,
        repair_success=is_parse_ok,
        validation_stages_passed=4 if is_parse_ok else 2,
        rule_fixes_count=counters.get("rule_fixes", 0) + counters.get("lex_fixes", 0),
        ai_fixes_count=counters.get("ai_fixes", 0),
        retries_avoided=counters.get("retries_avoided", 0),
    )

    # Hotspot analysis
    hotspot = engine_report.hotspot
    suggestion = engine_report.recommendations[0] if engine_report.recommendations else "Pipeline executed efficiently."

    # Enrich values dictionary
    merged_values = dict(values)
    merged_values["co2_kg"] = engine_report.energy_metrics.co2_kg
    merged_values["co2_grams"] = engine_report.energy_metrics.co2_grams
    merged_values["energy_joules"] = engine_report.energy_metrics.energy_joules
    merged_values["energy_wh"] = engine_report.energy_metrics.energy_wh
    merged_values["cpu_percent"] = engine_report.system_metrics.get("cpu_percent")
    merged_values["memory_mb"] = engine_report.system_metrics.get("memory_mb")
    merged_values["peak_memory_mb"] = engine_report.system_metrics.get("peak_memory_mb")

    report = {
        "total_runtime_ms": round(total_ms, 2),
        "phase_ms": {k: round(v, 2) for k, v in phase_ms.items()},
        "counters": dict(counters),
        "values": merged_values,
        "green_score": round(engine_report.green_score, 1),
        "hotspot": hotspot,
        "suggestion": suggestion,
        "energy_metrics": engine_report.energy_metrics.to_dict(),
        "model_metrics": engine_report.model_metrics.to_dict(),
        "system_metrics": dict(engine_report.system_metrics),
        "tradeoff": engine_report.tradeoff.to_dict(),
        "efficiency_optimizations": list(engine_report.efficiency_optimizations),
        "recommendations": list(engine_report.recommendations),
        "score_breakdown": {k: round(v, 1) for k, v in engine_report.score_breakdown.items()},
        "disclaimer": GREEN_METRICS_DISCLAIMER,
    }

    return report