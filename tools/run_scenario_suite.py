from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_dispatch.loaders import load_input_bundle
from smart_dispatch.simulator import DispatchSimulator


def run_scenario(data_dir: Path) -> dict[str, object]:
    bundle = load_input_bundle(data_dir)
    simulator = DispatchSimulator(
        orders=bundle.orders,
        agents=bundle.agents,
        graph=bundle.graph,
        constraints=bundle.constraints,
        dataset_name=data_dir.name,
        initial_warnings=bundle.warnings,
    )
    report = simulator.run(generated_at_utc=datetime.now(timezone.utc))
    summary = report["summary"]
    return {
        "scenario": data_dir.name,
        "orders_delivered": summary["orders_delivered"],
        "orders_total": summary["orders_total"],
        "orders_pending": summary["orders_pending"],
        "average_delivery_minutes": summary["average_delivery_minutes"],
        "sla_compliance_rate_percent": summary["sla_compliance_rate_percent"],
        "high_priority_on_time_rate_percent": summary["high_priority_on_time_rate_percent"],
        "max_queue_depth": summary["max_queue_depth"],
        "assignment_range": report["fairness"]["assignment_range"],
        "warning_count": len(report["warnings"]),
    }


def main() -> int:
    scenario_root = ROOT / "data" / "scenarios"
    scenario_dirs = sorted(path for path in scenario_root.iterdir() if path.is_dir())
    if not scenario_dirs:
        raise FileNotFoundError(f"No scenario directories found in {scenario_root}")

    results = [run_scenario(path) for path in scenario_dirs]
    output_dir = ROOT / "output" / "scenario_suite"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "scenario_results.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    lines = ["Scenario Suite Results", ""]
    for result in results:
        lines.extend(
            [
                f"Scenario: {result['scenario']}",
                f"Delivered: {result['orders_delivered']} / {result['orders_total']}",
                f"Pending: {result['orders_pending']}",
                f"Average delivery minutes: {result['average_delivery_minutes']}",
                f"SLA compliance rate: {result['sla_compliance_rate_percent']}%",
                f"High-priority on-time rate: {result['high_priority_on_time_rate_percent']}%",
                f"Max queue depth: {result['max_queue_depth']}",
                f"Assignment range: {result['assignment_range']}",
                f"Warnings: {result['warning_count']}",
                "",
            ]
        )
    summary_path = output_dir / "scenario_results.txt"
    summary_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(summary_path.read_text(encoding="utf-8"))
    print(f"JSON written to: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
