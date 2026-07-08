#!/usr/bin/env python3
"""Top-level Cesium compatibility command wrapper."""

from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parent
BOOTSTRAP_LOCAL_DEV_SCRIPT = ROOT / "tools" / "bootstrap_local_dev.py"
SOURCE_ROUTE_SCRIPT = ROOT / "extensions" / "cesium" / "tools" / "prepare_cesium_source_route.py"
EXAMPLE_WORKFLOW_SCRIPT = ROOT / "extensions" / "cesium" / "tools" / "cesium_example_workflow.py"


def _run_script(script: Path, argv: list[str]) -> int:
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(script), *argv]
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        if exc.code is None:
            return 0
        print(exc.code)
        return 1
    finally:
        sys.argv = old_argv
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Prepare a local Cesium dev environment and run the quick check")
    bootstrap.add_argument("args", nargs=argparse.REMAINDER)

    prep = subparsers.add_parser("prepare-source-route", help="Prepare the public Cesium source-route checkouts")
    prep.add_argument("args", nargs=argparse.REMAINDER)

    example = subparsers.add_parser("example", help="Run the Cesium example workflow wrapper")
    example.add_argument("args", nargs=argparse.REMAINDER)

    args, extra = parser.parse_known_args(argv)
    if getattr(args, "command", None) in {"bootstrap", "prepare-source-route", "example"}:
        remainder = list(getattr(args, "args", []))
        if extra:
            remainder.extend(extra)
        args.args = remainder
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "bootstrap":
        return _run_script(BOOTSTRAP_LOCAL_DEV_SCRIPT, args.args)
    if args.command == "prepare-source-route":
        return _run_script(SOURCE_ROUTE_SCRIPT, args.args)
    if args.command == "example":
        return _run_script(EXAMPLE_WORKFLOW_SCRIPT, args.args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
