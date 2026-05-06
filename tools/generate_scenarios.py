from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SCENARIO_ROOT = ROOT / "data" / "scenarios"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_raw_inputs() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    orders = read_csv(RAW_DIR / "orders.csv")
    agents = read_csv(RAW_DIR / "agents.csv")
    constraints = read_csv(RAW_DIR / "constraints.csv")
    edges = read_csv(RAW_DIR / "environment_edges.csv")
    return orders, agents, constraints, edges


def compress_timestamps(orders: list[dict[str, str]], start: datetime, interval_minutes: int) -> list[dict[str, str]]:
    updated: list[dict[str, str]] = []
    current = start
    for row in orders:
        cloned = deepcopy(row)
        cloned["timestamp"] = current.strftime("%Y-%m-%d %H:%M:%S")
        updated.append(cloned)
        current += timedelta(minutes=interval_minutes)
    return updated


def write_scenario(
    name: str,
    orders: list[dict[str, str]],
    agents: list[dict[str, str]],
    constraints: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> None:
    scenario_dir = SCENARIO_ROOT / name
    write_csv(scenario_dir / "orders.csv", orders, list(orders[0].keys()))
    write_csv(scenario_dir / "agents.csv", agents, list(agents[0].keys()))
    write_csv(scenario_dir / "constraints.csv", constraints, list(constraints[0].keys()))
    write_csv(scenario_dir / "environment_edges.csv", edges, list(edges[0].keys()))


def scenario_burst_high_priority(
    orders: list[dict[str, str]],
    agents: list[dict[str, str]],
    constraints: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> None:
    selected_orders = deepcopy(orders[:45])
    selected_orders = compress_timestamps(
        selected_orders,
        start=datetime.fromisoformat("2026-05-03 18:00:00"),
        interval_minutes=0,
    )
    for index, row in enumerate(selected_orders):
        row["priority"] = "high" if index < 30 else "normal"
        row["sla_minutes"] = "28" if index < 30 else "35"
        row["prep_time_minutes"] = str(min(18, int(row["prep_time_minutes"]) + 2))
    limited_agents = deepcopy(agents[:12])

    tuned_constraints = deepcopy(constraints)
    for row in tuned_constraints:
        if row["constraint"] == "max_active_orders_per_agent":
            row["value"] = "2"
        elif row["constraint"] == "priority_weight_high":
            row["value"] = "1.8"
    write_scenario("burst_high_priority", selected_orders, limited_agents, tuned_constraints, deepcopy(edges))


def scenario_limited_agents_tight_sla(
    orders: list[dict[str, str]],
    agents: list[dict[str, str]],
    constraints: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> None:
    selected_orders = deepcopy(orders[:60])
    selected_orders = compress_timestamps(
        selected_orders,
        start=datetime.fromisoformat("2026-05-03 19:00:00"),
        interval_minutes=1,
    )
    for row in selected_orders:
        row["sla_minutes"] = str(max(18, int(row["sla_minutes"]) - 18))
        row["prep_time_minutes"] = str(min(20, int(row["prep_time_minutes"]) + 3))
    limited_agents = deepcopy(agents[:6])

    tuned_constraints = deepcopy(constraints)
    for row in tuned_constraints:
        if row["constraint"] == "max_active_orders_per_agent":
            row["value"] = "1"
        elif row["constraint"] == "default_sla_minutes":
            row["value"] = "30"
    write_scenario("limited_agents_tight_sla", selected_orders, limited_agents, tuned_constraints, deepcopy(edges))


def scenario_partial_disconnect(
    orders: list[dict[str, str]],
    agents: list[dict[str, str]],
    constraints: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> None:
    selected_orders = deepcopy(orders[:50])
    selected_orders = compress_timestamps(
        selected_orders,
        start=datetime.fromisoformat("2026-05-03 20:00:00"),
        interval_minutes=2,
    )
    for index, row in enumerate(selected_orders[:10], start=1):
        row["order_id"] = f"PD{index:03d}"
        row["location_x"] = "9"
        row["location_y"] = "9"
        row["priority"] = "high"
        row["sla_minutes"] = "22"

    filtered_edges = [
        deepcopy(row)
        for row in edges
        if {row["from_x"], row["to_x"]} != {"7", "8"}
    ]
    staged_agents = [deepcopy(row) for row in agents if int(row["current_x"]) <= 7][:8]
    write_scenario("partial_disconnect", selected_orders, staged_agents, deepcopy(constraints), filtered_edges)


def scenario_noisy_input_resilience(
    orders: list[dict[str, str]],
    agents: list[dict[str, str]],
    constraints: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> None:
    selected_orders = deepcopy(orders[:30])
    selected_orders = compress_timestamps(
        selected_orders,
        start=datetime.fromisoformat("2026-05-03 21:00:00"),
        interval_minutes=1,
    )
    selected_orders.append(
        {
            "order_id": "BROKEN_ORDER",
            "timestamp": "not-a-date",
            "location_x": "x",
            "location_y": "1",
            "prep_time_minutes": "-4",
            "priority": "urgent",
            "sla_minutes": "0",
        }
    )
    selected_orders.append(
        {
            "order_id": "OFF_GRID",
            "timestamp": "2026-05-03 21:31:00",
            "location_x": "99",
            "location_y": "99",
            "prep_time_minutes": "8",
            "priority": "high",
            "sla_minutes": "25",
        }
    )

    noisy_agents = deepcopy(agents[:10])
    noisy_agents.append(
        {
            "agent_id": "BAD_AGENT",
            "current_x": "hello",
            "current_y": "0",
            "rating": "9.9",
        }
    )
    noisy_agents.append(
        {
            "agent_id": "OFF_GRID_AGENT",
            "current_x": "40",
            "current_y": "40",
            "rating": "4.7",
        }
    )

    noisy_constraints = deepcopy(constraints)
    noisy_constraints.append({"constraint": "priority_weight_high", "value": ""})
    noisy_edges = deepcopy(edges[:80])
    noisy_edges.append(
        {
            "from_x": "bad",
            "from_y": "0",
            "to_x": "1",
            "to_y": "0",
            "distance_minutes": "3",
            "delay_multiplier": "1.0",
        }
    )

    write_scenario("noisy_input_resilience", selected_orders, noisy_agents, noisy_constraints, noisy_edges)


def main() -> None:
    orders, agents, constraints, edges = load_raw_inputs()
    SCENARIO_ROOT.mkdir(parents=True, exist_ok=True)
    scenario_burst_high_priority(orders, agents, constraints, edges)
    scenario_limited_agents_tight_sla(orders, agents, constraints, edges)
    scenario_partial_disconnect(orders, agents, constraints, edges)
    scenario_noisy_input_resilience(orders, agents, constraints, edges)
    print(f"Generated scenarios in {SCENARIO_ROOT}")


if __name__ == "__main__":
    main()
