"""
Phase 4, step 3: drift detection.

Per-run diffs (diff_runs.py) catch sudden regressions between two specific
runs. This module catches a different failure mode: a slow decline across
many runs, where each individual step is too small to trip a warning/critical
threshold, but the cumulative trend is a real problem.
"""
import sys
from pathlib import Path
from pydantic import BaseModel

from diff_runs import load_run, RUNS_DIR

# How many of the most recent runs to include in the rolling window.
WINDOW_SIZE = 7

# If the rolling average pass rate drops below this, relative to the
# earliest run in the window, flag a slow-drift warning.
DRIFT_THRESHOLD = 0.05


class DriftReport(BaseModel):
    window_size: int
    runs_considered: int
    pass_rates: list[float]        # oldest to newest, within the window
    rolling_avg_pass_rate: float
    earliest_pass_rate: float
    latest_pass_rate: float
    drift_delta: float             # latest - earliest, negative = declining
    drift_detected: bool


def _all_runs_sorted() -> list[Path]:
    """All saved runs, oldest first (filenames sort lexically by timestamp)."""
    return sorted(RUNS_DIR.glob("run_*.json"))


def compute_drift(window_size: int = WINDOW_SIZE) -> DriftReport:
    all_runs = _all_runs_sorted()
    window = all_runs[-window_size:]  # the most recent `window_size` runs

    if len(window) < 2:
        raise ValueError(
            f"Need at least 2 runs to assess drift, found {len(window)}. "
            "Run the eval pipeline a few more times first."
        )

    pass_rates = []
    for run_path in window:
        data = load_run(run_path)
        total = len(data["results"])
        passed = sum(1 for r in data["results"] if r["category_match"])
        pass_rates.append(passed / total)

    rolling_avg = sum(pass_rates) / len(pass_rates)
    earliest = pass_rates[0]
    latest = pass_rates[-1]
    drift_delta = latest - earliest

    # Drift is a *declining trend*, not just any difference -- a single
    # bad run inside an otherwise stable window shouldn't trigger this.
    # We require the trend across the window to be consistently negative,
    # not just the two endpoints.
    is_declining_trend = all(
        pass_rates[i] <= pass_rates[i - 1] + 0.001  # small epsilon for float noise
        for i in range(1, len(pass_rates))
    )
    drift_detected = drift_delta <= -DRIFT_THRESHOLD and is_declining_trend

    return DriftReport(
        window_size=window_size,
        runs_considered=len(window),
        pass_rates=pass_rates,
        rolling_avg_pass_rate=rolling_avg,
        earliest_pass_rate=earliest,
        latest_pass_rate=latest,
        drift_delta=drift_delta,
        drift_detected=drift_detected,
    )


def print_drift_report(report: DriftReport) -> None:
    print(f"Drift analysis over last {report.runs_considered} run(s) "
          f"(window size {report.window_size}):\n")
    trend = " -> ".join(f"{p:.0%}" for p in report.pass_rates)
    print(f"Pass rate trend: {trend}")
    print(f"Rolling average: {report.rolling_avg_pass_rate:.1%}")
    print(f"Earliest -> latest: {report.earliest_pass_rate:.0%} -> "
          f"{report.latest_pass_rate:.0%} ({report.drift_delta:+.0%})\n")

    if report.drift_detected:
        print("⚠️  SLOW DRIFT DETECTED: consistent decline across the window, "
              "even though no single run may have triggered a critical alert.")
    else:
        print("No slow drift detected.")


if __name__ == "__main__":
    window_size = int(sys.argv[1]) if len(sys.argv) > 1 else WINDOW_SIZE
    report = compute_drift(window_size)
    print_drift_report(report)