from __future__ import annotations

import heapq
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from smart_dispatch.config import DispatchConfig
from smart_dispatch.graph import TravelGraph
from smart_dispatch.metrics import SimulationMetrics
from smart_dispatch.models import Agent, Order, OrderState
from smart_dispatch.scoring import AssignmentScorer, CandidateScore

EVENT_COMPLETE = 0
EVENT_START = 1
EVENT_ARRIVAL = 2

PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


class DispatchSimulator:
    def __init__(
        self,
        orders: list[Order],
        agents: list[Agent],
        graph: TravelGraph,
        dataset_name: str,
        constraints: dict[str, float] | None = None,
        config: DispatchConfig | None = None,
        initial_warnings: list[str] | None = None,
    ) -> None:
        self.orders = {order.order_id: order for order in sorted(orders, key=lambda item: item.created_at)}
        self.agents = {agent.agent_id: agent for agent in agents}
        self.graph = graph
        self.constraints = constraints or {}
        self.config = config or DispatchConfig.from_constraints(self.constraints)
        self.dataset_name = dataset_name
        self.event_queue: list[tuple[datetime, int, str]] = []
        self.warnings: list[str] = list(initial_warnings or [])
        self.decision_latencies_ms: list[float] = []
        self.assignment_cycles = 0
        self.assignments_made = 0
        self.started_order_ids: set[str] = set()
        self.completed_order_ids: list[str] = []
        self.capacity_warning_orders: set[str] = set()
        self.unreachable_warning_orders: set[str] = set()
        self.sla_expired_warning_orders: set[str] = set()
        self.assignment_wait_warning_orders: set[str] = set()
        self.metrics = SimulationMetrics()
        self.scorer = AssignmentScorer(self.config, self.graph)
        self.start_time = min(
            (order.created_at for order in self.orders.values()),
            default=datetime(1970, 1, 1),
        )
        self.wall_clock_started_at = 0.0
        for agent in self.agents.values():
            agent.initialize_projection(self.start_time)
        for order in self.orders.values():
            self._push_event(order.created_at, EVENT_ARRIVAL, order.order_id)

    def run(self, generated_at_utc: datetime | None = None) -> dict[str, Any]:
        self.wall_clock_started_at = time.perf_counter()
        while self.event_queue:
            current_time, event_type, order_id = heapq.heappop(self.event_queue)
            order = self.orders[order_id]
            if event_type == EVENT_ARRIVAL:
                self._handle_arrival(current_time, order)
            elif event_type == EVENT_START:
                self._handle_start(current_time, order)
            elif event_type == EVENT_COMPLETE:
                self._handle_completion(current_time, order)
            else:
                raise ValueError(f"Unknown event type: {event_type}")
        if generated_at_utc is None:
            generated_at_utc = datetime.now(timezone.utc)
        return self._build_report(generated_at_utc)

    def _push_event(self, at: datetime, rank: int, order_id: str) -> None:
        heapq.heappush(self.event_queue, (at, rank, order_id))

    def _handle_arrival(self, current_time: datetime, order: Order) -> None:
        if order.state is not OrderState.PENDING:
            return
        self._attempt_pending_assignments(current_time)

    def _handle_start(self, current_time: datetime, order: Order) -> None:
        if order.state is OrderState.ASSIGNED and order.order_id not in self.started_order_ids:
            order.state = OrderState.IN_TRANSIT
            order.in_transit_at = current_time
            self.started_order_ids.add(order.order_id)

    def _handle_completion(self, current_time: datetime, order: Order) -> None:
        if order.state is OrderState.DELIVERED:
            return
        order.state = OrderState.DELIVERED
        order.delivered_at = current_time
        self.completed_order_ids.append(order.order_id)

        agent = self.agents[order.assigned_agent_id or ""]
        agent.current_location = order.location
        if order.order_id in agent.active_orders:
            agent.active_orders.remove(order.order_id)
        if not agent.active_orders:
            agent.available_from = current_time
            agent.projected_location = agent.current_location

        self.metrics.record_completion(order)
        delivery_minutes = order.delivery_minutes()
        if delivery_minutes is not None and delivery_minutes > order.sla_minutes:
            self.warnings.append(
                f"Order {order.order_id} breached SLA by {round(delivery_minutes - order.sla_minutes, 2)} minutes."
            )

        self._attempt_pending_assignments(current_time)

    def _attempt_pending_assignments(self, current_time: datetime) -> None:
        start = time.perf_counter()
        pending_orders = self._pending_orders(current_time)
        self.metrics.record_queue_depth(len(pending_orders))
        assignments_this_cycle = 0
        for order in pending_orders:
            candidate = self._select_best_candidate(current_time, order)
            if candidate is None:
                continue
            self._assign_order(current_time, order, self.agents[candidate.agent_id], candidate)
            assignments_this_cycle += 1

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.decision_latencies_ms.append(elapsed_ms)
        self.assignment_cycles += 1
        self.assignments_made += assignments_this_cycle
        target_ms = self.config.runtime.decision_latency_target_ms
        if elapsed_ms > target_ms:
            self.warnings.append(
                f"Assignment cycle at {current_time.isoformat()} exceeded target latency: {round(elapsed_ms, 2)} ms."
            )

    def _pending_orders(self, current_time: datetime) -> list[Order]:
        orders = [
            order
            for order in self.orders.values()
            if order.state is OrderState.PENDING and order.created_at <= current_time
        ]
        orders.sort(key=lambda item: (PRIORITY_RANK[item.priority], item.created_at, item.order_id))
        return orders

    def _select_best_candidate(self, current_time: datetime, order: Order) -> CandidateScore | None:
        best_candidate: CandidateScore | None = None
        any_reachable_agent = False
        any_capacity_available = False
        for agent in self.agents.values():
            if len(agent.active_orders) < self.config.runtime.max_active_orders_per_agent:
                any_capacity_available = True
            candidate = self.scorer.score_candidate(current_time, order, agent)
            if candidate is None:
                continue
            any_reachable_agent = True
            if best_candidate is None or candidate.rank_key() > best_candidate.rank_key():
                best_candidate = candidate
        if best_candidate is None and not any_capacity_available:
            if order.order_id not in self.capacity_warning_orders:
                self.warnings.append(
                    f"Order {order.order_id} remains pending at {current_time.isoformat()} because all agents are at capacity."
                )
                self.capacity_warning_orders.add(order.order_id)
        elif best_candidate is None and not any_reachable_agent:
            if order.order_id not in self.unreachable_warning_orders:
                self.warnings.append(
                    f"Order {order.order_id} remains pending at {current_time.isoformat()} because no reachable agent path exists."
                )
                self.unreachable_warning_orders.add(order.order_id)
        if best_candidate is None and order.created_at + timedelta(minutes=order.sla_minutes) <= current_time:
            if order.order_id not in self.sla_expired_warning_orders:
                self.warnings.append(
                    f"Order {order.order_id} already exceeded its SLA by arrival-to-now timing but remains eligible for assignment."
                )
                self.sla_expired_warning_orders.add(order.order_id)
        return best_candidate

    def _assign_order(self, current_time: datetime, order: Order, agent: Agent, candidate: CandidateScore) -> None:
        start_time = candidate.start_time
        completion_time = candidate.completion_time

        order.state = OrderState.ASSIGNED
        order.assigned_agent_id = agent.agent_id
        order.assigned_at = current_time
        order.expected_start_at = start_time
        order.expected_completion_at = completion_time

        agent.active_orders.append(order.order_id)
        agent.cumulative_assignments += 1
        agent.available_from = completion_time
        agent.projected_location = order.location

        self._push_event(start_time, EVENT_START, order.order_id)
        self._push_event(completion_time, EVENT_COMPLETE, order.order_id)
        wait_minutes = (current_time - order.created_at).total_seconds() / 60.0
        self.metrics.record_assignment_wait(wait_minutes)
        if wait_minutes >= self.config.runtime.queue_wait_warning_minutes and order.order_id not in self.assignment_wait_warning_orders:
            self.warnings.append(
                f"Order {order.order_id} waited {round(wait_minutes, 2)} minutes before assignment."
            )
            self.assignment_wait_warning_orders.add(order.order_id)

    def _build_report(self, generated_at_utc: datetime) -> dict[str, Any]:
        delivered_orders = [self.orders[order_id] for order_id in self.completed_order_ids]
        pending_orders = [order for order in self.orders.values() if order.state is not OrderState.DELIVERED]
        if delivered_orders:
            simulation_end = max(order.delivered_at for order in delivered_orders if order.delivered_at is not None)
        else:
            simulation_end = self.start_time
        simulated_minutes = max(1.0, (simulation_end - self.start_time).total_seconds() / 60.0)
        arrival_rate = len(self.orders) / simulated_minutes
        wall_clock_elapsed = max(0.001, time.perf_counter() - self.wall_clock_started_at)
        processing_throughput = len(delivered_orders) / wall_clock_elapsed * 60.0
        if processing_throughput < self.config.runtime.processing_throughput_target_orders_per_minute:
            self.warnings.append(
                "Runtime processing throughput fell below the target of "
                f"{self.config.runtime.processing_throughput_target_orders_per_minute} orders per minute."
            )

        assignment_counts = {agent.agent_id: agent.cumulative_assignments for agent in self.agents.values()}
        average_delivery = self.metrics.delivery_times.average()
        average_wait = self.metrics.assignment_waits.average()
        average_margin = self.metrics.sla_margins.average()
        high_priority_metrics = self.metrics.priority_metrics["high"]
        high_priority_on_time_rate = (
            round(
                ((high_priority_metrics.delivered - high_priority_metrics.sla_violations) / high_priority_metrics.delivered)
                * 100.0,
                2,
            )
            if high_priority_metrics.delivered
            else None
        )
        high_priority_average_margin = high_priority_metrics.sla_margins.average()

        report = {
            "metadata": self.metrics.build_metadata(self.dataset_name, generated_at_utc),
            "summary": {
                "orders_total": len(self.orders),
                "orders_delivered": len(delivered_orders),
                "orders_pending": len(pending_orders),
                "average_delivery_minutes": round(average_delivery, 2) if average_delivery is not None else None,
                "average_assignment_wait_minutes": round(average_wait, 2) if average_wait is not None else None,
                "average_sla_margin_minutes": round(average_margin, 2) if average_margin is not None else None,
                "sla_compliance_rate_percent": round(
                    ((len(delivered_orders) - self.metrics.sla_violations) / len(delivered_orders)) * 100.0,
                    2,
                )
                if delivered_orders
                else None,
                "sla_breach_rate_percent": round((self.metrics.sla_violations / len(delivered_orders)) * 100.0, 2)
                if delivered_orders
                else None,
                "high_priority_on_time_rate_percent": high_priority_on_time_rate,
                "high_priority_average_sla_margin_minutes": round(high_priority_average_margin, 2)
                if high_priority_average_margin is not None
                else None,
                "max_queue_depth": self.metrics.max_queue_depth,
                "assignment_cycles": self.assignment_cycles,
                "assignments_made": self.assignments_made,
                "average_decision_latency_ms": round(sum(self.decision_latencies_ms) / len(self.decision_latencies_ms), 3)
                if self.decision_latencies_ms
                else 0.0,
                "simulation_timespan_minutes": round(simulated_minutes, 2),
                "simulation_arrival_rate_orders_per_minute": round(arrival_rate, 2),
                "runtime_processing_throughput_orders_per_minute": round(processing_throughput, 2),
            },
            "fairness": self.metrics.build_fairness_summary(assignment_counts),
            "priority_breakdown": self.metrics.build_priority_breakdown(),
            "assumptions": [
                "Environment edges are treated as bidirectional travel links for routing.",
                "Each agent executes assigned orders sequentially and can queue up to two active orders.",
                "Order location is treated as the service destination because the dataset does not provide separate pickup and drop-off nodes.",
                "Estimated service time is travel time plus prep time.",
                "The stricter 500ms decision-latency target from the issue list is used for performance checks.",
            ],
            "warnings": self.warnings,
        }
        return report
