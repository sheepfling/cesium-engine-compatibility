#!/usr/bin/env python3
"""Build a dry-run packet for the remaining cross-platform planned routes."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from tools import build_cesium_engine_matrix, build_cesium_execution_audit, proof_runs, run_cesium_plugin_lanes


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_planned_routes"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_planned_routes.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_planned_routes.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _planned_bundle_payload() -> dict[str, Any]:
    return run_cesium_plugin_lanes.build_payload(
        run_cesium_plugin_lanes.parse_args(["--dry-run", "--lanes", "cross-platform-planned"])
    )


def build_payload() -> dict[str, object]:
    bundle = _planned_bundle_payload()
    lanes = bundle.get("lanes", []) if isinstance(bundle.get("lanes"), list) else []
    host_roots = engine_root_discovery.public_engine_search_roots()
    engine_matrix = build_cesium_engine_matrix.build_payload()
    execution_audit = build_cesium_execution_audit.build_payload()
    evidence = [
        {
            "surface": "planned-routes",
            "kind": "dry_run_bundle",
            "path": "artifacts/reports/cesium_lane_runner/cesium_plugin_lanes.json",
            "exists": (ROOT / "artifacts" / "reports" / "cesium_lane_runner" / "cesium_plugin_lanes.json").is_file(),
        },
    ]
    seen_commands: set[str] = set()
    for lane in lanes:
        lane_id = str(lane.get("id") or "")
        if not lane_id:
            continue
        for task in lane.get("tasks", []):
            if not isinstance(task, dict):
                continue
            for command in task.get("commands", []):
                if not isinstance(command, dict):
                    continue
                command_text = str(command.get("command") or "")
                if not command_text or command_text in seen_commands:
                    continue
                seen_commands.add(command_text)
                evidence.append(
                    {
                        "surface": lane_id,
                        "kind": "planned_command",
                        "path": command_text,
                        "exists": True,
                    }
                )
    return {
        "schema": "cesium.planned_routes.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "dry-run" if bundle.get("overall_status") == "dry-run" else str(bundle.get("overall_status") or "partial"),
        "claim_boundaries": [
            "This packet records the remaining planned routes as a commandable dry-run bundle, not as build-green proof.",
            "Unreal Linux parity, Unity Linux/Docker, Unity macOS, and Godot macOS stay explicit and separate.",
            "The bundle keeps the fresh-host bootstrap story tied to the same runner shape used by the rest of the compatibility packet.",
            "A dry-run packet can prove commandability and inventory without pretending the underlying lane has passed.",
        ],
        "host": {
            "unreal_public_roots": [str(path) for path in host_roots["unreal"]],
            "unity_public_roots": [str(path) for path in host_roots["unity"]],
            "godot_public_roots": [str(path) for path in host_roots["godot"]],
        },
        "evidence": evidence,
        "bundle": bundle,
        "related_packets": {
            "engine_matrix": {
                "status": engine_matrix.get("status"),
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
            "execution_audit": {
                "status": execution_audit.get("overall_status"),
                "path": "artifacts/reports/cesium_execution_audit/cesium_execution_audit.json",
            },
            "compatibility_packet": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_compatibility_packet" / "cesium_compatibility_packet.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
        },
        "summary": {
            "bundle_lane_count": len(lanes),
            "bundle_task_count": sum(len(lane.get("tasks", [])) for lane in lanes if isinstance(lane, dict)),
            "bundle_command_count": sum(
                len(task.get("commands", []))
                for lane in lanes
                if isinstance(lane, dict)
                for task in lane.get("tasks", [])
                if isinstance(task, dict)
            ),
            "bundle_lane_ids": [str(lane.get("id") or "") for lane in lanes if isinstance(lane, dict)],
            "next_proof_runs": proof_runs.next_proof_runs(),
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Planned Routes",
        "",
        "This note points to the dedicated dry-run packet for the remaining cross-platform bootstrap routes.",
        "",
        "Use this command to regenerate the packet:",
        "",
        "```bash",
        "cesium-planned-routes",
        "```",
        "",
        "## What It Covers",
        "",
        "- Unreal Linux parity follow-up routes",
        "- Unity Linux/Docker planned proof routes",
        "- Unity macOS planned proof routes",
        "- Godot macOS planned proof routes",
        "- the shared host-root discovery used for bootstrap on a fresh machine",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Host Roots", ""])
    host = payload.get("host", {})
    if isinstance(host, dict):
        lines.append(f"- unreal_public_roots: `{', '.join(host.get('unreal_public_roots', [])) or 'none'}`")
        lines.append(f"- unity_public_roots: `{', '.join(host.get('unity_public_roots', [])) or 'none'}`")
        lines.append(f"- godot_public_roots: `{', '.join(host.get('godot_public_roots', [])) or 'none'}`")
    lines.extend(["", "## Packet Graph", ""])
    for packet in [
        "cesium-engine-matrix",
        "cesium-execution-audit",
        "cesium-compatibility-packet",
    ]:
        lines.append(f"- `{packet}`")
    lines.extend(["", "## Packet Status", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Evidence", ""])
    for row in payload.get("evidence", []):
        lines.append(f"- `{row['surface']}`: `{row['kind']}` -> `{row['path']}`")
    lines.extend(["", "## Bundle", ""])
    bundle = payload.get("bundle", {})
    if isinstance(bundle, dict):
        lines.append(f"- overall_status: `{bundle.get('overall_status')}`")
        lines.append(f"- selected_lanes: `{', '.join(bundle.get('selected_lanes', [])) or 'none'}`")
        lines.append(f"- log_dir: `{bundle.get('log_dir')}`")
        lines.append("")
        lines.append("| Lane | Status | Kind |")
        lines.append("| --- | --- | --- |")
        for lane in bundle.get("lanes", []):
            if not isinstance(lane, dict):
                continue
            lines.append(f"| `{lane.get('id')}` | `{lane.get('status')}` | `{lane.get('lane_kind')}` |")
        lines.append("")
        lines.append("### Commands")
        lines.append("")
        for lane in bundle.get("lanes", []):
            if not isinstance(lane, dict):
                continue
            lines.append(f"- `{lane.get('id')}`")
            for task in lane.get("tasks", []):
                if not isinstance(task, dict):
                    continue
                lines.append(f"  - `{task.get('id')}`: `{task.get('status')}`")
                for command in task.get("commands", []):
                    if isinstance(command, dict):
                        lines.append(f"    - `{command.get('command')}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        lines.append(f"- bundle_lane_count: `{summary.get('bundle_lane_count')}`")
        lines.append(f"- bundle_task_count: `{summary.get('bundle_task_count')}`")
        lines.append(f"- bundle_command_count: `{summary.get('bundle_command_count')}`")
        lines.append(f"- bundle_lane_ids: `{', '.join(summary.get('bundle_lane_ids', [])) or 'none'}`")
        lines.extend(["", "## Next Proof Runs", ""])
        for run in summary.get("next_proof_runs", []):
            lines.append(f"- `{run['surface']}`: `{run['command']}`")
            for focus in run.get("capture_focus", []):
                lines.append(f"  - {focus}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
