#!/usr/bin/env python3
"""Entry point for the Smart Research Assistant."""
from __future__ import annotations

import argparse
import logging

from pipeline.orchestrator import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Research Assistant")
    parser.add_argument("--query", required=True, help="Research question")
    parser.add_argument("--output", default="report.json", help="Output file path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print(f"Researching: {args.query}")
    report = run(args.query)

    report_json = report.model_dump_json(indent=2)
    with open(args.output, "w") as f:
        f.write(report_json)

    print(f"\nReport saved to {args.output}")
    print(f"  Sources:       {len(report.sources)}")
    print(f"  Key findings:  {len(report.key_findings)}")
    print(f"  Total tokens:  {report.total_tokens_used:,}")
    print(f"  Cached tokens: {report.cached_tokens:,}")
    print(f"  Agent iters:   {report.agent_iterations}")


if __name__ == "__main__":
    main()
