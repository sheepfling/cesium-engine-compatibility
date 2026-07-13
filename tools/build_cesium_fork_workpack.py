#!/usr/bin/env python3
"""Build a standard fork workpack for Cesium engine compatibility work."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import subprocess
from pathlib import Path
from typing import Any

from extensions.cesium.tools import prepare_cesium_source_route
from tools import build_cesium_compatibility_packet, build_cesium_engine_matrix, build_cesium_visual_proof


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_fork_workpack"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_fork_workpack.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_fork_workpack.md"


@dataclass(frozen=True)
class HostTarget:
    host: str
    architecture: str
    status: str
    green_commands: tuple[str, ...]
    proof_docs: tuple[str, ...]
    report_path: str
    notes: str


def _git_output(path: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _workspace_revision() -> dict[str, Any]:
    return {
        "root": str(ROOT),
        "branch": _git_output(ROOT, ["branch", "--show-current"]),
        "head_commit": _git_output(ROOT, ["rev-parse", "HEAD"]),
        "dirty": bool(_git_output(ROOT, ["status", "--short"])),
    }


def _source_route_repos() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    for spec in prepare_cesium_source_route.default_repo_specs():
        inspected = prepare_cesium_source_route.inspect_repo(spec)
        repos.append(
            {
                "key": inspected.get("key"),
                "label": inspected.get("label"),
                "path": inspected.get("path"),
                "remote_url": inspected.get("remote_url") or spec.remote_url,
                "target_branch": inspected.get("resolved_target_branch") or inspected.get("target_branch") or spec.target_branch,
                "head_commit": inspected.get("head_commit"),
                "target_commit": inspected.get("target_commit"),
                "official": inspected.get("official"),
                "status": "present" if inspected.get("is_git_checkout") else "missing",
            }
        )
    return repos


def _engine_hosts() -> dict[str, list[HostTarget]]:
    visual_root = str((ROOT / "artifacts" / "reports" / "cesium_visual_proof").relative_to(ROOT))
    return {
        "unreal": [
            HostTarget(
                host="windows",
                architecture="x86_64",
                status="verified",
                green_commands=(
                    "cesium-example report --engine unreal",
                    "cesium-example doctor --engine unreal",
                ),
                proof_docs=(
                    "docs/UNREAL_VERSION_MATRIX.md",
                    "docs/CESIUM_UNREAL_LINUX_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unreal/windows-x86_64.json",
                notes="Keep the Windows proof lane tied to the selected Unreal branch and the repo-owned example project.",
            ),
            HostTarget(
                host="linux",
                architecture="x86_64",
                status="verified",
                green_commands=(
                    "cesium-unreal-linux-docker build-plan --engine-version 5.7",
                    "cesium-unreal-linux-docker build --engine-version 5.8",
                ),
                proof_docs=(
                    "docs/UNREAL_VERSION_MATRIX.md",
                    "docs/CESIUM_UNREAL_LINUX_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unreal/linux-x86_64.json",
                notes="Use the Linux Docker lane for the repeatable host/toolchain proof and keep the platform-support tree explicit.",
            ),
            HostTarget(
                host="mac",
                architecture="x86_64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes unreal-host-mac",
                    "cesium-example doctor --engine unreal --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_PR_PACKET_SUMMARY.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unreal/mac-x86_64.json",
                notes="Mac stays split from Windows/Linux and should record the exact host architecture and camera-proof work separately.",
            ),
            HostTarget(
                host="mac",
                architecture="arm64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes unreal-host-mac",
                    "cesium-example doctor --engine unreal --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_PR_PACKET_SUMMARY.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unreal/mac-arm64.json",
                notes="Use a separate arm64 packet so the same branch can be proven on both Mac architectures.",
            ),
        ],
        "unity": [
            HostTarget(
                host="windows",
                architecture="x86_64",
                status="verified",
                green_commands=(
                    "cesium-capture-unity-host-report --native-target windows",
                    "cesium-stage-unity-host-report",
                    "cesium-export-unity-host-handoff",
                ),
                proof_docs=(
                    "docs/CESIUM_UNITY_VERSION_MATRIX.md",
                    "docs/CESIUM_UNITY_6000_5_FINDINGS.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unity/windows-x86_64.json",
                notes="Windows is the pinned proof anchor and should keep the selected editor version visible in every packet.",
            ),
            HostTarget(
                host="linux",
                architecture="x86_64",
                status="planned",
                green_commands=(
                    "cesium-unity-linux-docker --native-target linux",
                    "cesium-plugin-lanes --dry-run --lanes unity-host-linux-docker",
                ),
                proof_docs=(
                    "docs/CESIUM_UNITY_VERSION_MATRIX.md",
                    "docs/CESIUM_UNITY_6000_5_FINDINGS.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unity/linux-x86_64.json",
                notes="Linux Docker needs to keep the installed editor spread and package revision visible in the same packet.",
            ),
            HostTarget(
                host="mac",
                architecture="x86_64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes unity-host-mac",
                    "cesium-capture-unity-host-report --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_PR_PACKET_SUMMARY.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unity/mac-x86_64.json",
                notes="Mac x86_64 needs the same capture/report shape as the other lanes, but with separate mac-specific proof notes.",
            ),
            HostTarget(
                host="mac",
                architecture="arm64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes unity-host-mac",
                    "cesium-capture-unity-host-report --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_PR_PACKET_SUMMARY.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/unity/mac-arm64.json",
                notes="Mac arm64 should be tracked as a separate host architecture, not folded into a single Mac bucket.",
            ),
        ],
        "godot": [
            HostTarget(
                host="windows",
                architecture="x86_64",
                status="verified",
                green_commands=(
                    "cesium-example report --engine godot --native-target windows",
                    "cesium-example doctor --engine godot --native-target windows",
                ),
                proof_docs=(
                    "docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md",
                    "docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/godot/windows-x86_64.json",
                notes="Windows remains the baseline Godot lane and should keep the exact editor version family visible.",
            ),
            HostTarget(
                host="linux",
                architecture="x86_64",
                status="verified",
                green_commands=(
                    "cesium-example report --engine godot --native-target linux",
                    "cesium-example doctor --engine godot --native-target linux",
                ),
                proof_docs=(
                    "docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md",
                    "docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/godot/linux-x86_64.json",
                notes="Linux should remain a separate native import/open lane and can use Docker as the repeatable proxy when needed.",
            ),
            HostTarget(
                host="mac",
                architecture="x86_64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
                    "cesium-example report --engine godot --native-target mac",
                    "cesium-example doctor --engine godot --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/godot/mac-x86_64.json",
                notes="Mac x86_64 should keep camera, addon, and editor revision evidence separated from Windows and Linux.",
            ),
            HostTarget(
                host="mac",
                architecture="arm64",
                status="planned",
                green_commands=(
                    "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
                    "cesium-example report --engine godot --native-target mac",
                    "cesium-example doctor --engine godot --native-target mac",
                ),
                proof_docs=(
                    "extensions/cesium/docs/CESIUM_MACOS_SILICON_BUILD_NOTES.md",
                    "docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md",
                ),
                report_path="artifacts/reports/cesium_fork_workpack/godot/mac-arm64.json",
                notes="Mac arm64 should be tracked separately so the same lane can prove both Apple architectures cleanly.",
            ),
        ],
    }


def _engine_workpack(engine: str, *, matrix: dict[str, Any], visual_proof: dict[str, Any], workspace: dict[str, Any], source_repos: list[dict[str, Any]]) -> dict[str, Any]:
    host_targets = _engine_hosts()[engine]
    version_coverage = matrix.get("summary", {}).get("version_coverage", {}) if isinstance(matrix.get("summary"), dict) else {}
    proof_location = visual_proof.get("summary", {}).get("capture_root") if isinstance(visual_proof.get("summary"), dict) else None
    fork_target = {
        "unreal": "CesiumGS/cesium-unreal",
        "unity": "CesiumGS/cesium-unity",
        "godot": "Battle-Road-Labs/3D-Tiles-For-Godot",
    }[engine]
    docs = {
        "unreal": ["docs/UNREAL_VERSION_MATRIX.md", "docs/CESIUM_UNREAL_LINUX_NOTES.md"],
        "unity": ["docs/CESIUM_UNITY_VERSION_MATRIX.md", "docs/CESIUM_UNITY_6000_5_FINDINGS.md"],
        "godot": ["docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md", "docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md", "docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md"],
    }[engine]
    return {
        "engine": engine,
        "fork_target": fork_target,
        "workspace_revision": workspace,
        "cesium_source_revision": workspace.get("head_commit"),
        "source_route_root": "external/cesium",
        "source_route_repos": source_repos,
        "version_coverage": version_coverage,
        "host_targets": [
            {
                "host": target.host,
                "architecture": target.architecture,
                "status": target.status,
                "green_commands": list(target.green_commands),
                "proof_docs": list(target.proof_docs),
                "report_path": target.report_path,
                "notes": target.notes,
            }
            for target in host_targets
        ],
        "report_locations": {
            "workpack": f"artifacts/reports/cesium_fork_workpack/{engine}/workpack.json",
            "engine_matrix": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            "compatibility_packet": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            "visual_proof_root": proof_location,
        },
        "docs": docs,
        "next_steps": [
            f"Keep {engine} work items in the per-host report path contract above.",
            "Record the Cesium workspace commit before branching fork work so the exact source version stays visible.",
            "Use the visual-proof packet when screenshot or camera-angle evidence is needed.",
        ],
    }


def build_payload() -> dict[str, object]:
    workspace = _workspace_revision()
    source_repos = _source_route_repos()
    matrix = build_cesium_engine_matrix.build_payload()
    compatibility = build_cesium_compatibility_packet.build_payload()
    visual_proof = build_cesium_visual_proof.build_payload()
    engines = [
        _engine_workpack("unreal", matrix=matrix, visual_proof=visual_proof, workspace=workspace, source_repos=source_repos),
        _engine_workpack("unity", matrix=matrix, visual_proof=visual_proof, workspace=workspace, source_repos=source_repos),
        _engine_workpack("godot", matrix=matrix, visual_proof=visual_proof, workspace=workspace, source_repos=source_repos),
    ]
    planned = [item for engine in engines for item in engine["host_targets"] if item["status"] == "planned"]
    verified = [item for engine in engines for item in engine["host_targets"] if item["status"] == "verified"]
    return {
        "schema": "cesium.fork_workpack.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "partial" if planned else "complete",
        "claim_boundaries": [
            "This is the standard reporting surface for Cesium fork work across Unreal, Unity, and Godot.",
            "The packet records the exact Cesium workspace revision so the source version is always visible in the report header.",
            "Each engine gets one host-by-host checklist that can be extended without losing the current baseline or forward-verification lane.",
            "Planned macOS work is split by architecture so Apple Silicon and Intel stay separate when they both matter.",
        ],
        "workspace": workspace,
        "source_repos": source_repos,
        "engines": engines,
        "summary": {
            "engine_count": len(engines),
            "verified_host_rows": len(verified),
            "planned_host_rows": len(planned),
            "source_repo_count": len(source_repos),
            "visual_proof_status": visual_proof.get("status"),
            "compatibility_packet_status": compatibility.get("status"),
        },
        "related_packets": {
            "compatibility_packet": {
                "status": compatibility.get("status"),
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
            "engine_matrix": {
                "status": matrix.get("status"),
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
            "visual_proof": {
                "status": visual_proof.get("status"),
                "path": "artifacts/reports/cesium_visual_proof/cesium_visual_proof.json",
            },
        },
        "next_steps": [
            "Use the per-engine host rows as the canonical checklist for fork-specific green work.",
            "Keep the Cesium workspace commit in every fork packet so it is obvious which source version was exercised.",
            "Attach screenshots or camera-angle outputs through cesium-visual-proof when visual evidence is needed.",
        ],
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Fork Workpack",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- workspace_commit: `{payload.get('workspace', {}).get('head_commit')}`",
        f"- source_repo_count: `{payload.get('summary', {}).get('source_repo_count')}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Workspace", ""])
    workspace = payload.get("workspace", {})
    if isinstance(workspace, dict):
        lines.append(f"- root: `{workspace.get('root')}`")
        lines.append(f"- branch: `{workspace.get('branch') or 'detached'}`")
        lines.append(f"- head_commit: `{workspace.get('head_commit') or 'unknown'}`")
        lines.append(f"- dirty: `{workspace.get('dirty')}`")
    lines.extend(["", "## Source Repos", ""])
    for repo in payload.get("source_repos", []):
        lines.append(f"### {repo['label']}")
        lines.append(f"- key: `{repo['key']}`")
        lines.append(f"- path: `{repo['path']}`")
        lines.append(f"- remote_url: `{repo['remote_url']}`")
        lines.append(f"- target_branch: `{repo['target_branch']}`")
        lines.append(f"- head_commit: `{repo.get('head_commit') or 'missing'}`")
        lines.append(f"- target_commit: `{repo.get('target_commit') or 'missing'}`")
        lines.append(f"- status: `{repo['status']}`")
    lines.extend(["", "## Engine Workpacks", ""])
    for engine in payload.get("engines", []):
        lines.append(f"### {engine['engine']}")
        lines.append(f"- fork_target: `{engine['fork_target']}`")
        lines.append(f"- cesium_source_revision: `{engine['cesium_source_revision']}`")
        lines.append(f"- workpack_location: `{engine['report_locations']['workpack']}`")
        lines.append(f"- visual_proof_root: `{engine['report_locations']['visual_proof_root']}`")
        lines.append("- host_targets:")
        for host in engine.get("host_targets", []):
            lines.append(f"  - `{host['host']}` / `{host['architecture']}`: `{host['status']}`")
            lines.append(f"    report_path: `{host['report_path']}`")
            lines.append(f"    notes: {host['notes']}")
            lines.append("    green_commands:")
            for command in host.get("green_commands", []):
                lines.append(f"      - `{command}`")
            lines.append("    proof_docs:")
            for doc in host.get("proof_docs", []):
                lines.append(f"      - `{doc}`")
    lines.extend(["", "## Related Packets", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        lines.append(f"- engine_count: `{summary.get('engine_count')}`")
        lines.append(f"- verified_host_rows: `{summary.get('verified_host_rows')}`")
        lines.append(f"- planned_host_rows: `{summary.get('planned_host_rows')}`")
        lines.append(f"- source_repo_count: `{summary.get('source_repo_count')}`")
        lines.append(f"- visual_proof_status: `{summary.get('visual_proof_status')}`")
        lines.append(f"- compatibility_packet_status: `{summary.get('compatibility_packet_status')}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
