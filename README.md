# <span style="color:#FF6B35">🚀 Smart Delivery Dispatch System</span>

## <span style="color:#4ECDC4">👥 Team Information</span>
- **Team Name:** CODEHUSTLERS
- **Year:** 1st year
- **All-Female Team:** No

## <span style="color:#4ECDC4">📖 Overview</span>
Smart Delivery Dispatch System is a real-time dispatch simulator that assigns delivery agents to incoming orders using graph-based routing and explainable heuristic scoring. The goal is to minimize delivery time, reduce SLA violations, prioritize urgent orders, and maintain fair workload distribution across agents.

This project was built for the **Code2Create Challenge - Round 2 Hackathon**. The solution is intentionally lightweight, modular, and easy to explain, with the focus placed on sound decision logic, measurable performance, and resilience under difficult scenarios.

## <span style="color:#4ECDC4">🏗️ Architecture Overview</span>
Our approach is a modular event-driven dispatch pipeline.

- **🔀 Dispatch strategy:**
  Orders enter a pending queue and are processed by priority first (`high > normal > low`) and FIFO within the same priority. Each dispatch cycle evaluates all feasible agent-order matches and assigns the best available agent.

- **🧮 Agent scoring:**
  Each feasible agent is scored using a weighted heuristic that combines estimated delivery time, SLA margin, current workload, order priority, and agent rating. Tie-breakers prefer lower travel time, lighter workload, and higher rating.

- **⏱️ SLA, priority, and capacity handling:**
  High-priority orders receive stronger scoring weight. Orders close to SLA breach gain urgency automatically. Each agent can hold at most 2 active orders and executes them sequentially for predictable state tracking. If no valid agent is available, the order remains pending and the system emits warnings instead of failing silently.

- **⚙️ Main pipeline:**
  1. Load and validate CSV inputs.
  2. Skip malformed rows with descriptive warnings.
  3. Build the weighted travel graph.
  4. Precompute shortest paths for fast routing queries.
  5. Simulate order arrivals and delivery completions.
  6. Score feasible assignments and update agent/order state.
  7. Export delivery, SLA, fairness, and priority metrics.

## <span style="color:#4ECDC4">🎯 Design Principles</span>
- 💡 Explainable decisions over black-box complexity.
- ⚡ Fast assignment latency through precomputed routing.
- 🧩 Clear separation of concerns for maintainability.
- 🛡️ Graceful handling of invalid input and hard edge cases.
- 📊 Metrics-first evaluation so trade-offs are visible.

## <span style="color:#4ECDC4">📁 Project Structure</span>
```text
CODEHUSTLERS/
├── data/
│   ├── raw/
│   └── scenarios/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ISSUE_COVERAGE.md
│   └── SCENARIO_SUITE.md
├── output/
├── src/
│   └── smart_dispatch/
│       ├── config.py
│       ├── graph.py
│       ├── loaders.py
│       ├── metrics.py
│       ├── models.py
│       ├── scoring.py
│       └── simulator.py
├── tests/
│   └── test_dispatch.py
├── tools/
│   ├── generate_scenarios.py
│   └── run_scenario_suite.py
└── main.py
```

## <span style="color:#4ECDC4">🔧 Core Components</span>
- 📦 `loaders.py`
  Loads orders, agents, constraints, and graph edges from CSV files. Invalid rows are skipped with warnings so valid data can still run.

- 🗺️ `graph.py`
  Builds the weighted environment graph and precomputes shortest travel times between reachable nodes.

- 🏆 `scoring.py`
  Encapsulates the agent scoring logic based on delivery time, SLA pressure, fairness, priority, and rating.

- 🔄 `simulator.py`
  Runs the event-driven dispatch engine, manages state transitions, and handles queueing, assignment, and delivery completion.

- 📈 `metrics.py`
  Tracks delivery time, SLA performance, assignment waits, fairness spread, and per-priority outcomes.

- ⚙️ `config.py`
  Converts input constraints into runtime and scoring configuration so the behavior can be tuned without rewriting the engine.

## <span style="color:#4ECDC4">🧠 Algorithms and Decision Logic</span>
- 🗺️ **Routing:**
  Dijkstra-based shortest path computation over the environment graph, with paths precomputed for fast dispatch decisions.

