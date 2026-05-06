from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from smart_dispatch.graph import TravelGraph
from smart_dispatch.models import Agent, Coordinate, GraphEdge, Order

VALID_PRIORITIES = {"high", "normal", "low"}
REQUIRED_FILES = (
    "orders.csv",
    "agents.csv",
    "constraints.csv",
    "environment_edges.csv",
)


@dataclass(frozen=True)
class InputBundle:
    orders: list[Order]
    agents: list[Agent]
    graph: TravelGraph
    constraints: dict[str, float]
    warnings: list[str]


def load_input_bundle(data_dir: Path) -> InputBundle:
    missing = [name for name in REQUIRED_FILES if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files in {data_dir}: {', '.join(missing)}")

    warnings: list[str] = []
    edges = load_graph_edges(data_dir / "environment_edges.csv", warnings)
    graph = TravelGraph(edges)
    agents = load_agents(data_dir / "agents.csv", warnings)
    orders = load_orders(data_dir / "orders.csv", warnings)
    constraints = load_constraints(data_dir / "constraints.csv", warnings)
    agents, orders = validate_location_references(graph, agents, orders, warnings)
    if not edges:
        raise ValueError("No valid environment edges were loaded.")
    if not agents:
        raise ValueError("No valid agents were loaded after validation.")
    return InputBundle(orders=orders, agents=agents, graph=graph, constraints=constraints, warnings=warnings)


def load_orders(path: Path, warnings: list[str]) -> list[Order]:
    orders: list[Order] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {
            "order_id",
            "timestamp",
            "location_x",
            "location_y",
            "prep_time_minutes",
            "priority",
            "sla_minutes",
        }
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"Unexpected orders.csv headers: {reader.fieldnames}")
        for index, row in enumerate(reader, start=2):
            try:
                order_id = require_text(row, "order_id")
                created_at = datetime.fromisoformat(require_text(row, "timestamp"))
                location = Coordinate(
                    x=require_int(row, "location_x"),
                    y=require_int(row, "location_y"),
                )
                prep_time_minutes = require_int(row, "prep_time_minutes", minimum=0)
                priority = require_text(row, "priority").lower()
                if priority not in VALID_PRIORITIES:
                    raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
                sla_minutes = require_int(row, "sla_minutes", minimum=1)
            except Exception as exc:
                warnings.append(
                    f"Skipped invalid order row {index} ({row.get('order_id', '<unknown>')}): {exc}"
                )
                continue
            orders.append(
                Order(
                    order_id=order_id,
                    created_at=created_at,
                    location=location,
                    prep_time_minutes=prep_time_minutes,
                    priority=priority,
                    sla_minutes=sla_minutes,
                )
            )
    return orders


def load_agents(path: Path, warnings: list[str]) -> list[Agent]:
    agents: list[Agent] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"agent_id", "current_x", "current_y", "rating"}
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"Unexpected agents.csv headers: {reader.fieldnames}")
        for index, row in enumerate(reader, start=2):
            try:
                agent_id = require_text(row, "agent_id")
                location = Coordinate(
                    x=require_int(row, "current_x"),
                    y=require_int(row, "current_y"),
                )
                rating = require_float(row, "rating", minimum=0.0, maximum=5.0)
            except Exception as exc:
                warnings.append(
                    f"Skipped invalid agent row {index} ({row.get('agent_id', '<unknown>')}): {exc}"
                )
                continue
            agents.append(Agent(agent_id=agent_id, current_location=location, rating=rating))
    return agents


def load_graph_edges(path: Path, warnings: list[str]) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {
            "from_x",
            "from_y",
            "to_x",
            "to_y",
            "distance_minutes",
            "delay_multiplier",
        }
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"Unexpected environment_edges.csv headers: {reader.fieldnames}")
        for index, row in enumerate(reader, start=2):
            try:
                start = Coordinate(require_int(row, "from_x"), require_int(row, "from_y"))
                end = Coordinate(require_int(row, "to_x"), require_int(row, "to_y"))
                distance_minutes = require_float(row, "distance_minutes", minimum=0.0)
                delay_multiplier = require_float(row, "delay_multiplier", minimum=0.1)
            except Exception as exc:
                coords = f"({row.get('from_x')},{row.get('from_y')}) -> ({row.get('to_x')},{row.get('to_y')})"
                warnings.append(f"Skipped invalid graph edge row {index} {coords}: {exc}")
                continue
            edges.append(
                GraphEdge(
                    start=start,
                    end=end,
                    distance_minutes=distance_minutes,
                    delay_multiplier=delay_multiplier,
                )
            )
    return edges


def load_constraints(path: Path, warnings: list[str]) -> dict[str, float]:
    constraints: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"constraint", "value"}
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"Unexpected constraints.csv headers: {reader.fieldnames}")
        for index, row in enumerate(reader, start=2):
            try:
                name = require_text(row, "constraint")
                value = require_float(row, "value", minimum=0.0)
            except Exception as exc:
                warnings.append(
                    f"Skipped invalid constraint row {index} ({row.get('constraint', '<unknown>')}): {exc}"
                )
                continue
            constraints[name] = value
    return constraints


def validate_location_references(
    graph: TravelGraph,
    agents: list[Agent],
    orders: list[Order],
    warnings: list[str],
) -> tuple[list[Agent], list[Order]]:
    valid_agents: list[Agent] = []
    valid_orders: list[Order] = []

    for agent in agents:
        if not graph.has_node(agent.current_location):
            warnings.append(f"Skipped agent {agent.agent_id}: unknown graph node {agent.current_location.as_key()}.")
            continue
        valid_agents.append(agent)

    for order in orders:
        if not graph.has_node(order.location):
            warnings.append(f"Skipped order {order.order_id}: unknown graph node {order.location.as_key()}.")
            continue
        valid_orders.append(order)

    return valid_agents, valid_orders


def require_text(row: dict[str, str], field: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def require_int(row: dict[str, str], field: str, minimum: int | None = None) -> int:
    value = int(require_text(row, field))
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value


def require_float(
    row: dict[str, str],
    field: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = float(require_text(row, field))
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{field} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return value
