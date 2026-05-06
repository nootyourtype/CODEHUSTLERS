from __future__ import annotations

import textwrap
import unittest
from datetime import datetime
from pathlib import Path
import sys
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_dispatch.config import DispatchConfig
from smart_dispatch.graph import TravelGraph
from smart_dispatch.loaders import load_input_bundle
from smart_dispatch.models import Agent, Coordinate, GraphEdge, Order
from smart_dispatch.scoring import AssignmentScorer
from smart_dispatch.simulator import DispatchSimulator


class LoaderTests(unittest.TestCase):
    def test_missing_required_files_raise_clear_error(self) -> None:
        temp_dir = self._make_temp_dir()
        with self.assertRaises(FileNotFoundError) as context:
            load_input_bundle(temp_dir)
        self.assertIn("Missing required input files", str(context.exception))

    def test_invalid_priority_row_is_skipped_and_valid_rows_continue(self) -> None:
        data_dir = self._make_temp_dir()
        self._write_file(
            data_dir / "orders.csv",
            """
            order_id,timestamp,location_x,location_y,prep_time_minutes,priority,sla_minutes
            O001,2026-05-03 09:00:00,0,0,5,urgent,30
            O002,2026-05-03 09:05:00,1,0,5,high,30
            """,
        )
        self._write_file(
            data_dir / "agents.csv",
            """
            agent_id,current_x,current_y,rating
            A001,0,0,4.9
            """,
        )
        self._write_file(
            data_dir / "constraints.csv",
            """
            constraint,value
            max_active_orders_per_agent,2
            """,
        )
        self._write_file(
            data_dir / "environment_edges.csv",
            """
            from_x,from_y,to_x,to_y,distance_minutes,delay_multiplier
            0,0,1,0,3,1.0
            """,
        )
        bundle = load_input_bundle(data_dir)
        self.assertEqual(len(bundle.orders), 1)
        self.assertEqual(bundle.orders[0].order_id, "O002")
        self.assertTrue(any("Skipped invalid order row" in warning for warning in bundle.warnings))

    @staticmethod
    def _write_file(path: Path, content: str) -> None:
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")

    def _make_temp_dir(self) -> Path:
        base_dir = ROOT / ".test_tmp"
        base_dir.mkdir(exist_ok=True)
        temp_dir = base_dir / uuid.uuid4().hex
        temp_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir


class GraphTests(unittest.TestCase):
    def test_graph_is_bidirectional_for_travel_queries(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(
                    start=Coordinate(0, 0),
                    end=Coordinate(1, 0),
                    distance_minutes=3,
                    delay_multiplier=1.0,
                )
            ]
        )
        self.assertEqual(graph.travel_minutes(Coordinate(1, 0), Coordinate(0, 0)), 3.0)


