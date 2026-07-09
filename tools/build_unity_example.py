#!/usr/bin/env python3
"""Build the repo-owned Cesium Unity example project with a local Unity editor."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from tools import unity_env


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "unity_example_build"
DEFAULT_LOG_ROOT = ROOT / "artifacts" / "reports" / "unity_example_build" / "logs"
DEFAULT_BUILD_ROOT = PROJECT_DIR / "build" / "unity" / "CesiumVanillaExample"
BUILD_TARGETS = ("windows", "linux", "mac")
NODE_SYSTEM_CA_FLAG = "--use-system-ca"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity-version", help="Unity editor version prefix to select, for example 6000.5")
    parser.add_argument("--build-target", choices=BUILD_TARGETS, default="windows")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--log-out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preserve", action="store_true")
    return parser.parse_args(argv)


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


def _build_output_path(project_dir: Path, build_target: str) -> Path:
    base = project_dir / "build" / "unity" / "CesiumVanillaExample"
    if build_target == "windows":
        return base / "windows" / "CesiumVanillaExample.exe"
    if build_target == "linux":
        return base / "linux" / "CesiumVanillaExample.x86_64"
    return base / "mac" / "CesiumVanillaExample.app"


def _staged_project_dir(stage_root: Path, unity_version: str, stage_token: str) -> Path:
    return stage_root / _slug(unity_version) / stage_token / "CesiumVanillaExample"


def _prepare_project_dir(source_dir: Path, staged_dir: Path) -> Path:
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        if Path(directory).resolve() == source_dir.resolve():
            ignored.update({"Library", "Logs", "Temp", "UserSettings", "Build", "build"})
        if Path(directory).name == "Packages":
            ignored.add("packages-lock.json")
        return {name for name in names if name in ignored}

    shutil.copytree(source_dir, staged_dir, ignore=_ignore)
    return staged_dir


def _rewrite_project_version(project_dir: Path, unity_version: str) -> None:
    version_file = project_dir / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.is_file():
        return
    lines = version_file.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    seen_version = False
    seen_revision = False
    for line in lines:
        if line.startswith("m_EditorVersion:"):
            rewritten.append(f"m_EditorVersion: {unity_version}")
            seen_version = True
            continue
        if line.startswith("m_EditorVersionWithRevision:"):
            rewritten.append(f"m_EditorVersionWithRevision: {unity_version} (aligned)")
            seen_revision = True
            continue
        rewritten.append(line)
    if not seen_version:
        rewritten.append(f"m_EditorVersion: {unity_version}")
    if not seen_revision:
        rewritten.append(f"m_EditorVersionWithRevision: {unity_version} (aligned)")
    version_file.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def _build_command(editor: str, project_dir: Path, *, build_target: str, log_out: Path) -> list[str]:
    return [
        editor,
        "-batchmode",
        "-nographics",
        "-accept-apiupdate",
        "-quit",
        "-projectPath",
        str(project_dir),
        "-executeMethod",
        "CesiumExample.CesiumExampleBuild.BuildFromCommandLine",
        "-cesiumBuildTarget",
        build_target,
        "-logFile",
        str(log_out),
    ]


def _append_node_system_ca_flag(value: str | None) -> str:
    if not value:
        return NODE_SYSTEM_CA_FLAG
    parts = value.split()
    if NODE_SYSTEM_CA_FLAG in parts:
        return value
    return f"{value} {NODE_SYSTEM_CA_FLAG}"


def _build_env(runtime_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["NODE_OPTIONS"] = _append_node_system_ca_flag(env.get("NODE_OPTIONS"))
    # Unity 6000.3.x can try to write licensing/config files under the user's
    # LocalAppData tree. Keep the editor isolated to a writable runtime profile
    # so older installs do not inherit a blocked host profile path.
    user_profile = runtime_root / "UserProfile"
    localappdata = runtime_root / "LocalAppData"
    appdata = runtime_root / "RoamingAppData"
    temp_dir = runtime_root / "Temp"
    unity_logs_dir = runtime_root / "UnityLogs"
    upm_cache_root = runtime_root / "UPMCache"
    upm_config_root = runtime_root / "UPMConfig"
    upm_npm_cache_path = runtime_root / "UPMNpmCache"
    for path in (user_profile, localappdata, appdata, temp_dir, unity_logs_dir):
        path.mkdir(parents=True, exist_ok=True)
    for path in (upm_cache_root, upm_config_root, upm_npm_cache_path):
        path.mkdir(parents=True, exist_ok=True)
    env["USERPROFILE"] = str(user_profile)
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\"
    env["HOME"] = str(user_profile)
    env["LOCALAPPDATA"] = str(localappdata)
    env["APPDATA"] = str(appdata)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["UNITY_LOGS_DIR"] = str(unity_logs_dir)
    env["UPM_CACHE_ROOT"] = str(upm_cache_root)
    env["UPM_CONFIG_ROOT"] = str(upm_config_root)
    env["UPM_NPM_CACHE_PATH"] = str(upm_npm_cache_path)
    return env


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _failure_signals(build_log_tail: list[str]) -> list[str]:
    signals: list[str] = []
    if any("Failed to resolve packages:" in line for line in build_log_tail):
        signals.append("Package Manager tried to write under the installed editor tree and hit EPERM.")
    if any("Unable to retrieve BIOS serial number" in line for line in build_log_tail):
        signals.append("Unity licensing still hits BIOS lookup denial and mutex contention on this host.")
    return signals


def _stop_stale_unity_licensing_clients() -> None:
    # Older Unity editors can leave behind a licensing client that keeps the
    # global mutex and prevents a fresh batchmode run from progressing.
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process Unity.Licensing.Client -ErrorAction SilentlyContinue | Stop-Process -Force",
        ],
        cwd=ROOT,
    )


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Unity Example Build",
        "",
        f"- status: `{payload['status']}`",
        f"- unity_version: `{payload['unity_version']}`",
        f"- build_target: `{payload['build_target']}`",
        f"- editor_path: `{payload['editor_path']}`",
        f"- project_dir: `{payload['project_dir']}`",
        f"- output_path: `{payload['output_path']}`",
        f"- log_out: `{payload['log_out']}`",
        f"- exit_code: `{payload.get('exit_code')}`",
    ]
    if payload.get("stdout_tail"):
        lines.extend(["", "## Stdout Tail", ""])
        for line in payload["stdout_tail"]:
            lines.append(f"- {line}")
    if payload.get("stderr_tail"):
        lines.extend(["", "## Stderr Tail", ""])
        for line in payload["stderr_tail"]:
            lines.append(f"- {line}")
    if payload.get("build_log_tail"):
        lines.extend(["", "## Build Log Tail", ""])
        for line in payload["build_log_tail"]:
            lines.append(f"- {line}")
    if payload.get("failure_signals"):
        lines.extend(["", "## Failure Signals", ""])
        for signal in payload["failure_signals"]:
            lines.append(f"- {signal}")
    if payload.get("detail"):
        lines.extend(["", "## Detail", "", str(payload["detail"])])
    return "\n".join(lines) + "\n"


def _default_report_paths(out_dir: Path, unity_version: str, build_target: str) -> tuple[Path, Path, Path]:
    stem = f"unity_example_build_{_slug(unity_version)}_{build_target}"
    return (
        out_dir / f"{stem}.json",
        out_dir / f"{stem}.md",
        DEFAULT_LOG_ROOT / f"{stem}.log",
    )


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    install = unity_env.resolve_install(args.unity_version)
    if install is None or install.editor_path is None:
        return {
            "schema": "cesium.unity_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "needs-attention",
            "detail": "No suitable Unity editor install was discovered.",
            "unity_version": args.unity_version,
            "build_target": args.build_target,
            "project_dir": str(args.project_dir),
            "editor_path": None,
            "output_path": str(_build_output_path(args.project_dir, args.build_target)),
            "log_out": None,
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
        }

    json_out, md_out, log_out = _default_report_paths(args.out_dir, install.version, args.build_target)
    if args.json_out is not None:
        json_out = args.json_out
    if args.md_out is not None:
        md_out = args.md_out
    if args.log_out is not None:
        log_out = args.log_out

    stage_token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    staged_project_dir = _staged_project_dir(args.out_dir / "_work", install.version, stage_token)
    runtime_root = args.out_dir / "_work" / _slug(install.version) / stage_token / "runtime"
    output_path = _build_output_path(staged_project_dir, args.build_target)
    command = _build_command(install.editor_path, staged_project_dir, build_target=args.build_target, log_out=log_out)
    if args.dry_run:
        payload = {
            "schema": "cesium.unity_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "dry-run",
            "detail": "not executed; use without --dry-run to run the Unity example build",
            "unity_version": install.version,
            "build_target": args.build_target,
            "project_dir": str(args.project_dir),
            "staged_project_dir": str(staged_project_dir),
            "stage_token": stage_token,
            "editor_path": install.editor_path,
            "command": command,
            "output_path": str(output_path),
            "log_out": str(log_out),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
        }
        _write_report(payload, json_out, md_out)
        return payload

    _stop_stale_unity_licensing_clients()
    _prepare_project_dir(args.project_dir, staged_project_dir)
    _rewrite_project_version(staged_project_dir, install.version)
    log_out.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=_build_env(runtime_root))
    build_log_text = log_out.read_text(encoding="utf-8", errors="replace") if log_out.is_file() else ""
    build_exists = output_path.is_file() or output_path.is_dir()
    status = "pass" if completed.returncode == 0 and build_exists else "fail"
    detail = "Unity example build completed" if status == "pass" else "Unity example build failed"
    payload = {
        "schema": "cesium.unity_example_build.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "detail": detail,
        "unity_version": install.version,
        "build_target": args.build_target,
        "project_dir": str(args.project_dir),
        "staged_project_dir": str(staged_project_dir),
        "stage_token": stage_token,
        "editor_path": install.editor_path,
        "command": command,
        "output_path": str(output_path),
        "output_exists": build_exists,
        "output_size_bytes": output_path.stat().st_size if output_path.is_file() else None,
        "log_out": str(log_out),
        "exit_code": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout or ""),
        "stderr_tail": _tail_lines(completed.stderr or ""),
        "build_log_tail": _tail_lines(build_log_text),
        "failure_signals": _failure_signals(_tail_lines(build_log_text)),
    }
    _write_report(payload, json_out, md_out)
    if args.preserve:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.parent.mkdir(parents=True, exist_ok=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
