#!/usr/bin/env python3
"""CLI for running evaluations."""

import argparse
import asyncio
import sys
from typing import Any

from app.evaluation import Evaluator


def print_summary(report: dict[str, Any]) -> None:
    """Print evaluation summary."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY".center(60))
    print("=" * 60)
    print(f"\nModel: {report['model']}")
    print(f"Duration: {report['duration_seconds']}s")
    print(f"Total Traces: {report['total_traces']}")

    if report["total_traces"] > 0:
        success_rate = (report["successful_traces"] / report["total_traces"]) * 100
        print(f"Success Rate: {success_rate:.1f}% ({report['successful_traces']}/{report['total_traces']})")

        print("\nMetrics:")
        for metric_name, data in report["metrics_summary"].items():
            total = data["success_count"] + data["failure_count"]
            if total > 0:
                pct = (data["success_count"] / total) * 100
                print(f"  • {metric_name}: {pct:.1f}% success, avg score: {data['avg_score']:.2f}")

    if report.get("report_path"):
        print(f"\nReport saved: {report['report_path']}")

    print("=" * 60 + "\n")


async def run_evaluation(no_report: bool = False) -> None:
    """Run the evaluation."""
    print("Starting evaluation...")
    print(f"Report generation: {'disabled' if no_report else 'enabled'}\n")

    try:
        evaluator = Evaluator()
        report = await evaluator.run(generate_report_file=not no_report)
        print_summary(report)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run evaluations on agent outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--no-report", action="store_true", help="Skip generating JSON report file")

    args = parser.parse_args()

    try:
        asyncio.run(run_evaluation(no_report=args.no_report))
    except KeyboardInterrupt:
        print("\nEvaluation canceled")
        sys.exit(130)


if __name__ == "__main__":
    main()
