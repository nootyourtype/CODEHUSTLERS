from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(frozen=True, order=True)
class Coordinate:
    x: int
    y: int

    def as_key(self) -> tuple[int, int]:
        return (self.x, self.y)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


class OrderState(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"


@dataclass
class Order:
    order_id: str
    created_at: datetime
    location: Coordinate
    prep_time_minutes: int
    priority: str
    sla_minutes: int
    state: OrderState = OrderState.PENDING
    assigned_agent_id: str | None = None
    assigned_at: datetime | None = None
    in_transit_at: datetime | None = None
    delivered_at: datetime | None = None
    expected_start_at: datetime | None = None
    expected_completion_at: datetime | None = None

    def delivery_minutes(self) -> float | None:
        if self.delivered_at is None:
            return None
        return (self.delivered_at - self.created_at).total_seconds() / 60.0


@dataclass
class Agent:
    agent_id: str
    current_location: Coordinate
    rating: float
    active_orders: list[str] = field(default_factory=list)
    cumulative_assignments: int = 0
    projected_location: Coordinate | None = None
    available_from: datetime | None = None

    def initialize_projection(self, start_time: datetime) -> None:
        self.projected_location = self.current_location
        self.available_from = start_time

    @property
    def availability(self) -> bool:
        return len(self.active_orders) < 2

    def to_summary(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "current_location": self.current_location.to_dict(),
            "rating": self.rating,
            "active_orders": list(self.active_orders),
            "cumulative_assignments": self.cumulative_assignments,
        }


@dataclass(frozen=True)
class GraphEdge:
    start: Coordinate
    end: Coordinate
    distance_minutes: float
    delay_multiplier: float

    @property
    def effective_minutes(self) -> float:
        return self.distance_minutes * self.delay_multiplier
