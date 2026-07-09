#!/usr/bin/env python3
"""Capture a Cesium Unity host report from local discovery and lane metadata."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from extensions.cesium.tools import cesium_example_workflow
from tools import unity_env


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="unity", choices=("unity",), help="Cesium engine lane to summarize")
    parser.add_argument("--unity-version", help="Unity version to prefer when selecting a local install")
    parser.add_argument("--native-target", choices=("windows", "linux", "mac"))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args(argv)


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Cesium Unity Host Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- host_platform: `{report['host']['platform']}`",
        f"- work_root: `{report['host']['work_root']}`",
        f"- default_install: `{(report['host']['default_install'] or {}).get('install_root') or 'none'}`",
        f"- version: `{report['compatibility_tracking']['version_matrix'][0]['version']}`",
        f"- package_count: `{report['compatibility_tracking']['version_matrix'][0]['package_count']}`",
        "",
        "## Discovered Installs",
        "",
    ]
    for install in report["host"]["installs"]:
        lines.append(f"- `{install['version']}` -> `{install['install_root']}`")
    lines.extend(["", "## Public Roots", ""])
    for root in report["host"]["public_roots"]:
        lines.append(f"- `{root}`")
    return "\n".join(lines) + "\n"


def build_report(native_target: str | None = None, *, unity_version: str | None = None) -> dict[str, object]:
    host = unity_env.describe_host()
    selected_install = unity_env.resolve_install(unity_version)
    discover = cesium_example_workflow.discover_payload("unity", native_target=native_target)
    doctor = cesium_example_workflow.doctor_payload("unity", native_target=native_target)
    return {
        "schema": "cesium.unity_host_report.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": "unity",
        "native_target": native_target,
        "unity_version": unity_version,
        "selected_install": selected_install.to_dict() if selected_install is not None else None,
        "host": host,
        "discover": discover,
        "doctor": doctor,
        "compatibility_tracking": discover["compatibility_tracking"],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args.native_target, unity_version=args.unity_version)
    json_path = out_dir / "unity_host_report.json"
    md_path = out_dir / "unity_host_report.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
