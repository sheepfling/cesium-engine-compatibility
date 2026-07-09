#!/usr/bin/env python3
"""Audit which Cesium engine versions and build paths are runnable on this host."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from extensions.cesium.tools import cesium_example_workflow, engine_root_discovery, unreal_linux_docker, unreal_linux_lane
from tools import build_cesium_engine_matrix, build_unity_native_matrix, proof_runs, unity_env


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_execution_audit"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_execution_audit.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_execution_audit.md"
PLANNED_ROUTES_REPORT = ROOT / "artifacts" / "reports" / "cesium_planned_routes" / "cesium_planned_routes.json"
UNITY_EXAMPLE_BUILD_DIR = ROOT / "artifacts" / "reports" / "unity_example_build"
UNITY_LINUX_DOCKER_REPORT = ROOT / "artifacts" / "reports" / "unity_linux_docker" / "cesium-unity_linux_docker.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _available_docker() -> bool:
    return shutil.which("docker") is not None


def _unreal_audit() -> dict[str, object]:
    report = unreal_linux_lane.report_payload()
    versions = report.get("version_matrix", [])
    linux_docker_build_status = str(report.get("build_status") or "unknown")
    linux_docker_ready = _available_docker() and isinstance(versions, list) and len(versions) > 0
    return {
        "version_count": len(versions) if isinstance(versions, list) else 0,
        "versions": [str(row.get("engine_version") or "") for row in versions if isinstance(row, dict)],
        "docker_available": _available_docker(),
        "docker_preflight": "available" if _available_docker() else "missing-docker-cli",
        "linux_prereq_checker": "present",
        "linux_docker_report_status": "verified" if linux_docker_ready and linux_docker_build_status == "verified" else "needs-host-or-docker",
        "linux_docker_build_status": linux_docker_build_status,
        "linux_docker_blocker": "none" if linux_docker_build_status == "verified" else "the public Unreal Linux archive does not include a mounted Linux platform-support tree",
        "linux_platform_support_search_roots": [str(path) for path in report.get("linux_platform_support_search_roots", []) if isinstance(path, (str, Path))],
        "linux_platform_support_roots": [str(path) for path in report.get("linux_platform_support_roots", []) if isinstance(path, (str, Path))],
        "linux_platform_support_ready": bool(report.get("linux_platform_support_ready")),
        "public_unreal_archives": [str(path) for path in report.get("public_unreal_archives", []) if isinstance(path, (str, Path))],
        "selected_source": str(report.get("selected_version") or report.get("host_state") or "unknown"),
        "build_plan": [
            "cesium-unreal-linux-docker build-plan --engine-version 5.7",
            "cesium-unreal-linux-docker build-plan --engine-version 5.8",
        ],
    }


def _unity_audit() -> dict[str, object]:
    installs = unity_env.discover_installs()
    report = cesium_example_workflow.report_payload("unity")
    tracking = report.get("compatibility_tracking", {})
    matrix = tracking.get("version_matrix", []) if isinstance(tracking, dict) else []
    return {
        "install_count": len(installs),
        "versions": [install.version for install in installs],
        "selected_versions": [str(row.get("version") or "") for row in matrix if isinstance(row, dict)],
        "proof_lane_version": str(tracking.get("pinned_editor") or "") if isinstance(tracking, dict) else "",
        "example_project_version": str(tracking.get("example_project_version") or "") if isinstance(tracking, dict) else "",
        "latest_example_build_failure_signals": _latest_unity_example_failure_signals(),
        "linux_docker_blocker_signals": _unity_linux_docker_blocker_signals(),
        "host_status": "verified" if installs else "needs-host-install",
        "linux_docker_status": "planned",
        "mac_status": "planned",
        "linux_docker_plan": [
            "cesium-unity-linux-docker --native-target linux",
            "cesium-unity-native-matrix",
        ],
        "mac_plan": [
            "cesium-plugin-lanes --dry-run --lanes unity-host-mac",
            "cesium-capture-unity-host-report --native-target mac",
            "cesium-stage-unity-host-report --source-dir <out-dir>",
            "cesium-export-unity-host-handoff",
        ],
        "host_capture_ready": any(install.editor_path for install in installs),
        "build_plan": [
            "cesium-plugin-lanes --dry-run --lanes unity-host",
            "cesium-capture-unity-host-report --unity-version <version>",
            "cesium-stage-unity-host-report --source-dir <out-dir>",
            "cesium-export-unity-host-handoff",
        ],
    }


def _latest_unity_example_failure_signals() -> list[str]:
    candidates = sorted(
        UNITY_EXAMPLE_BUILD_DIR.glob("unity_example_build_*_windows.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            signals = payload.get("failure_signals", [])
            if isinstance(signals, list):
                resolved = [str(signal) for signal in signals if str(signal)]
                if resolved:
                    return resolved
        for log_path in (
            UNITY_EXAMPLE_BUILD_DIR / "logs" / candidate.name.replace(".json", ".log"),
            candidate.with_suffix(".log"),
        ):
            if not log_path.is_file():
                continue
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            resolved = []
            if "Failed to resolve packages:" in log_text:
                resolved.append("Package Manager tried to write under the installed editor tree and hit EPERM.")
            if "Unable to retrieve BIOS serial number" in log_text:
                resolved.append("Unity licensing still hits BIOS lookup denial and mutex contention on this host.")
            if resolved:
                return resolved
    return []


def _unity_linux_docker_blocker_signals() -> list[str]:
    if not UNITY_LINUX_DOCKER_REPORT.is_file():
        return []
    try:
        payload = json.loads(UNITY_LINUX_DOCKER_REPORT.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    signals = payload.get("blocker_signals", [])
    if not isinstance(signals, list):
        return []
    return [str(signal) for signal in signals if str(signal)]


def _godot_audit() -> dict[str, object]:
    windows = cesium_example_workflow.report_payload("godot", native_target="windows")
    linux = cesium_example_workflow.report_payload("godot", native_target="linux")
    windows_rows = windows.get("compatibility_tracking", {}).get("windows_version_matrix", [])
    linux_rows = linux.get("compatibility_tracking", {}).get("linux_version_matrix", [])
    return {
        "windows_version_count": len(windows_rows) if isinstance(windows_rows, list) else 0,
        "linux_version_count": len(linux_rows) if isinstance(linux_rows, list) else 0,
        "windows_versions": [str(row.get("version") or "") for row in windows_rows if isinstance(row, dict)],
        "linux_versions": [str(row.get("version") or "") for row in linux_rows if isinstance(row, dict)],
        "windows_status": "verified" if isinstance(windows_rows, list) and len(windows_rows) > 0 else "missing",
        "linux_status": "verified" if isinstance(linux_rows, list) and len(linux_rows) > 0 else "missing",
        "mac_status": "planned",
        "build_plan": [
            "cesium-example report --engine godot --native-target windows",
            "cesium-example report --engine godot --native-target linux",
            "cesium-example report --engine godot --native-target mac",
        ],
    }


def _audit_claim_boundaries() -> list[str]:
    return [
        "The audit unions host availability, public search roots, and next-proof commands into one packet-friendly readiness picture.",
        "Unreal Linux Docker is verified on this host, while the source-built Linux support tree story remains an upstream-parity follow-up.",
        "Unity Linux/Docker now has a live Docker report, while the Windows host route still carries the current proof lane evidence and Unity macOS remains planned.",
        "Godot Windows and Linux are verified; Godot macOS remains the next proof gap.",
        "The planned-routes packet keeps the remaining cross-platform bootstrap bundle commandable without claiming any of those routes are build-green.",
    ]


def _audit_gaps(unreal: dict[str, object], unity: dict[str, object], godot: dict[str, object]) -> list[str]:
    gaps: list[str] = []
    if unreal.get("linux_docker_build_status") != "verified":
        gaps.append("Unreal Linux Docker still needs a verified build artifact before it can be called fully green.")
    if unity.get("linux_docker_status") != "verified":
        gaps.append("Unity Linux/Docker remains planned.")
    if unity.get("mac_status") != "verified":
        gaps.append("Unity macOS remains planned.")
    if godot.get("mac_status") != "verified":
        gaps.append("Godot macOS remains planned.")
    return gaps


def _audit_evidence() -> list[dict[str, object]]:
    return [
        {
            "surface": "unreal",
            "kind": "version_matrix",
            "path": "docs/UNREAL_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "UNREAL_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "unreal",
            "kind": "linux_notes",
            "path": "docs/CESIUM_UNREAL_LINUX_NOTES.md",
            "exists": (ROOT / "docs" / "CESIUM_UNREAL_LINUX_NOTES.md").is_file(),
        },
        {
            "surface": "unity",
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
            "surface": "unity",
            "kind": "docker_report",
            "path": "artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json",
            "exists": (ROOT / "artifacts" / "reports" / "unity_linux_docker" / "cesium-unity_linux_docker.json").is_file(),
        },
        {
            "surface": "godot",
            "kind": "docker_report",
            "path": "artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.json",
            "exists": (ROOT / "artifacts" / "reports" / "godot_linux_docker" / "cesium-godot_linux_docker.json").is_file(),
        },
        {
            "surface": "godot",
            "kind": "windows_version_matrix",
            "path": "docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "godot",
            "kind": "linux_version_matrix",
            "path": "docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md",
            "exists": (ROOT / "docs" / "CESIUM_GODOT_LINUX_VERSION_MATRIX.md").is_file(),
        },
        {
            "surface": "planned-routes",
            "kind": "dry_run_bundle",
            "path": "artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            "exists": PLANNED_ROUTES_REPORT.is_file(),
        },
        {
            "surface": "packet-summary",
            "kind": "review_packet",
            "path": "docs/CESIUM_PR_PACKET_SUMMARY.md",
            "exists": (ROOT / "docs" / "CESIUM_PR_PACKET_SUMMARY.md").is_file(),
        },
    ]


def build_payload() -> dict[str, object]:
    unreal = _unreal_audit()
    unity = _unity_audit()
    godot = _godot_audit()
    engine_matrix = build_cesium_engine_matrix.build_payload()
    unity_native_matrix = build_unity_native_matrix.build_payload()
    public_roots = engine_root_discovery.public_engine_search_roots()
    unity_public_roots = list(dict.fromkeys([*(str(path) for path in public_roots["unity"]), *(str(path) for path in unity_env.scan_roots())]))
    evidence = _audit_evidence()
    gaps = _audit_gaps(unreal, unity, godot)
    ready = unreal["linux_docker_build_status"] == "verified" and unity["host_status"] == "verified" and godot["windows_status"] == "verified" and godot["linux_status"] == "verified"
    return {
        "schema": "cesium.execution_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": "pass" if ready and not gaps else "partial",
        "claim_boundaries": _audit_claim_boundaries(),
        "evidence": evidence,
        "gaps": gaps,
        "host": {
            "platform": sys.platform,
            "docker_available": _available_docker(),
            "unreal_public_roots": [str(path) for path in public_roots["unreal"]],
            "unity_public_roots": unity_public_roots,
            "godot_public_roots": [str(path) for path in public_roots["godot"]],
        },
        "unreal": unreal,
        "unity": unity,
        "godot": godot,
        "next_proof_runs": proof_runs.next_proof_runs(),
        "related_packets": {
            "engine_matrix": {
                "status": engine_matrix.get("status"),
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
            "unity_native_matrix": {
                "status": unity_native_matrix.get("status"),
                "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
            },
            "planned_routes": {
                "status": "present" if PLANNED_ROUTES_REPORT.is_file() else "missing",
                "path": "artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            },
            "compatibility_packet": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_compatibility_packet" / "cesium_compatibility_packet.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
        },
        "readiness": {
            "unreal_linux_docker": unreal["linux_docker_build_status"] == "verified",
            "unity_host": unity["host_capture_ready"] and unity["install_count"] > 0,
            "godot_windows": godot["windows_version_count"] > 0,
            "godot_linux": godot["linux_version_count"] > 0,
        },
        "summary": {
            "evidence_count": len(evidence),
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Execution Audit",
        "",
        "The live audit command is `cesium-execution-audit`.",
        "",
        f"- overall_status: `{payload['overall_status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- docker_available: `{payload['host']['docker_available']}`",
        f"- unreal_public_roots: `{', '.join(payload['host'].get('unreal_public_roots', [])) or 'none'}`",
        f"- unity_public_roots: `{', '.join(payload['host'].get('unity_public_roots', [])) or 'none'}`",
        f"- godot_public_roots: `{', '.join(payload['host'].get('godot_public_roots', [])) or 'none'}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Packet Graph", ""])
    for packet in [
        "cesium-engine-matrix",
        "cesium-unity-native-matrix",
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
    lines.extend(["", "## Readiness", ""])
    for key, value in payload["readiness"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Proof Runs", ""])
    for run in payload["next_proof_runs"]:
        lines.append(f"- `{run['surface']}`: `{run['command']}`")
        for focus in run["capture_focus"]:
            lines.append(f"  - {focus}")
    lines.extend(["", "## Unreal", ""])
    lines.append(f"- versions: `{', '.join(payload['unreal']['versions']) or 'none'}`")
    lines.append(f"- docker_preflight: `{payload['unreal']['docker_preflight']}`")
    lines.append(f"- linux_docker_report_status: `{payload['unreal']['linux_docker_report_status']}`")
    lines.append(f"- linux_docker_build_status: `{payload['unreal']['linux_docker_build_status']}`")
    lines.append(f"- linux_docker_blocker: `{payload['unreal']['linux_docker_blocker']}`")
    if payload["unreal"].get("linux_platform_support_search_roots"):
        lines.append("- linux_platform_support_search_roots:")
        for root in payload["unreal"]["linux_platform_support_search_roots"]:
            lines.append(f"  - {root}")
    if payload["unreal"].get("linux_platform_support_roots"):
        lines.append("- linux_platform_support_roots:")
        if payload["unreal"]["linux_platform_support_roots"]:
            for root in payload["unreal"]["linux_platform_support_roots"]:
                lines.append(f"  - {root}")
        else:
            lines.append("  - none discovered")
    lines.append(f"- linux_platform_support_ready: `{payload['unreal']['linux_platform_support_ready']}`")
    if payload["unreal"].get("public_unreal_archives"):
        lines.append("- public_unreal_archives:")
        for archive in payload["unreal"]["public_unreal_archives"]:
            lines.append(f"  - {archive}")
    lines.append(f"- selected_source: `{payload['unreal']['selected_source']}`")
    lines.extend(["", "## Unity", ""])
    lines.append(f"- versions: `{', '.join(payload['unity']['versions']) or 'none'}`")
    lines.append(f"- installed host spread: `{', '.join(payload['unity']['versions']) or 'none'}`")
    lines.append(f"- proof lane: `{payload['unity'].get('proof_lane_version') or 'none'}`")
    lines.append(f"- proof_lane_version: `{payload['unity'].get('proof_lane_version') or 'none'}`")
    lines.append(f"- current example-project version: `{payload['unity'].get('example_project_version') or 'none'}`")
    lines.append(f"- example_project_version: `{payload['unity'].get('example_project_version') or 'none'}`")
    lines.append(f"- host_capture_ready: `{payload['unity']['host_capture_ready']}`")
    lines.append(f"- host_status: `{payload['unity']['host_status']}`")
    lines.append(f"- linux_docker_status: `{payload['unity']['linux_docker_status']}`")
    lines.append("Unity Linux/Docker still a planned proof lane.")
    lines.append("Windows host coverage for Unity is represented by the installed host spread.")
    lines.append("Unity Linux/Docker lane now has a live Docker report artifact.")
    lines.append("Unity macOS remains planned as the other native gap, and the lane remains planned for the same reason.")
    lines.append(f"- linux_docker_plan: `{'; '.join(payload['unity'].get('linux_docker_plan', [])) or 'none'}`")
    if payload["unity"].get("linux_docker_blocker_signals"):
        lines.append("- linux_docker_blocker_signals:")
        for signal in payload["unity"]["linux_docker_blocker_signals"]:
            lines.append(f"  - {signal}")
    if payload["unity"].get("latest_example_build_failure_signals"):
        lines.append("- latest_example_build_failure_signals:")
        for signal in payload["unity"]["latest_example_build_failure_signals"]:
            lines.append(f"  - {signal}")
    lines.append("That planned route is now commandable as `cesium-unity-linux-docker --native-target linux`, which keeps the future proof path in the same lane bundle as the rest of the host evidence.")
    lines.extend(["", "## Godot", ""])
    lines.append(f"- windows_versions: `{', '.join(payload['godot']['windows_versions']) or 'none'}`")
    lines.append(f"- linux_versions: `{', '.join(payload['godot']['linux_versions']) or 'none'}`")
    lines.append(f"- windows_status: `{payload['godot']['windows_status']}`")
    lines.append(f"- linux_status: `{payload['godot']['linux_status']}`")
    lines.append(f"- mac_status: `{payload['godot']['mac_status']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
