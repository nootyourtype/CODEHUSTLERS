# Scenario Suite

This scenario pack is meant to show that the dispatch pipeline is not only tuned to the provided raw dataset.

## Included Scenarios
- `burst_high_priority`: compresses many orders into the same short window and raises the share of high-priority requests.
- `limited_agents_tight_sla`: reduces the fleet and tightens deadlines to force queue pressure and harder assignment trade-offs.
- `partial_disconnect`: removes part of the travel graph so some orders become unreachable and should remain pending with warnings.
- `noisy_input_resilience`: injects malformed rows and off-grid records to confirm that valid data still runs while bad rows are skipped with warnings.

## How To Use
1. Generate the scenarios:
   `python tools/generate_scenarios.py`
2. Run the whole suite:
   `python tools/run_scenario_suite.py`

## What We Expect
- Some scenarios should show lower SLA compliance or pending orders.
- The noisy-input scenario should still execute because malformed rows are skipped.
- The disconnected scenario should surface explicit reachability warnings instead of failing silently.
