#!/usr/bin/env python3
"""Inspect and report on the repo-owned Unreal Linux lane."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import platform
import subprocess
import sys
from extensions.cesium.tools.engine_root_discovery import discover_unreal_linux_archives, public_engine_search_roots


ROOT = Path(__file__).resolve().parents[3]
SOURCE_CHECKOUT = ROOT / "external" / "cesium" / "cesium-unreal"
PROJECT_ROOT = ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample"
REPORT_DIR = ROOT / "artifacts" / "reports" / "unreal_linux_docker"
PLUGIN_MANIFEST = SOURCE_CHECKOUT / "CesiumForUnreal.uplugin"
RUNTIME_BUILD = SOURCE_CHECKOUT / "Source" / "CesiumRuntime" / "CesiumRuntime.Build.cs"
EDITOR_BUILD = SOURCE_CHECKOUT / "Source" / "CesiumEditor" / "CesiumEditor.Build.cs"
LINUX_DOC = SOURCE_CHECKOUT / "Documentation" / "developer-setup-linux.md"
LANE_DOC = ROOT / "docs" / "CESIUM_UNREAL_LINUX_NOTES.md"
LINUX_PLATFORM_SUPPORT_SEARCH_ROOTS = (
    Path(r"C:\Users\Public\Unreal") / "Engine" / "Platforms" / "Linux",
    Path(r"C:\Program Files\Epic Games") / "Engine" / "Platforms" / "Linux",
)
VERSION_MATRIX = [
    {
        "engine_version": "5.7",
        "lane_role": "current baseline",
        "focus": "Confirm source checkout, plugin packaging, and editor-open behavior against the pinned 5.7-era lane.",
    },
    {
        "engine_version": "5.8",
        "lane_role": "forward verification",
        "focus": "Confirm that Linux host/toolchain alignment still works on the newer 5.8 lane without mixing in Windows-only assumptions.",
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _git(path: Path, args: list[str]) -> str | None:
    if not (path / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "-c", "http.sslVerify=false", "-c", f"safe.directory={path}", "-C", str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _file_contains(path: Path, needles: list[str]) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    return all(needle in content for needle in needles)


def _check_path(name: str, path: Path, *, required: bool = True) -> dict[str, object]:
    if path.is_file():
        return {"name": name, "status": "ok", "detail": str(path)}
    if path.is_dir():
        return {"name": name, "status": "ok", "detail": str(path)}
    return {"name": name, "status": "fail" if required else "warn", "detail": f"missing: {path}"}


def _discover_linux_platform_support_roots() -> list[Path]:
    return [candidate for candidate in LINUX_PLATFORM_SUPPORT_SEARCH_ROOTS if candidate.is_dir()]


def _latest_report_log(prefix: str, *, engine_version: str | None = None) -> Path | None:
    logs = [path for path in REPORT_DIR.glob(f"{prefix}*.log") if path.is_file()]
    if not logs:
        return None
    if engine_version is not None:
        preferred = [path for path in logs if engine_version in path.name]
        if preferred:
            logs = preferred
    return max(logs, key=lambda path: path.stat().st_mtime)


def _build_evidence_from_log(log_path: Path | None) -> dict[str, object]:
    if log_path is None:
        return {
            "build_status": "unknown",
            "build_result": None,
            "build_log": None,
            "build_output_binary": None,
        }
    text = log_path.read_text(encoding="utf-8", errors="replace")
    result: str | None = None
    if "Result: Succeeded" in text and "ExitCode=0" in text:
        result = "succeeded"
    elif "Result: Failed" in text or "ExitCode=" in text:
        result = "failed"
    output_binary: str | None = None
    for line in text.splitlines():
        if line.startswith("Output binary: "):
            output_binary = line.removeprefix("Output binary: ").strip()
            break
    return {
        "build_status": "verified" if result == "succeeded" else ("failed" if result == "failed" else "unknown"),
        "build_result": result,
        "build_log": str(log_path),
        "build_output_binary": output_binary,
    }


def _select_version_matrix(engine_version: str | None) -> dict[str, object] | None:
    if engine_version is None:
        return None
    for row in VERSION_MATRIX:
        if row["engine_version"] == engine_version:
            return row
    return None


def report_payload(*, engine_version: str | None = None) -> dict[str, object]:
    host_system = platform.system().lower()
    host_state = "linux-host" if host_system == "linux" else "non-linux-host"
    selected_version = _select_version_matrix(engine_version)
    checks = [
        _check_path("source_checkout", SOURCE_CHECKOUT),
        _check_path("plugin_manifest", PLUGIN_MANIFEST),
        _check_path("runtime_build", RUNTIME_BUILD),
        _check_path("editor_build", EDITOR_BUILD),
        _check_path("linux_doc", LINUX_DOC),
        _check_path("lane_doc", LANE_DOC),
        _check_path("example_project", PROJECT_ROOT),
    ]
    checks.append(
        {
            "name": "linux_platform_declared",
            "status": "ok" if _file_contains(PLUGIN_MANIFEST, ["Linux"]) else "fail",
            "detail": "CesiumForUnreal.uplugin advertises Linux support",
        }
    )
    checks.append(
        {
            "name": "runtime_linux_branch",
            "status": "ok" if _file_contains(RUNTIME_BUILD, ["UnrealTargetPlatform.Linux"]) else "fail",
            "detail": "CesiumRuntime.Build.cs includes a Linux branch",
        }
    )
    checks.append(
        {
            "name": "editor_linux_branch",
            "status": "ok" if _file_contains(EDITOR_BUILD, ["UnrealTargetPlatform.Linux"]) else "fail",
            "detail": "CesiumEditor.Build.cs includes a Linux branch",
        }
    )
    linux_platform_support_roots = _discover_linux_platform_support_roots()
    build_evidence = _build_evidence_from_log(_latest_report_log("cesium_unreal_linux_build_", engine_version=engine_version))
    source_branch = _git(SOURCE_CHECKOUT, ["branch", "--show-current"])
    source_commit = _git(SOURCE_CHECKOUT, ["rev-parse", "HEAD"])
    linux_ready = all(check["status"] == "ok" for check in checks)
    status = "ok" if linux_ready else "needs-attention"
    return {
        "schema": "cesium.unreal_linux_lane.v1",
        "generated_at": _now(),
        "host_state": host_state,
        "status": status,
        "selected_version": engine_version,
        "selected_version_details": selected_version,
        "source_checkout": str(SOURCE_CHECKOUT),
        "project_root": str(PROJECT_ROOT),
        "source_branch": source_branch,
        "source_commit": source_commit,
        "version_matrix": VERSION_MATRIX,
        "public_search_roots": [str(path) for path in public_engine_search_roots()["unreal"]],
        "public_unreal_archives": [str(path) for path in discover_unreal_linux_archives()],
        "linux_platform_support_search_roots": [str(path) for path in LINUX_PLATFORM_SUPPORT_SEARCH_ROOTS],
        "linux_platform_support_roots": [str(path) for path in linux_platform_support_roots],
        "linux_platform_support_ready": bool(linux_platform_support_roots),
        **build_evidence,
        "checks": checks,
        "next_steps": [
            "Run this lane on a Linux host to capture real build, package, and editor-open output.",
            "Use the Linux Unreal engine toolchain from the upstream developer-setup-linux guidance.",
            "Record any first failing UE release and toolchain detail in docs/CESIUM_UNREAL_LINUX_NOTES.md.",
            "Mount a source-built Linux Unreal tree or a populated Linux platform-support tree before treating the Docker build as a fully general upstream lane.",
        ],
        "proof_commands": [
            "cesium-unreal-linux inspect",
            "cesium-unreal-linux report",
        ],
        "build_commands": [
            f"cmake -B build -S {_display(SOURCE_CHECKOUT / 'extern' / 'cesium-native')} -DCMAKE_TOOLCHAIN_FILE={_display(SOURCE_CHECKOUT / 'extern' / 'unreal-linux-toolchain.cmake')} -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release",
            f"./RunUAT.sh BuildPlugin -Plugin={_display(PLUGIN_MANIFEST)} -Package={_display(ROOT / 'artifacts' / 'unreal-linux' / 'CesiumForUnreal')} -CreateSubFolder -TargetPlatforms=Linux",
        ],
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Unreal Linux Lane",
        "",
        f"- host_state: `{payload['host_state']}`",
        f"- status: `{payload['status']}`",
    ]
    if payload.get("selected_version") is not None:
        lines.append(f"- selected_version: `{payload.get('selected_version')}`")
    lines.extend([
        f"- source_checkout: `{payload['source_checkout']}`",
        f"- project_root: `{payload['project_root']}`",
    ])
    if payload.get("source_branch") is not None:
        lines.append(f"- source_branch: `{payload.get('source_branch') or 'unknown'}`")
    if payload.get("source_commit") is not None:
        lines.append(f"- source_commit: `{payload.get('source_commit') or 'unknown'}`")
    if payload.get("selected_version_details") is not None:
        lines.extend(["", "## Selected Version", ""])
        row = payload["selected_version_details"]
        lines.append(f"- `{row['engine_version']}`: `{row['lane_role']}`")
        lines.append(f"  focus: `{row['focus']}`")
    if payload.get("checks"):
        lines.extend(["", "## Checks", ""])
        for check in payload["checks"]:
            lines.append(f"- `{check['name']}`: `{check['status']}`")
            lines.append(f"  detail: `{check['detail']}`")
    if payload.get("version_matrix"):
        lines.extend(["", "## Version Matrix", ""])
        for row in payload["version_matrix"]:
            lines.append(f"- `{row['engine_version']}`: `{row['lane_role']}`")
            lines.append(f"  focus: `{row['focus']}`")
    if payload.get("public_search_roots"):
        lines.extend(["", "## Public Search Roots", ""])
        for root in payload["public_search_roots"]:
            lines.append(f"- `{root}`")
    if payload.get("public_unreal_archives"):
        lines.extend(["", "## Public Unreal Archives", ""])
        for archive in payload["public_unreal_archives"]:
            lines.append(f"- `{archive}`")
    if payload.get("linux_platform_support_search_roots") is not None:
        lines.extend(["", "## Linux Platform Support Search Roots", ""])
        for root in payload["linux_platform_support_search_roots"]:
            lines.append(f"- `{root}`")
    if payload.get("linux_platform_support_roots") is not None:
        lines.extend(["", "## Linux Platform Support Roots", ""])
        if payload["linux_platform_support_roots"]:
            for root in payload["linux_platform_support_roots"]:
                lines.append(f"- `{root}`")
        else:
            lines.append("- none discovered")
        lines.append(f"- ready: `{payload['linux_platform_support_ready']}`")
    if payload.get("build_status") is not None:
        lines.extend(["", "## Build Evidence", ""])
        lines.append(f"- build_status: `{payload['build_status']}`")
        lines.append(f"- build_result: `{payload.get('build_result') or 'unknown'}`")
        lines.append(f"- build_log: `{payload.get('build_log') or 'none'}`")
        if payload.get("build_output_binary") is not None:
            lines.append(f"- build_output_binary: `{payload.get('build_output_binary')}`")
    if payload.get("build_commands"):
        lines.extend(["", "## Build Commands", ""])
        for command in payload["build_commands"]:
            lines.append(f"- `{command}`")
    if payload.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in payload["next_steps"]:
            lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "report"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--format", choices=("text", "json"), default="text")
        sub.add_argument("--engine-version", choices=[row["engine_version"] for row in VERSION_MATRIX])
        if name == "report":
            sub.add_argument("--json-out", type=Path)
            sub.add_argument("--md-out", type=Path)
    return parser.parse_args(argv)


def print_text(payload: dict[str, object]) -> None:
    print("Unreal Linux Lane")
    print(f"status: {payload['status']}")
    print(f"host_state: {payload['host_state']}")
    if payload.get("selected_version") is not None:
        print(f"selected_version: {payload['selected_version']}")
    print(f"source_checkout: {payload['source_checkout']}")
    print(f"project_root: {payload['project_root']}")
    if payload.get("selected_version_details") is not None:
        row = payload["selected_version_details"]
        print("selected_version_details:")
        print(f"  - {row['engine_version']}: {row['lane_role']} ({row['focus']})")
    print("checks:")
    for check in payload.get("checks", []):
        print(f"  - {check['name']}: {check['status']} ({check['detail']})")
    if payload.get("version_matrix"):
        print("version_matrix:")
        for row in payload["version_matrix"]:
            print(f"  - {row['engine_version']}: {row['lane_role']} ({row['focus']})")
    if payload.get("public_search_roots"):
        print("public_search_roots:")
        for root in payload["public_search_roots"]:
            print(f"  - {root}")
    if payload.get("public_unreal_archives"):
        print("public_unreal_archives:")
        for archive in payload["public_unreal_archives"]:
            print(f"  - {archive}")
    print("build_evidence:")
    print(f"  - build_status: {payload.get('build_status')}")
    print(f"  - build_result: {payload.get('build_result') or 'unknown'}")
    print(f"  - build_log: {payload.get('build_log') or 'none'}")
    if payload.get("build_output_binary") is not None:
        print(f"  - build_output_binary: {payload.get('build_output_binary')}")
    print("build_commands:")
    for command in payload.get("build_commands", []):
        print(f"  - {command}")
    print("next_steps:")
    for step in payload.get("next_steps", []):
        print(f"  - {step}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = report_payload(engine_version=args.engine_version)
    if args.command == "report":
        json_out = args.json_out or (ROOT / "artifacts" / "reports" / "unreal_linux_lane.json")
        md_out = args.md_out or (ROOT / "artifacts" / "reports" / "unreal_linux_lane.md")
        write_report(payload, json_out, md_out)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print_text(payload)
    return 0 if payload["status"] in {"ok", "pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
