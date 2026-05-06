# Architecture Notes

## Goal
Build a clean, modular MVP for the Smart Delivery Dispatch System that matches the PDF, `ISSUES.md`, and the submission `README.md`.

## Modules
- `main.py`: CLI entrypoint and report writer.
- `src/smart_dispatch/loaders.py`: CSV loading, validation, and input bundle creation.
- `src/smart_dispatch/graph.py`: bidirectional travel graph and all-pairs shortest-path lookup.
- `src/smart_dispatch/config.py`: runtime and scoring configuration derived from the input constraints.
- `src/smart_dispatch/scoring.py`: candidate evaluation and tie-breaking logic.
- `src/smart_dispatch/simulator.py`: event-driven dispatch simulation and state transitions.
- `src/smart_dispatch/metrics.py`: incremental metrics tracking and report assembly.

## Runtime Flow
1. Load and validate the raw CSV files.
2. Skip malformed rows with descriptive warnings so valid records can still be processed.
3. Build the graph and precompute shortest travel times.
4. Convert constraints into runtime and scoring configuration.
5. Simulate order arrivals in timestamp order.
6. Score feasible agents for each pending order.
7. Apply assignments atomically and schedule start/completion events.
8. Update metrics as orders complete.
9. Export structured JSON and a human-readable text summary.

## Important Assumptions
- The graph edges are treated as bidirectional because the provided road grid is directional only in the CSV.
- Each agent may hold up to two active orders, but orders are executed sequentially to keep the state model deterministic for the MVP.
- The single order location in the dataset is treated as the service destination because no separate pickup and drop-off nodes are supplied.

## Why This Structure Helps Judging
- Code quality: each responsibility lives in a dedicated module.
- Modularity: scoring, metrics, graph logic, and I/O can be reasoned about independently.
- Soundness: assumptions are explicit and reflected in both code and output.
- Real-time behavior: shortest paths are precomputed once so assignment decisions stay fast.
- Robustness: malformed rows, unreachable orders, and overloaded queues produce warnings instead of silent failure.
