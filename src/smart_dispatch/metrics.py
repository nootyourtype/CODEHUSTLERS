from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from smart_dispatch.models import Order


class RunningStats:
    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        if self.minimum is None or value < self.minimum:
            self.minimum = value
        if self.maximum is None or value > self.maximum:
            self.maximum = value

    def average(self) -> float | None:
        if self.count == 0:
            return None
        return self.mean

    def variance(self) -> float | None:
        if self.count == 0:
            return None
        return self.m2 / self.count

    def std_dev(self) -> float | None:
        variance = self.variance()
        if variance is None:
            return None
        return math.sqrt(variance)


@dataclass
class PriorityMetrics:
    delivered: int = 0
    sla_violations: int = 0
    delivery_times: RunningStats = field(default_factory=RunningStats)
    sla_margins: RunningStats = field(default_factory=RunningStats)


class SimulationMetrics:
    def __init__(self) -> None:
        self.delivery_times = RunningStats()
        self.sla_margins = RunningStats()
        self.assignment_waits = RunningStats()
        self.priority_metrics = {
            "high": PriorityMetrics(),
            "normal": PriorityMetrics(),
            "low": PriorityMetrics(),
        }
        self.max_queue_depth = 0
        self.sla_violations = 0

    def record_queue_depth(self, queue_depth: int) -> None:
        self.max_queue_depth = max(self.max_queue_depth, queue_depth)

    def record_assignment_wait(self, wait_minutes: float) -> None:
        self.assignment_waits.add(wait_minutes)

    def record_completion(self, order: Order) -> None:
        delivery_minutes = order.delivery_minutes()
        if delivery_minutes is None:
            return
        sla_margin = order.sla_minutes - delivery_minutes
        priority_metrics = self.priority_metrics[order.priority]

        self.delivery_times.add(delivery_minutes)
        self.sla_margins.add(sla_margin)
        priority_metrics.delivery_times.add(delivery_minutes)
        priority_metrics.sla_margins.add(sla_margin)
        priority_metrics.delivered += 1
        if delivery_minutes > order.sla_minutes:
            self.sla_violations += 1
            priority_metrics.sla_violations += 1

    def build_fairness_summary(self, assignment_counts: dict[str, int]) -> dict[str, Any]:
        fairness_values = list(assignment_counts.values())
        if fairness_values:
            min_assignments = min(fairness_values)
            max_assignments = max(fairness_values)
            assignment_range = max_assignments - min_assignments
            mean_assignments = sum(fairness_values) / len(fairness_values)
            load_variance = statistics.pvariance(fairness_values) if len(fairness_values) > 1 else 0.0
            load_std_dev = statistics.pstdev(fairness_values) if len(fairness_values) > 1 else 0.0
        else:
            min_assignments = 0
            max_assignments = 0
            assignment_range = 0
            mean_assignments = 0.0
            load_variance = 0.0
            load_std_dev = 0.0
        return {
            "assignment_counts": assignment_counts,
            "min_assignments": min_assignments,
            "max_assignments": max_assignments,
            "mean_assignments": round(mean_assignments, 2),
            "assignment_range": assignment_range,
            "load_variance": round(load_variance, 4),
            "load_std_dev": round(load_std_dev, 4),
        }

    def build_priority_breakdown(self) -> dict[str, dict[str, Any]]:
        breakdown: dict[str, dict[str, Any]] = {}
        for priority, metrics in self.priority_metrics.items():
            average_delivery = metrics.delivery_times.average()
            average_margin = metrics.sla_margins.average()
            breakdown[priority] = {
                "delivered": metrics.delivered,
                "average_delivery_minutes": round(average_delivery, 2) if average_delivery is not None else None,
                "sla_breach_rate_percent": round((metrics.sla_violations / metrics.delivered) * 100.0, 2)
                if metrics.delivered
                else None,
                "average_sla_margin_minutes": round(average_margin, 2) if average_margin is not None else None,
            }
        return breakdown

    def build_metadata(self, dataset_name: str, generated_at_utc: datetime) -> dict[str, Any]:
        if generated_at_utc.tzinfo is not None:
            generated_at_utc = generated_at_utc.astimezone(timezone.utc).replace(tzinfo=None)
        return {
            "dataset": dataset_name,
            "generated_at_utc": generated_at_utc.isoformat(timespec="seconds") + "Z",
        }