- 🎯 **Dispatch selection:**
  Weighted heuristic scoring across feasible candidates.

- 📋 **Queue behavior:**
  Priority queue with FIFO ordering inside each priority class.

- ⚖️ **Fairness:**
  Agents with fewer historical assignments receive a small advantage to avoid overloading a single courier.

## <span style="color:#4ECDC4">📂 Input Data</span>
The system consumes four CSV files:

- 📋 `orders.csv`
  `order_id, timestamp, location_x, location_y, prep_time_minutes, priority, sla_minutes`

- 🧑‍💼 `agents.csv`
  `agent_id, current_x, current_y, rating`

- 🔒 `constraints.csv`
  runtime and scoring weights such as active order limits and priority weights

- 🌐 `environment_edges.csv`
  graph edges with travel time and delay multiplier

## <span style="color:#4ECDC4">📊 Metrics Tracked</span>
- ⏱️ Average delivery time
- ⏳ Average assignment wait time
- ✅ SLA compliance rate
- ❌ SLA breach rate
- 🔥 High-priority on-time rate
- 📐 High-priority average SLA margin
- 📦 Maximum queue depth
- ⚖️ Workload variance and standard deviation
- 📏 Assignment range across agents
- ⚡ Decision latency

## <span style="color:#4ECDC4">🧪 Validation and Testing</span>
The system is validated in two ways:

- 🔬 **Unit tests:**
  Covers routing behavior, malformed input handling, disconnected orders, capacity pressure, priority-sensitive assignment, and summary metrics.

- 🌪️ **Scenario suite:**
  Includes burst-demand, tight-SLA, noisy-input, and partial-disconnect scenarios to show how the pipeline behaves under stress and ambiguity.

**Current baseline results on the provided dataset:**

| Metric | Result |
|--------|--------|
| 📦 Orders Delivered | 150 / 150 |
| ⏱️ Avg Delivery Time | 14.01 minutes |
| ✅ SLA Compliance | 100.0% |
| ❌ SLA Breach Rate | 0.0% |
| 🔥 High-Priority On-Time | 100.0% |
| 📐 High-Priority SLA Margin | 29.78 minutes |
| ⚡ Avg Decision Latency | 0.097 ms |

## <span style="color:#4ECDC4">▶️ How to Run</span>
From the project root:

```bash
python main.py
```

To generate and run the stress-test scenario suite:

```bash
python tools/generate_scenarios.py
python tools/run_scenario_suite.py
```

## <span style="color:#4ECDC4">📤 Output</span>
The application writes:

- 📄 `output/metrics.json` — structured report for the main dataset
- 📝 `output/summary.txt` — human-readable summary for the main dataset
- 📁 `output/scenario_suite/` — aggregated stress-test results

## <span style="color:#4ECDC4">📌 Assumptions</span>
- Environment edges are treated as bidirectional travel links for practical routing.
- Each agent can hold at most 2 active orders.
- Active orders are executed sequentially to keep the state machine deterministic.
- Order location is treated as the service destination because the dataset does not include separate pickup and drop-off nodes.

## <span style="color:#4ECDC4">💪 Strengths of the Solution</span>
- ⚡ Fast and explainable dispatch decisions
- 🧩 Clean modular architecture
- 🎯 Strong handling of priority and SLA trade-offs
- ⚖️ Fairness-aware workload balancing
- 🛡️ Resilient behavior under malformed input and graph disruptions
- 🧪 Test coverage for both happy-path and stress-path scenarios

## <span style="color:#4ECDC4">🔮 Future Improvements</span>
- 🚦 Dynamic traffic updates during simulation
- 📊 Real-time dashboard for live metrics
- 🤖 Smarter adaptive weight tuning
- 🏋️ Batch optimization for extreme load bursts
- 🗺️ Richer visualization of queue and routing behavior

## <span style="color:#4ECDC4">✅ Conclusion</span>
This solution balances correctness, speed, modularity, and explainability. It performs strongly on the provided dataset, degrades realistically under stress scenarios, and provides enough structure and transparency to be defended confidently in a judging environment.