class SimulatorTests(unittest.TestCase):
    def test_high_priority_order_gets_capacity_first(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(Coordinate(0, 0), Coordinate(1, 0), 1, 1.0),
                GraphEdge(Coordinate(1, 0), Coordinate(2, 0), 1, 1.0),
            ]
        )
        orders = [
            Order("O_LOW", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(1, 0), 2, "low", 30),
            Order("O_HIGH", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(2, 0), 2, "high", 30),
        ]
        agents = [Agent("A001", Coordinate(0, 0), 4.5)]
        simulator = DispatchSimulator(
            orders=orders,
            agents=agents,
            graph=graph,
            config=DispatchConfig.from_constraints({"max_active_orders_per_agent": 1}),
            dataset_name="unit",
        )

        report = simulator.run()

        self.assertEqual(report["summary"]["orders_delivered"], 2)
        self.assertEqual(simulator.orders["O_HIGH"].assigned_at, datetime.fromisoformat("2026-05-03 09:00:00"))
        self.assertGreater(simulator.orders["O_LOW"].assigned_at, simulator.orders["O_HIGH"].assigned_at)

    def test_disconnected_order_stays_pending_with_warning(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(Coordinate(0, 0), Coordinate(1, 0), 1, 1.0),
            ]
        )
        orders = [
            Order("O_BLOCKED", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(1, 0), 2, "high", 30),
            Order("O_UNKNOWN", datetime.fromisoformat("2026-05-03 09:01:00"), Coordinate(2, 0), 2, "normal", 30),
        ]
        agents = [Agent("A001", Coordinate(0, 0), 4.5)]
        simulator = DispatchSimulator(
            orders=orders,
            agents=agents,
            graph=graph,
            config=DispatchConfig.from_constraints({"max_active_orders_per_agent": 1}),
            dataset_name="unit-disconnected",
        )

        report = simulator.run()

        self.assertEqual(report["summary"]["orders_delivered"], 1)
        self.assertEqual(report["summary"]["orders_pending"], 1)
        self.assertIn("no reachable agent path exists", " ".join(report["warnings"]))

    def test_overloaded_queue_records_wait_and_capacity_warning(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(Coordinate(0, 0), Coordinate(1, 0), 5, 1.0),
            ]
        )
        orders = [
            Order("O1", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(1, 0), 20, "high", 60),
            Order("O2", datetime.fromisoformat("2026-05-03 09:01:00"), Coordinate(1, 0), 20, "normal", 60),
            Order("O3", datetime.fromisoformat("2026-05-03 09:02:00"), Coordinate(1, 0), 20, "low", 60),
        ]
        agents = [Agent("A001", Coordinate(0, 0), 4.8)]
        simulator = DispatchSimulator(
            orders=orders,
            agents=agents,
            graph=graph,
            config=DispatchConfig.from_constraints({"max_active_orders_per_agent": 1}),
            dataset_name="unit-overload",
        )

        report = simulator.run()

        self.assertEqual(report["summary"]["orders_delivered"], 3)
        self.assertGreater(report["summary"]["average_assignment_wait_minutes"], 0.0)
        self.assertIn("all agents are at capacity", " ".join(report["warnings"]))

    def test_scorer_prefers_agent_with_more_sla_margin(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(Coordinate(0, 0), Coordinate(1, 0), 1, 1.0),
                GraphEdge(Coordinate(5, 0), Coordinate(1, 0), 8, 1.0),
            ]
        )
        config = DispatchConfig.from_constraints({})
        scorer = AssignmentScorer(config, graph)
        order = Order("O1", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(1, 0), 2, "high", 20)
        fast_agent = Agent("A_FAST", Coordinate(0, 0), 4.0)
        slow_agent = Agent("A_SLOW", Coordinate(5, 0), 5.0)

        fast_score = scorer.score_candidate(order.created_at, order, fast_agent)
        slow_score = scorer.score_candidate(order.created_at, order, slow_agent)

        self.assertIsNotNone(fast_score)
        self.assertIsNotNone(slow_score)
        assert fast_score is not None
        assert slow_score is not None
        self.assertGreater(fast_score.remaining_sla_minutes, slow_score.remaining_sla_minutes)
        self.assertGreater(fast_score.score, slow_score.score)

    def test_summary_includes_high_priority_metrics(self) -> None:
        graph = TravelGraph(
            [
                GraphEdge(Coordinate(0, 0), Coordinate(1, 0), 1, 1.0),
            ]
        )
        orders = [
            Order("O1", datetime.fromisoformat("2026-05-03 09:00:00"), Coordinate(1, 0), 2, "high", 30),
        ]
        agents = [Agent("A001", Coordinate(0, 0), 4.5)]
        simulator = DispatchSimulator(
            orders=orders,
            agents=agents,
            graph=graph,
            config=DispatchConfig.from_constraints({}),
            dataset_name="unit-summary",
        )

        report = simulator.run()

        self.assertEqual(report["summary"]["sla_compliance_rate_percent"], 100.0)
        self.assertEqual(report["summary"]["high_priority_on_time_rate_percent"], 100.0)
        self.assertIsNotNone(report["summary"]["high_priority_average_sla_margin_minutes"])


if __name__ == "__main__":
    unittest.main()
