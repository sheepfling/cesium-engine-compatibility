#!/usr/bin/env python3
"""Build the unified Windows visual-proof packet across Unreal, Unity, and Godot."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import (
    build_cesium_visual_proof,
    build_godot_visual_proof,
    build_unity_visual_proof,
    build_unreal_visual_proof,
    compare_cesium_visual_proof,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "windows_visual_proof"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "windows_visual_proof.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "windows_visual_proof.md"


def _runner_rows() -> list[dict[str, Any]]:
    return [
        {
            "engine": "unreal",
            "report": build_unreal_visual_proof.build_payload(),
        },
        {
            "engine": "unity",
            "report": build_unity_visual_proof.build_payload(),
        },
        {
            "engine": "godot",
            "report": build_godot_visual_proof.build_payload(),
        },
    ]


def build_payload() -> dict[str, Any]:
    visual_proof = build_cesium_visual_proof.build_payload()
    compare = compare_cesium_visual_proof.build_payload(strict_missing=True)
    runners = _runner_rows()
    commandable = all(row["report"].get("status") == "commandable" for row in runners)
    runner_commands = [
        {
            "engine": row["engine"],
            "startup_health_command": row["report"].get("command"),
            "launch_command": row["report"].get("launcher_command") or row["report"].get("command"),
            "normalize_command": row["report"].get("normalize_command"),
            "manifest_path": row["report"].get("manifest_path"),
            "expected_pngs": row["report"].get("expected_pngs", []),
            "engine_side_harness_status": row["report"].get("engine_side_harness_status"),
        }
        for row in runners
    ]
    return {
        "schema": "cesium.windows_visual_proof.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "commandable" if commandable else "planned",
        "visual_proof_packet": {
            "status": visual_proof.get("status"),
            "path": "artifacts/reports/cesium_visual_proof/cesium_visual_proof.json",
        },
        "comparison_packet": {
            "status": compare.get("status"),
            "path": "artifacts/reports/cesium_visual_proof_compare/cesium_visual_proof_compare.json",
        },
        "runner_reports": [
            {
                "engine": row["engine"],
                "status": row["report"].get("status"),
                "path": {
                    "unreal": "artifacts/reports/unreal_visual_proof/unreal_visual_proof.json",
                    "unity": "artifacts/reports/unity_visual_proof/unity_visual_proof.json",
                    "godot": "artifacts/reports/godot_visual_proof/godot_visual_proof.json",
                }[row["engine"]],
            }
            for row in runners
        ],
        "runner_commands": runner_commands,
        "camera_shots": visual_proof.get("camera_shots", []),
        "next_steps": [
            "Run the engine-specific Windows proof commands to produce the per-engine runner reports.",
            "Run `cesium-windows-visual-proof-run` to launch the actual engine lanes, normalize the captures, and apply the compare gate.",
            "Normalize the raw capture roots into the shared visual-proof root.",
            "Run the compare gate so black, gray, flat, and drifted frames fail the lane automatically.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Windows Visual Proof",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Runner Commands",
        "",
    ]
    for row in payload.get("runner_commands", []):
        lines.append(f"### {row['engine']}")
        lines.append(f"- startup_health_command: `{row.get('startup_health_command')}`")
        lines.append(f"- launch_command: `{row.get('launch_command')}`")
        lines.append(f"- normalize_command: `{row.get('normalize_command')}`")
        lines.append(f"- manifest_path: `{row.get('manifest_path')}`")
    lines.extend(["", "## Runner Reports", ""])
    for row in payload.get("runner_reports", []):
        lines.append(f"- `{row['engine']}`: `{row['status']}` -> `{row['path']}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args(argv)

    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"planned", "commandable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
