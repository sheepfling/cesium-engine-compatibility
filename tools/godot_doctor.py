#!/usr/bin/env python3
"""Convenience wrapper for the Godot example doctor lane."""

from __future__ import annotations

import argparse

from extensions.cesium.tools import cesium_example_workflow


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    forwarded = [
        "doctor",
        "--engine",
        "godot",
        "--native-target",
        args.native_target,
        "--format",
        args.format,
    ]
    return cesium_example_workflow.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
