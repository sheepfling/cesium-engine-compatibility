#!/usr/bin/env python3
"""Normalize visual-proof screenshots into the shared packet root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools import build_cesium_visual_proof


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("unreal", "unity", "godot"), required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--host", default="windows")
    parser.add_argument("--native-target", default="windows")
    parser.add_argument("--architecture", default="x86_64")
    parser.add_argument("--overwrite", action="store_true", default=False)
    return parser.parse_args(argv)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return build_cesium_visual_proof.normalize_visual_proof_capture(
        args.engine,
        args.source_root,
        args.capture_root,
        host=getattr(args, "host", "windows"),
        native_target=getattr(args, "native_target", "windows"),
        architecture=getattr(args, "architecture", "x86_64"),
        overwrite=args.overwrite,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("status") in {"pass", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
