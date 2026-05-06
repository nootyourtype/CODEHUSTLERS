# Issue Coverage

This note maps the MVP implementation to the problem statement and `ISSUES.md`.

## Covered in the Current Build
- Issues 1-3: CSV loading, validation, and graph construction are implemented.
- Issues 4-6: pending-order prioritization, agent registry behavior, and candidate generation are implemented.
- Issues 7-11: heuristic scoring, configurable priorities, assignment application, delivery completion, and re-queueing after completions are implemented.
- Issues 12-15: delivery, SLA, fairness, and per-priority metrics are implemented with structured JSON output and a readable summary.
- Issue 16: malformed CSV rows, missing required files, invalid values, and referential-integrity problems are handled with descriptive warnings while valid records continue processing.
- Issue 17: tie-breaking, queueing when no agent is feasible, and disconnected-path filtering are implemented.
- Issue 18: shortest paths are precomputed and decision latency is measured against the stricter 500ms evaluation target.
- Issue 20: `README.md` contains the extraction-safe architecture summary, and this document plus `ARCHITECTURE.md` hold the fuller explanation.

## Partially Covered
- Issue 19: runtime processing throughput is reported, but the dataset itself is not a 100-orders-per-minute arrival stream, so this is measured as engine capacity rather than dataset arrival rate.

## Intentional MVP Trade-Offs
- The solver uses a weighted heuristic rather than a global optimizer. This matches the PDF guidance that strong reasoning is preferred over unnecessary complexity.
- Active orders are queued sequentially per agent. This keeps state transitions deterministic and easier to explain under judging.
- Resilience is demonstrated through tests for malformed rows, disconnected orders, overloaded queues, and priority-sensitive assignment behavior.
