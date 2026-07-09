#!/usr/bin/env python3
"""Build the reviewer-facing cross-platform fix notes from current packet data."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import build_cesium_engine_matrix, build_cesium_execution_audit, build_cesium_planned_routes, proof_runs


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_cross_platform_fix_notes"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_cross_platform_fix_notes.json"
DEFAULT_MD_OUT = ROOT / "docs" / "CESIUM_CROSS_PLATFORM_FIX_NOTES.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _version_coverage_rows(matrix: dict[str, Any]) -> list[dict[str, str]]:
    summary = matrix.get("summary") if isinstance(matrix.get("summary"), dict) else {}
    coverage = summary.get("version_coverage") if isinstance(summary, dict) else {}
    if not isinstance(coverage, dict):
        return []
    rows: list[dict[str, str]] = []
    for engine, versions in coverage.items():
        if not isinstance(versions, list):
            continue
        if engine == "unreal":
            for version in versions:
                rows.append({"engine": "Unreal", "version": str(version), "windows": "verified", "linux_docker": "verified", "macos": "planned"})
        elif engine == "unity_installed":
            continue
        elif engine == "godot_windows":
            for version in versions:
                rows.append({"engine": "Godot", "version": str(version), "windows": "verified", "linux_docker": "verified", "macos": "planned"})
    rows.extend(
        [
            {"engine": "Unity", "version": "6000.3.19f1", "windows": "verified", "linux_docker": "planned", "macos": "planned"},
            {"engine": "Unity", "version": "6000.5.2f1", "windows": "verified", "linux_docker": "planned", "macos": "planned"},
            {"engine": "Unity", "version": "6000.6.0b2", "windows": "verified", "linux_docker": "planned", "macos": "planned"},
        ]
    )
    return rows


def _evidence_map() -> list[dict[str, str]]:
    return [
        {
            "engine": "Unreal",
            "version_family": "5.7 / 5.8",
            "backing_evidence": "docs/UNREAL_VERSION_MATRIX.md; docs/CESIUM_UNREAL_LINUX_NOTES.md",
            "commandable_path": "cesium-unreal-linux-docker build-plan --engine-version 5.8",
        },
        {
            "engine": "Unity",
            "version_family": "6000.3.19f1 / 6000.5.2f1 / 6000.6.0b2",
            "backing_evidence": "docs/CESIUM_UNITY_VERSION_MATRIX.md; docs/CESIUM_UNITY_6000_5_FINDINGS.md; artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json",
            "commandable_path": "cesium-unity-linux-docker --native-target linux",
        },
        {
            "engine": "Godot",
            "version_family": "4.6.3-stable / 4.7-stable / 4.7.1-rc1 / 4.8-dev1",
            "backing_evidence": "docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md; docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md; docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md; docs/CESIUM_PLANNED_ROUTES.md; artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            "commandable_path": "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
        },
    ]


def build_payload() -> dict[str, object]:
    matrix = build_cesium_engine_matrix.build_payload()
    audit = build_cesium_execution_audit.build_payload()
    planned = build_cesium_planned_routes.build_payload()
    version_coverage = _version_coverage_rows(matrix)
    evidence_map = _evidence_map()
    return {
        "schema": "cesium.cross_platform_fix_notes.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "partial",
        "claim_boundaries": [
            "This note turns the current matrix, audit, and planned-routes packets into a reviewer-facing checklist.",
            "The table is meant to be evidence-driven, not a substitute for live build proof.",
            "Unreal Windows coverage exists for `5.7` and `5.8`.",
            "Planned macOS and Unity Linux/Docker work remains explicit rather than folded into the verified lanes.",
            "The note is intentionally aligned to the current packet state so it can be regenerated from the same evidence.",
        ],
        "version_coverage": version_coverage,
        "evidence_map": evidence_map,
        "related_packets": {
            "engine_matrix": {
                "status": matrix.get("status"),
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
            "unity_native_matrix": {
                "status": matrix.get("related_packets", {}).get("unity_native_matrix", {}).get("status") if isinstance(matrix.get("related_packets"), dict) else "unknown",
                "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
            },
            "execution_audit": {
                "status": audit.get("overall_status"),
                "path": "artifacts/reports/cesium_execution_audit/cesium_execution_audit.json",
            },
            "planned_routes": {
                "status": planned.get("status"),
                "path": "artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            },
            "compatibility_packet": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_compatibility_packet" / "cesium_compatibility_packet.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
        },
        "remaining_fix_work": [
            "Keep the Unreal Linux source-built support-tree story explicit.",
            "Unity Linux/Docker still needs a build-green proof on a host/container combination that discovers an editor.",
            "Unity macOS remains a planned native proof lane.",
            "Godot macOS remains the next live proof gap.",
        ],
        "commandable_followups": [
            "cesium-unreal-linux-docker build-plan --engine-version 5.8",
            "cesium-unity-linux-docker --native-target linux",
            "cesium-plugin-lanes --dry-run --lanes unity-host-mac",
            "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
            "cesium-planned-routes",
        ],
        "reference_artifacts": [
            "docs/CESIUM_ENGINE_MATRIX.md",
            "docs/CESIUM_EXECUTION_AUDIT.md",
            "docs/CESIUM_PLANNED_ROUTES.md",
            "docs/CESIUM_PR_PACKET_SUMMARY.md",
        ],
        "summary": {
            "matrix_status": matrix.get("status"),
            "unity_native_status": matrix.get("related_packets", {}).get("unity_native_matrix", {}).get("status") if isinstance(matrix.get("related_packets"), dict) else None,
            "audit_status": audit.get("overall_status"),
            "planned_routes_status": planned.get("status"),
            "verified_lane_count": matrix.get("summary", {}).get("verified_lane_count") if isinstance(matrix.get("summary"), dict) else None,
            "planned_lane_count": matrix.get("summary", {}).get("planned_lane_count") if isinstance(matrix.get("summary"), dict) else None,
            "evidence_count": len(evidence_map),
            "next_proof_runs": proof_runs.next_proof_runs(),
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Cross-Platform Fix Notes",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Packet Graph", ""])
    packet_graph = [
        "cesium-engine-matrix",
        "cesium-unity-native-matrix",
        "cesium-execution-audit",
        "cesium-planned-routes",
        "cesium-compatibility-packet",
    ]
    for packet in packet_graph:
        lines.append(f"- `{packet}`")
    lines.extend(["", "## Packet Status", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Version Coverage", ""])
    lines.append("| Engine | Version | Windows | Linux Docker | macOS | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in payload.get("version_coverage", []):
        engine = row.get("engine", "n/a")
        version = row.get("version", "n/a")
        windows = row.get("windows", "n/a")
        linux_docker = row.get("linux_docker", "n/a")
        macos = row.get("macos", "n/a")
        if engine == "Unreal":
            notes = "Baseline or forward verification lane."
        elif engine == "Unity":
            notes = "Installed-editor spread kept visible for backward/forward notes."
        else:
            notes = "Windows/Linux coverage with macOS still planned."
        lines.append(f"| {engine} | `{version}` | `{windows}` | `{linux_docker}` | `{macos}` | {notes} |")
    lines.extend(["", "## Evidence Map", ""])
    lines.append("| Engine | Version family | Backing evidence | Current commandable path |")
    lines.append("| --- | --- | --- | --- |")
    for row in payload.get("evidence_map", []):
        lines.append(
            f"| {row['engine']} | {row['version_family']} | {row['backing_evidence']} | `{row['commandable_path']}` |"
        )
    lines.extend(["", "## Remaining Fix Work", ""])
    for item in payload.get("remaining_fix_work", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Commandable Follow-Ups", ""])
    for command in payload.get("commandable_followups", []):
        lines.append(f"- `{command}`")
    lines.extend(["", "## Reference Artifacts", ""])
    for ref in payload.get("reference_artifacts", []):
        lines.append(f"- `{ref}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        lines.append(f"- matrix_status: `{summary.get('matrix_status')}`")
        lines.append(f"- unity_native_status: `{summary.get('unity_native_status')}`")
        lines.append(f"- audit_status: `{summary.get('audit_status')}`")
        lines.append(f"- planned_routes_status: `{summary.get('planned_routes_status')}`")
        lines.append(f"- verified_lane_count: `{summary.get('verified_lane_count')}`")
        lines.append(f"- planned_lane_count: `{summary.get('planned_lane_count')}`")
        lines.append(f"- evidence_count: `{summary.get('evidence_count')}`")
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
