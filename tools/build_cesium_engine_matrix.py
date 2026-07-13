#!/usr/bin/env python3
"""Build a Cesium engine matrix across Unreal, Unity, and Godot lanes."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from extensions.cesium.tools import cesium_example_workflow, unreal_linux_lane
from tools import build_unity_native_matrix, proof_runs, unity_env


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_engine_matrix"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_engine_matrix.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_engine_matrix.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _matrix_rows(source: object) -> list[dict[str, object]]:
    if not isinstance(source, dict):
        return []
    for key in ("version_matrix", "windows_version_matrix", "linux_version_matrix"):
        rows = source.get(key)
        if isinstance(rows, list):
            normalized: list[dict[str, object]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                normalized.append(row)
            if normalized:
                return normalized
    return []


def _summary_row(
    name: str,
    payload: dict[str, object],
    *,
    lane: str,
    native_target: str | None = None,
    version_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    tracking = payload.get("compatibility_tracking")
    source = tracking if isinstance(tracking, dict) else payload
    rows = version_rows if version_rows is not None else _matrix_rows(source)
    evidence_tier = "planned" if lane in {"godot-mac", "unity-linux-docker"} else "verified"
    status = "planned" if evidence_tier == "planned" else str(payload.get("status") or payload.get("overall_status") or "unknown")
    if lane == "unreal-linux" and str(payload.get("build_status") or "") == "verified":
        status = "verified"
    summary = {
        "lane": lane,
        "engine": name,
        "native_target": native_target,
        "status": status,
        "evidence_tier": evidence_tier,
        "preferred_version": payload.get("preferred_version"),
        "version_count": len(rows),
        "versions": [str(row.get("version") or row.get("engine_version") or "") for row in rows],
        "public_search_roots": list(source.get("public_search_roots", [])) if isinstance(source, dict) else [],
        "build_commands": list(source.get("build_commands", [])) if isinstance(source, dict) and isinstance(source.get("build_commands"), list) else [],
        "native_lane_commands": source.get("native_lane_commands", {}) if isinstance(source, dict) else {},
        "next_steps": list(payload.get("next_steps", [])) if isinstance(payload.get("next_steps"), list) else [],
        "source_route_root": payload.get("source_route_root"),
        "build_plan": _build_plan_for_lane(lane, name, native_target=native_target),
    }
    return summary


def _matrix_status(lanes: list[dict[str, object]]) -> str:
    statuses = [str(lane.get("status") or "") for lane in lanes]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "planned" for status in statuses):
        return "partial"
    if statuses and all(status in {"verified", "pass", "ok"} for status in statuses):
        return "complete"
    return "partial" if lanes else "unknown"


def _matrix_claim_boundaries() -> list[str]:
    return [
        "Verified lanes are the ones we can defend today; planned lanes stay explicitly labeled so the matrix never pretends a gap is green.",
        "Unreal Linux Docker is verified on this host, while the source-built Linux support tree remains an upstream-parity follow-up.",
        "Unity Linux/Docker has live Docker report evidence but still waits on build-green proof, Unity macOS remains planned, and Godot macOS remains a commandable proof route.",
        "The matrix unions Windows-native, Linux Docker, and host-only evidence into one packet-friendly view of the current compatibility picture.",
    ]


def _matrix_gaps(lanes: list[dict[str, object]], *, unity_native_targets: list[dict[str, object]] | None = None) -> list[str]:
    gaps: list[str] = []
    if any(lane["lane"] == "unity-linux-docker" and lane["status"] == "planned" for lane in lanes):
        gaps.append("Unity Linux/Docker remains planned.")
    if any(lane["lane"] == "godot-mac" and lane["status"] == "planned" for lane in lanes):
        gaps.append("Godot macOS remains planned.")
    if any(lane["lane"] == "unreal-linux" and lane["status"] != "verified" for lane in lanes):
        gaps.append("Unreal Linux Docker still needs a verified build artifact before it can be called fully green.")
    if unity_native_targets and any(
        str(target.get("target") or "") == "mac" and str(target.get("status") or "") != "verified"
        for target in unity_native_targets
    ):
        gaps.append("Unity macOS remains planned.")
    return gaps


def _matrix_evidence() -> list[dict[str, object]]:
    return [
        {
            "surface": "unreal-windows",
            "kind": "version_matrix",
            "path": "docs/UNREAL_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "UNREAL_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "unreal-linux",
            "kind": "linux_notes",
            "path": "docs/CESIUM_UNREAL_LINUX_NOTES.md",
            "exists": (ROOT / "docs" / "CESIUM_UNREAL_LINUX_NOTES.md").is_file(),
        },
        {
            "surface": "unreal-macos",
            "kind": "macos_silicon_notes",
            "path": "docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
            "exists": (ROOT / "docs" / "CESIUM_MACOS_SILICON_BUILD_NOTES.md").is_file(),
        },
        {
            "surface": "unity-windows",
            "kind": "version_matrix",
            "path": "docs/CESIUM_UNITY_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "CESIUM_UNITY_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "unity",
            "kind": "findings",
            "path": "docs/CESIUM_UNITY_6000_5_FINDINGS.md",
            "exists": (ROOT / "docs" / "CESIUM_UNITY_6000_5_FINDINGS.md").is_file(),
        },
        {
            "surface": "unity-native",
            "kind": "native_matrix",
            "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
            "exists": (ROOT / "artifacts" / "reports" / "unity_native_matrix" / "unity_native_matrix.json").is_file(),
        },
        {
            "surface": "unity-linux-docker",
            "kind": "docker_report",
            "path": "artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json",
            "exists": (ROOT / "artifacts" / "reports" / "unity_linux_docker" / "cesium-unity_linux_docker.json").is_file(),
        },
        {
            "surface": "godot-linux-docker",
            "kind": "docker_report",
            "path": "artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.json",
            "exists": (ROOT / "artifacts" / "reports" / "godot_linux_docker" / "cesium-godot_linux_docker.json").is_file(),
        },
        {
            "surface": "godot-windows",
            "kind": "version_matrix",
            "path": "docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "godot-linux",
            "kind": "version_matrix",
            "path": "docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "CESIUM_GODOT_LINUX_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "godot-mac",
            "kind": "cross_platform_notes",
            "path": "docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md",
            "exists": (ROOT / "docs" / "CESIUM_GODOT_CROSS_PLATFORM_NOTES.md").is_file(),
        },
        {
            "surface": "packet-summary",
            "kind": "review_packet",
            "path": "docs/CESIUM_PR_PACKET_SUMMARY.md",
            "exists": (ROOT / "docs" / "CESIUM_PR_PACKET_SUMMARY.md").is_file(),
        },
    ]


def _build_plan_for_lane(lane: str, engine: str, *, native_target: str | None = None) -> list[str]:
    if lane == "unreal-windows":
        return [
            "cesium-example report --engine unreal",
            "cesium-example report --engine unreal --format json",
        ]
    if lane == "unreal-linux":
        return [
            "cesium-unreal-linux-docker build-plan --engine-version 5.7",
            "cesium-unreal-linux-docker build-plan --engine-version 5.8",
            "cesium-unreal-linux-docker build --engine-version 5.8",
        ]
    if lane == "unity-windows":
        return [
            "cesium-capture-unity-host-report --native-target windows",
            "cesium-stage-unity-host-report",
            "cesium-export-unity-host-handoff",
            "cesium-import-unity-host-report dist/unity_host_handoff/cesium-unity-host-handoff.zip",
        ]
    if lane == "unity-linux-docker":
        return [
            "cesium-unity-linux-docker --native-target linux",
            "cesium-plugin-lanes --dry-run --lanes unity-host-linux-docker",
            "cesium-unity-native-matrix",
        ]
    if lane == "godot-windows":
        return [
            "cesium-example report --engine godot --native-target windows",
            "cesium-example doctor --engine godot --native-target windows",
        ]
    if lane == "godot-linux":
        return [
            "cesium-example report --engine godot --native-target linux",
            "cesium-example doctor --engine godot --native-target linux",
        ]
    if lane == "godot-mac":
        return [
            "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
            "cesium-example report --engine godot --native-target mac",
            "cesium-example doctor --engine godot --native-target mac",
        ]
    return [f"cesium-example report --engine {engine}{' --native-target ' + native_target if native_target else ''}"]


def build_payload() -> dict[str, object]:
    unreal = cesium_example_workflow.report_payload("unreal")
    unity = cesium_example_workflow.report_payload("unity")
    unity_native = build_unity_native_matrix.build_payload()
    unity_installs = [install.to_dict() for install in unity_env.discover_installs()]
    unity_linux_docker_plan = [
        "cesium-unity-linux-docker --native-target linux",
        "cesium-unity-native-matrix",
        "cesium-plugin-lanes --dry-run --lanes unity-host-linux-docker",
    ]
    unity_native_targets = unity_native.get("targets") if isinstance(unity_native.get("targets"), list) else []
    godot_windows = cesium_example_workflow.report_payload("godot", native_target="windows")
    godot_linux = cesium_example_workflow.report_payload("godot", native_target="linux")
    godot_mac = cesium_example_workflow.report_payload("godot", native_target="mac")
    unreal_linux = unreal_linux_lane.report_payload()
    lanes = [
        _summary_row("unreal", unreal, lane="unreal-windows"),
        _summary_row("unreal-linux", unreal_linux, lane="unreal-linux"),
        _summary_row("unity", unity, lane="unity-windows", version_rows=unity_installs or None),
        _summary_row("unity", unity, lane="unity-linux-docker", native_target="linux", version_rows=unity_installs or None),
        _summary_row("godot", godot_windows, lane="godot-windows", native_target="windows"),
        _summary_row("godot", godot_linux, lane="godot-linux", native_target="linux"),
        _summary_row("godot", godot_mac, lane="godot-mac", native_target="mac"),
    ]
    evidence = _matrix_evidence()
    status = _matrix_status(lanes)
    return {
        "schema": "cesium.engine_matrix.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "note": (
            "The matrix unions Windows-native, Linux Docker, and host-only evidence into a single packet-friendly compatibility picture, with evidence tiers separating verified lanes from planned lanes, the discovered Unity install spread staying visible beside the planned macOS and Linux targets, and the Unity proof lane remaining pinned to 6000.5.0f1."
            if status != "fail"
            else "The matrix captures the current compatibility picture, but at least one lane still reports failure."
        ),
        "claim_boundaries": _matrix_claim_boundaries(),
        "evidence": evidence,
        "gaps": _matrix_gaps(lanes, unity_native_targets=unity_native_targets),
        "related_packets": {
            "unity_native_matrix": {
                "status": unity_native.get("status"),
                "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
            },
            "execution_audit": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_execution_audit" / "cesium_execution_audit.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_execution_audit/cesium_execution_audit.json",
            },
            "planned_routes": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_planned_routes" / "cesium_planned_routes.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            },
            "compatibility_packet": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_compatibility_packet" / "cesium_compatibility_packet.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
        },
        "lane_count": len(lanes),
        "lanes": lanes,
        "summary": {
            "engines": ["unreal", "unreal-linux", "unity", "godot"],
            "verified_lane_count": sum(1 for lane in lanes if lane["evidence_tier"] == "verified"),
            "planned_lane_count": sum(1 for lane in lanes if lane["evidence_tier"] == "planned"),
            "evidence_count": len(evidence),
            "next_proof_runs": proof_runs.next_proof_runs(),
            "version_coverage": {
                "unreal": [row["version"] for row in _matrix_rows(unreal.get("compatibility_tracking"))],
                "unreal_lane_split": ["5.7 baseline", "5.8 forward verification"],
                "unity": [row["version"] for row in _matrix_rows(unity.get("compatibility_tracking"))],
                "unity_proof_lane": [str(unity.get("compatibility_tracking", {}).get("pinned_editor") or "")],
                "unity_example_project_version": [
                    str(unity.get("compatibility_tracking", {}).get("example_project_version") or "")
                ],
                "unity_installed": [str(row.get("version") or "") for row in unity_installs],
                "unity_linux_docker_planned": unity_linux_docker_plan,
                "unity_mac_planned": [
                    str(command)
                    for target in unity_native_targets
                    if str(target.get("target") or "") == "mac"
                    for command in (target.get("commands") if isinstance(target.get("commands"), list) else [])
                ] or ["cesium-plugin-lanes --dry-run --lanes unity-host-mac"],
                "godot_windows": [row["version"] for row in _matrix_rows(godot_windows.get("compatibility_tracking"))],
                "godot_linux": [row["version"] for row in _matrix_rows(godot_linux.get("compatibility_tracking"))],
                "godot_mac_planned": ["cesium-plugin-lanes --dry-run --lanes godot-host-mac"],
                "unreal_linux": [row["engine_version"] for row in _matrix_rows(unreal_linux)],
                "unreal_linux_lane_split": [
                    f"{unreal_linux.get('lane_split', {}).get('baseline_version', '5.7')} baseline",
                    f"{unreal_linux.get('lane_split', {}).get('forward_version', '5.8')} forward verification",
                ],
            },
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Engine Matrix",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- lane_count: `{payload['lane_count']}`",
        "",
        str(payload["note"]),
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Packet Graph", ""])
    for packet in [
        "cesium-unity-native-matrix",
        "cesium-execution-audit",
        "cesium-planned-routes",
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
    lines.extend(["", "## Gaps", ""])
    if payload.get("gaps"):
        for gap in payload["gaps"]:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "## Lane Table", ""])
    lines.append("| Lane | Engine | Target | Evidence | Status | Versions |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for lane in payload["lanes"]:
        versions = ", ".join(lane["versions"]) if lane["versions"] else "none"
        lines.append(
            f"| {lane['lane']} | {lane['engine']} | {lane.get('native_target') or 'default'} | {lane['evidence_tier']} | {lane['status']} | {versions} |"
        )
    lines.extend(["", "## Summary", ""])
    lines.append(f"- verified_lane_count: `{payload['summary']['verified_lane_count']}`")
    lines.append(f"- planned_lane_count: `{payload['summary']['planned_lane_count']}`")
    lines.append(f"- evidence_count: `{payload['summary']['evidence_count']}`")
    for engine, versions in payload["summary"]["version_coverage"].items():
        joined = ", ".join(str(version) for version in versions) or "none"
        lines.append(f"- {engine}: `{joined}`")
    lines.extend(["", "## Build Plans", ""])
    for lane in payload["lanes"]:
        lines.append(f"### {lane['lane']}")
        lines.append("")
        for command in lane["build_plan"]:
            lines.append(f"- `{command}`")
        lines.append("")
    lines.extend(["", "## Next Proof Runs", ""])
    for run in payload["summary"].get("next_proof_runs", []):
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
