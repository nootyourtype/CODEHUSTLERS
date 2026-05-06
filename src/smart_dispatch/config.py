from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    priority_scale: float = 20.0
    delivery_time_penalty_scale: float = 1.0
    sla_margin_scale: float = 0.7
    sla_margin_cap: float = 25.0
    sla_breach_penalty_scale: float = 2.5
    fairness_bonus_cap: float = 12.0
    fairness_penalty_per_assignment: float = 2.0
    active_order_penalty_scale: float = 4.0
    rating_bonus_scale: float = 3.0


@dataclass(frozen=True)
class RuntimeConfig:
    max_active_orders_per_agent: int = 2
    decision_latency_target_ms: float = 500.0
    processing_throughput_target_orders_per_minute: float = 100.0
    queue_wait_warning_minutes: float = 15.0
    default_sla_minutes: float = 50.0


@dataclass(frozen=True)
class DispatchConfig:
    runtime: RuntimeConfig
    scoring: ScoringConfig
    priority_weights: dict[str, float]

    @classmethod
    def from_constraints(cls, constraints: dict[str, float]) -> "DispatchConfig":
        runtime = RuntimeConfig(
            max_active_orders_per_agent=int(constraints.get("max_active_orders_per_agent", 2)),
            # The issue list sets a stricter 500ms evaluation target than the CSV.
            decision_latency_target_ms=min(
                500.0,
                float(constraints.get("decision_latency_target_seconds", 0.5)) * 1000.0,
            ),
            default_sla_minutes=float(constraints.get("default_sla_minutes", 50.0)),
        )
        scoring = ScoringConfig()
        priority_weights = {
            "high": float(constraints.get("priority_weight_high", 1.5)),
            "normal": float(constraints.get("priority_weight_normal", 1.0)),
            "low": float(constraints.get("priority_weight_low", 0.8)),
        }
        return cls(runtime=runtime, scoring=scoring, priority_weights=priority_weights)
