from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_dispatch.loaders import load_input_bundle
from smart_dispatch.simulator import DispatchSimulator


def render_summary(report: dict[str, object]) -> str:
    summary = report["summary"]
    metadata = report["metadata"]
    fairness = report["fairness"]
    lines = [
        "Smart Delivery Dispatch MVP",
        f"Dataset: {metadata['dataset']}",
        f"Generated at (UTC): {metadata['generated_at_utc']}",
        f"Orders delivered: {summary['orders_delivered']} / {summary['orders_total']}",
        f"Average delivery time (minutes): {summary['average_delivery_minutes']}",
        f"SLA compliance rate: {summary['sla_compliance_rate_percent']}%",
        f"SLA breach rate: {summary['sla_breach_rate_percent']}%",
        f"High-priority on-time rate: {summary['high_priority_on_time_rate_percent']}%",
        f"High-priority average SLA margin (minutes): {summary['high_priority_average_sla_margin_minutes']}",
        f"Assignments made: {summary['assignments_made']}",
        f"Fairness assignment range: {fairness['assignment_range']}",
        f"Fairness load std dev: {fairness['load_std_dev']}",
        f"Average decision latency (ms): {summary['average_decision_latency_ms']}",
        f"Runtime processing throughput (engine orders/minute): {summary['runtime_processing_throughput_orders_per_minute']}",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Smart Delivery Dispatch MVP.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data" / "raw",
        help="Directory containing orders.csv, agents.csv, constraints.csv, and environment_edges.csv.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "metrics.json",
        help="Path where the JSON metrics report will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_input_bundle(args.data_dir)
    simulator = DispatchSimulator(
        orders=bundle.orders,
        agents=bundle.agents,
        graph=bundle.graph,
        constraints=bundle.constraints,
        dataset_name=args.data_dir.name,
        initial_warnings=bundle.warnings,
    )
    report = simulator.run(generated_at_utc=datetime.now(timezone.utc).replace(tzinfo=None))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary_path = args.output.with_name("summary.txt")
    summary_path.write_text(render_summary(report) + "\n", encoding="utf-8")

    print(render_summary(report))
    print(f"Metrics written to: {args.output}")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
