"""Command-line entry point for Proofloom."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmarks
from .data import HERO_SEED, export_hero_dataset, generate_hero_dataset
from .domain import money_inr
from .evaluation import run_evaluation
from .service import ProofloomService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofloom", description="Verification-first synthetic settlement close")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="run the deterministic four-settlement close")
    evaluation = sub.add_parser("evaluate", help="reproduce the merchant-group-held-out evaluation")
    evaluation.add_argument("--output", default="evaluation")
    evaluation.add_argument("--bootstrap-resamples", type=int, default=500)
    benchmark = sub.add_parser("benchmark", help="run bounded local benchmarks")
    benchmark.add_argument("--output", default="benchmarks")
    export = sub.add_parser("export-data", help="export deterministic hero fixtures")
    export.add_argument("--output", default="data/demo")
    serve = sub.add_parser("serve", help="start the local operator UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        service = ProofloomService()
        payload = service.run_close()
        review = next((item for item in payload["decisions"] if item["status"] == "review_required"), None)
        if review is not None:
            payload = service.review(
                review["decision_id"],
                action="approve",
                reviewer="demo-controller",
                requested_amount_paise=review["expected_amount_paise"],
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
        summary = payload["summary"]
        print(
            f"\nClosed {summary['closed']}/{len(payload['decisions'])}; "
            f"matched {money_inr(summary['matched_value_paise'])}; "
            f"audit {'valid' if payload['audit']['valid'] else 'invalid'}.",
        )
        return 0
    if args.command == "evaluate":
        result = run_evaluation(args.output, bootstrap_resamples=args.bootstrap_resamples)
        print(json.dumps(result["policy_comparison"], indent=2, sort_keys=True))
        return 0
    if args.command == "benchmark":
        result = run_benchmarks(args.output)
        print(json.dumps(result["workloads"], indent=2, sort_keys=True))
        return 0
    if args.command == "export-data":
        export_hero_dataset(generate_hero_dataset(HERO_SEED), args.output)
        print(f"Exported deterministic hero data to {Path(args.output).resolve()}")
        return 0
    if args.command == "serve":
        import uvicorn

        uvicorn.run("proofloom.api:app", host=args.host, port=args.port, reload=False)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
