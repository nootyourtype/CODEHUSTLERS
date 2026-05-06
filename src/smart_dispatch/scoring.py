from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from smart_dispatch.config import DispatchConfig
from smart_dispatch.graph import TravelGraph
from smart_dispatch.models import Agent, Order


@dataclass(frozen=True)
class CandidateScore:
    agent_id: str
    score: float
    travel_minutes: float
    delivery_minutes: float
    remaining_sla_minutes: float
    start_time: datetime
    completion_time: datetime
    fairness_bonus: float
    load_penalty: float
    priority_bonus: float
    sla_margin_bonus: float
    sla_breach_penalty: float
    rating_bonus: float

    def rank_key(self) -> tuple[float, float, float, float, float]:
        return (
            self.score,
            self.remaining_sla_minutes,
            -self.travel_minutes,
            -self.load_penalty,
            self.rating_bonus,
        )


class AssignmentScorer:
    def __init__(self, config: DispatchConfig, graph: TravelGraph) -> None:
        self.config = config
        self.graph = graph

    def score_candidate(self, current_time: datetime, order: Order, agent: Agent) -> CandidateScore | None:
        if len(agent.active_orders) >= self.config.runtime.max_active_orders_per_agent:
            return None

        projected_location = agent.projected_location or agent.current_location
        travel_minutes = self.graph.travel_minutes(projected_location, order.location)
        if math.isinf(travel_minutes):
            return None

        start_time = max(current_time, agent.available_from or current_time)
        completion_time = start_time + timedelta(minutes=travel_minutes + order.prep_time_minutes)
        delivery_minutes = (completion_time - order.created_at).total_seconds() / 60.0
        remaining_sla_minutes = order.sla_minutes - delivery_minutes

        scoring = self.config.scoring
        priority_bonus = self.config.priority_weights[order.priority] * scoring.priority_scale
        sla_margin_bonus = max(
            -scoring.sla_margin_cap,
            min(scoring.sla_margin_cap, remaining_sla_minutes * scoring.sla_margin_scale),
        )
        sla_breach_penalty = max(0.0, -remaining_sla_minutes) * scoring.sla_breach_penalty_scale
        fairness_bonus = max(
            0.0,
            scoring.fairness_bonus_cap - (agent.cumulative_assignments * scoring.fairness_penalty_per_assignment),
        )
        load_penalty = len(agent.active_orders) * scoring.active_order_penalty_scale
        rating_bonus = agent.rating * scoring.rating_bonus_scale
        time_penalty = delivery_minutes * scoring.delivery_time_penalty_scale

        total_score = (
            priority_bonus
            + sla_margin_bonus
            + fairness_bonus
            + rating_bonus
            - load_penalty
            - time_penalty
            - sla_breach_penalty
        )
        return CandidateScore(
            agent_id=agent.agent_id,
            score=total_score,
            travel_minutes=travel_minutes,
            delivery_minutes=delivery_minutes,
            remaining_sla_minutes=remaining_sla_minutes,
            start_time=start_time,
            completion_time=completion_time,
            fairness_bonus=fairness_bonus,
            load_penalty=load_penalty,
            priority_bonus=priority_bonus,
            sla_margin_bonus=sla_margin_bonus,
            sla_breach_penalty=sla_breach_penalty,
            rating_bonus=rating_bonus,
        )
