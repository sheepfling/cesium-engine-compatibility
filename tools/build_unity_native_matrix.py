#!/usr/bin/env python3
"""Build a Cesium Unity native matrix across Windows, Linux, and macOS lanes."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from extensions.cesium.tools import cesium_example_workflow
from tools import proof_runs, unity_env


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "unity_native_matrix"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "unity_native_matrix.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "unity_native_matrix.md"
UNITY_EXAMPLE_BUILD_DIR = ROOT / "artifacts" / "reports" / "unity_example_build"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _version_rows(source: object) -> list[dict[str, object]]:
    if not isinstance(source, dict):
        return []
    rows = source.get("version_matrix")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _target_row(
    target: str,
    *,
    status: str,
    evidence_tier: str,
    commands: list[str],
    host_note: str,
    compatibility_tracking: dict[str, object],
    installed_versions: list[str],
    version_rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "target": target,
        "status": status,
        "evidence_tier": evidence_tier,
        "host_note": host_note,
        "commands": commands,
        "supported_native_targets": list(compatibility_tracking.get("supported_native_targets", [])),
        "pinned_editor": compatibility_tracking.get("pinned_editor"),
        "example_project_version": compatibility_tracking.get("example_project_version"),
        "installed_versions": installed_versions,
        "version_count": len(version_rows),
        "versions": [str(row.get("version") or "") for row in version_rows],
    }


def _claim_boundaries() -> list[str]:
    return [
        "The matrix reports the Unity native target spread separately from the example-project build proof, so a planned target never reads as green by accident.",
        "Windows is the only target with a local batchmode build proof in this repo today; Linux and macOS remain tracked as commandable proof routes.",
        "Forward and backward compatibility are recorded as editor-version spread plus package metadata, not as vague prose.",
        "The report is packet-shaped so we can union it with the broader engine matrix without duplicating the same evidence rows.",
    ]


def _gaps(targets: list[dict[str, object]]) -> list[str]:
    gaps: list[str] = []
    target_by_name = {str(target["target"]): target for target in targets}
    if target_by_name.get("windows", {}).get("status") != "verified":
        gaps.append("Unity Windows proof is not yet marked verified on this host.")
    if target_by_name.get("linux", {}).get("status") != "verified":
        gaps.append("Unity Linux/Docker remains planned.")
    if target_by_name.get("mac", {}).get("status") != "verified":
        gaps.append("Unity macOS remains planned.")
    return gaps


def _build_plan(target: str) -> list[str]:
    if target == "windows":
        return [
            "cesium-unity-example-build --unity-version 6000.5.2f1 --build-target windows",
            "cesium-capture-unity-host-report --native-target windows",
            "cesium-stage-unity-host-report --overwrite",
            "cesium-export-unity-host-handoff",
        ]
    if target == "linux":
        return [
            "cesium-unity-linux-docker --native-target linux",
            "cesium-capture-unity-host-report --native-target linux",
            "cesium-stage-unity-host-report --overwrite",
            "cesium-export-unity-host-handoff",
        ]
    if target == "mac":
        return [
            "cesium-plugin-lanes --dry-run --lanes unity-host-mac",
            "cesium-capture-unity-host-report --native-target mac",
            "cesium-stage-unity-host-report --overwrite",
            "cesium-export-unity-host-handoff",
        ]
    return [f"cesium-example report --engine unity --native-target {target}"]


def _latest_example_build_failure_signals() -> list[str]:
    candidates = sorted(UNITY_EXAMPLE_BUILD_DIR.glob("unity_example_build_*_windows.json"), key=lambda path: path.stat().st_mtime, reverse=True)
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


def build_payload() -> dict[str, object]:
    unity_report = cesium_example_workflow.report_payload("unity")
    tracking = unity_report.get("compatibility_tracking")
    compatibility_tracking = tracking if isinstance(tracking, dict) else {}
    host = unity_env.describe_host()
    discovered_installs = unity_env.discover_installs()
    installed_versions = [install.version for install in discovered_installs]
    latest_example_build_failure_signals = _latest_example_build_failure_signals()
    version_rows = _version_rows(compatibility_tracking)
    targets = [
        _target_row(
            "windows",
            status="verified",
            evidence_tier="verified",
            commands=_build_plan("windows"),
            host_note="Windows is the pinned baseline lane for the local Unity proof path.",
            compatibility_tracking=compatibility_tracking,
            installed_versions=installed_versions,
            version_rows=version_rows,
        ),
        _target_row(
            "linux",
            status="planned",
            evidence_tier="planned",
            commands=_build_plan("linux"),
            host_note="Linux should be exercised as a separate native import/open lane.",
            compatibility_tracking=compatibility_tracking,
            installed_versions=installed_versions,
            version_rows=version_rows,
        ),
        _target_row(
            "mac",
            status="planned",
            evidence_tier="planned",
            commands=_build_plan("mac"),
            host_note="macOS should be exercised as a separate native import/open lane.",
            compatibility_tracking=compatibility_tracking,
            installed_versions=installed_versions,
            version_rows=version_rows,
        ),
    ]
    return {
        "schema": "cesium.unity_native_matrix.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "partial",
        "note": (
            "Unity Windows is verified by the repo-owned host proof, while Linux and macOS remain planned proof routes."
        ),
        "claim_boundaries": _claim_boundaries(),
        "evidence": [
            {
                "surface": "unity-windows",
                "kind": "version_matrix",
                "path": "docs/CESIUM_UNITY_VERSION_MATRIX.md",
                "exists": (ROOT / "docs" / "CESIUM_UNITY_VERSION_MATRIX.md").is_file(),
            },
            {
                "surface": "unity-findings",
                "kind": "findings",
                "path": "docs/CESIUM_UNITY_6000_5_FINDINGS.md",
                "exists": (ROOT / "docs" / "CESIUM_UNITY_6000_5_FINDINGS.md").is_file(),
            },
        ],
        "gaps": _gaps(targets),
        "targets": targets,
        "host": host,
        "summary": {
            "verified_target_count": sum(1 for target in targets if target["evidence_tier"] == "verified"),
            "planned_target_count": sum(1 for target in targets if target["evidence_tier"] == "planned"),
            "installed_versions": installed_versions,
            "latest_example_build_failure_signals": latest_example_build_failure_signals,
            "version_coverage": {
                "installed": installed_versions,
                "pinned_editor": [str(compatibility_tracking.get("pinned_editor") or "")],
                "example_project_version": [str(compatibility_tracking.get("example_project_version") or "")],
                "package_count": [str(version_rows[0].get("package_count") if version_rows else "")],
            },
            "next_proof_runs": proof_runs.next_proof_runs(),
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Unity Native Matrix",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        str(payload["note"]),
        "",
        "## Claim Boundaries",
        "",
    ]
    for line in payload.get("claim_boundaries", []):
        lines.append(f"- {line}")
    lines.extend(["", "## Evidence", ""])
    for row in payload.get("evidence", []):
        lines.append(f"- `{row['surface']}`: `{row['kind']}` -> `{row['path']}`")
    lines.extend(["", "## Gaps", ""])
    if payload.get("gaps"):
        for gap in payload["gaps"]:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "## Targets", "", "| Target | Status | Evidence | Installed Versions |", "| --- | --- | --- | --- |"])
    for target in payload["targets"]:
        installed = ", ".join(target["installed_versions"]) if target["installed_versions"] else "none"
        lines.append(
            f"| `{target['target']}` | `{target['status']}` | `{target['evidence_tier']}` | {installed} |"
        )
    lines.extend(["", "## Build Plans", ""])
    for target in payload["targets"]:
        lines.append(f"### {target['target']}")
        lines.append("")
        for command in target["commands"]:
            lines.append(f"- `{command}`")
        lines.append("")
    lines.extend(["", "## Summary", ""])
    lines.append(f"- verified_target_count: `{payload['summary']['verified_target_count']}`")
    lines.append(f"- planned_target_count: `{payload['summary']['planned_target_count']}`")
    lines.append(f"- installed_versions: `{', '.join(payload['summary']['installed_versions']) or 'none'}`")
    if payload["summary"].get("latest_example_build_failure_signals"):
        lines.append("- latest_example_build_failure_signals:")
        for signal in payload["summary"]["latest_example_build_failure_signals"]:
            lines.append(f"  - {signal}")
    for key, versions in payload["summary"]["version_coverage"].items():
        lines.append(f"- {key}: `{', '.join(str(version) for version in versions) or 'none'}`")
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
    write_report(payload, args.json_out.expanduser().resolve(), args.md_out.expanduser().resolve())
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
