#!/usr/bin/env python3
"""Build the repo-owned Cesium Godot example project with a local editor."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any

from extensions.cesium.tools import engine_root_discovery


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "godot_example_build"
DEFAULT_LOG_ROOT = DEFAULT_OUT_DIR / "logs"
BUILD_TARGETS = ("windows", "linux")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot-version", help="Godot version prefix to select, for example 4.7")
    parser.add_argument("--build-target", choices=BUILD_TARGETS, default="windows")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--log-out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


def _export_preset_name(build_target: str) -> str:
    return {
        "windows": "Windows Desktop",
        "linux": "Linux/X11",
    }[build_target]


def _template_stem() -> str:
    return "windows_x86_64" if platform.system().lower() == "windows" else "linux.x86_64"


def _template_root(godot_version: str, runtime_root: Path) -> Path:
    override = os.environ.get("FASTDIS_GODOT_EXPORT_TEMPLATES_ROOT")
    if override:
        return Path(override).expanduser() / godot_version
    if platform.system().lower() == "windows":
        return Path(os.environ.get("APPDATA", str(runtime_root / "RoamingAppData"))) / "Godot" / "export_templates" / godot_version
    return Path(os.environ.get("XDG_DATA_HOME", str(runtime_root / "Home" / ".local" / "share"))) / "godot" / "export_templates" / godot_version


def _template_paths(template_root: Path, build_target: str) -> list[Path]:
    if build_target == "windows":
        return [template_root / "windows_debug_x86_64.exe", template_root / "windows_release_x86_64.exe"]
    return [template_root / "linux_debug.x86_64", template_root / "linux_release.x86_64"]


def _build_output_path(project_dir: Path, build_target: str) -> Path:
    base = project_dir / "build" / "godot" / "CesiumVanillaExample"
    if build_target == "windows":
        return base / "windows" / "CesiumVanillaExample.exe"
    return base / "linux" / "CesiumVanillaExample.x86_64"


def _staged_project_dir(stage_root: Path, godot_version: str, stage_token: str) -> Path:
    return stage_root / _slug(godot_version) / stage_token / "CesiumVanillaExample"


def _ignore_build_artifacts(directory: str, names: list[str]) -> set[str]:
    ignored = {"Library", "Logs", "Temp", "UserSettings", "build", "Build", ".godot"}
    if Path(directory).name == "build":
        ignored.update(names)
    return {name for name in names if name in ignored}


def _prepare_project_dir(source_dir: Path, staged_dir: Path) -> Path:
    shutil.copytree(source_dir, staged_dir, ignore=_ignore_build_artifacts)
    return staged_dir


def _discover_installs() -> list[dict[str, object]]:
    system = platform.system().lower()
    if system == "windows":
        return engine_root_discovery.discover_godot_windows_versions()
    return engine_root_discovery.discover_godot_linux_versions()


def _public_search_roots() -> list[str]:
    return [str(path) for path in engine_root_discovery.public_engine_search_roots()["godot"]]


def _resolve_install(godot_version: str | None = None) -> dict[str, object] | None:
    installs = _discover_installs()
    if godot_version is not None:
        for install in installs:
            version = str(install.get("version") or "")
            if version == godot_version or version.startswith(godot_version):
                return install
        return None
    return installs[0] if installs else None


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _failure_signals(build_log_tail: list[str]) -> list[str]:
    signals: list[str] = []
    if any("No export templates found" in line for line in build_log_tail):
        signals.append("Godot export templates are missing from the selected editor install.")
    if any("ERROR:" in line for line in build_log_tail):
        signals.append("Godot emitted at least one build-time error during export.")
    if any("SCRIPT ERROR" in line for line in build_log_tail):
        signals.append("Godot reported a script error while preparing the export.")
    if any("Failed to load" in line for line in build_log_tail):
        signals.append("Godot could not load part of the project or export configuration.")
    return signals


def _missing_template_signals(template_paths: list[Path]) -> list[str]:
    return [f"Missing export template: {path}" for path in template_paths if not path.is_file()]


def _build_command(editor: str, project_dir: Path, *, build_target: str, output_path: Path) -> list[str]:
    return [
        editor,
        "--headless",
        "--path",
        str(project_dir),
        "--export-release",
        _export_preset_name(build_target),
        str(output_path),
        "--quit",
    ]


def _default_report_paths(out_dir: Path, godot_version: str, build_target: str) -> tuple[Path, Path, Path]:
    stem = f"godot_example_build_{_slug(godot_version)}_{build_target}"
    return (
        out_dir / f"{stem}.json",
        out_dir / f"{stem}.md",
        DEFAULT_LOG_ROOT / f"{stem}.log",
    )


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def _build_env(runtime_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    if platform.system().lower() != "windows":
        return env
    user_profile = runtime_root / "UserProfile"
    localappdata = runtime_root / "LocalAppData"
    appdata = runtime_root / "RoamingAppData"
    temp_dir = runtime_root / "Temp"
    godot_user_dir = runtime_root / "GodotUser"
    for path in (user_profile, localappdata, appdata, temp_dir, godot_user_dir):
        path.mkdir(parents=True, exist_ok=True)
    env["USERPROFILE"] = str(user_profile)
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\"
    env["HOME"] = str(user_profile)
    env["LOCALAPPDATA"] = str(localappdata)
    env["APPDATA"] = str(appdata)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["GODOT_USER_DIR"] = str(godot_user_dir)
    return env


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Godot Example Build",
        "",
        f"- status: `{payload['status']}`",
        f"- godot_version: `{payload.get('godot_version')}`",
        f"- build_target: `{payload['build_target']}`",
        f"- editor_path: `{payload.get('editor_path')}`",
        f"- project_dir: `{payload['project_dir']}`",
        f"- staged_project_dir: `{payload.get('staged_project_dir')}`",
        f"- template_root: `{payload.get('template_root')}`",
        f"- output_path: `{payload['output_path']}`",
        f"- log_out: `{payload['log_out']}`",
        f"- exit_code: `{payload.get('exit_code')}`",
    ]
    if payload.get("template_paths"):
        lines.extend(["", "## Template Paths", ""])
        for path in payload["template_paths"]:
            lines.append(f"- {path}")
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


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = args.project_dir.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    public_search_roots = _public_search_roots()
    install = _resolve_install(args.godot_version)
    if install is None or not install.get("executable"):
        return {
            "schema": "cesium.godot_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "needs-attention",
            "detail": "No suitable Godot editor install was discovered.",
            "godot_version": args.godot_version,
            "build_target": args.build_target,
            "project_dir": str(project_dir),
            "public_search_roots": public_search_roots,
            "editor_path": None,
            "output_path": str(_build_output_path(project_dir, args.build_target)),
            "template_root": None,
            "template_paths": [],
            "missing_template_paths": [],
            "log_out": None,
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
            "next_steps": [
                "Install a Godot editor under one of the discovered public search roots, or set FASTDIS_GODOT_ROOTS.",
                r'For Windows, a good default is C:\Users\Public\Godot\engines\windows or C:\Users\Public\Godot\engines\linux.',
                "Install the matching export template package for the target editor version.",
            ],
        }

    godot_version = str(install.get("version") or args.godot_version or "unknown")
    json_out, md_out, log_out = _default_report_paths(out_dir, godot_version, args.build_target)
    if args.json_out is not None:
        json_out = args.json_out
    if args.md_out is not None:
        md_out = args.md_out
    if args.log_out is not None:
        log_out = args.log_out

    stage_token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    staged_project_dir = _staged_project_dir(out_dir / "_work", godot_version, stage_token)
    output_path = _build_output_path(staged_project_dir, args.build_target)
    command = _build_command(str(install["executable"]), staged_project_dir, build_target=args.build_target, output_path=output_path)
    runtime_root = out_dir / "_work" / _slug(godot_version) / stage_token / "runtime"
    template_root = _template_root(godot_version, runtime_root)
    template_paths = _template_paths(template_root, args.build_target)
    missing_template_paths = [str(path) for path in template_paths if not path.is_file()]

    if args.dry_run:
        payload = {
            "schema": "cesium.godot_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "dry-run",
            "detail": "not executed; use without --dry-run to run the Godot example build",
            "godot_version": godot_version,
            "build_target": args.build_target,
            "project_dir": str(project_dir),
            "staged_project_dir": str(staged_project_dir),
            "stage_token": stage_token,
            "public_search_roots": public_search_roots,
            "template_root": str(template_root),
            "template_paths": [str(path) for path in template_paths],
            "missing_template_paths": missing_template_paths,
            "editor_path": str(install["executable"]),
            "command": command,
            "output_path": str(output_path),
            "log_out": str(log_out),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
            "next_steps": [
                f"Search for Godot installs under: {', '.join(public_search_roots) or 'the configured roots'}",
                "Install matching export templates before running the export build.",
            ],
        }
        _write_report(payload, json_out, md_out)
        return payload

    _prepare_project_dir(args.project_dir, staged_project_dir)
    log_out.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=_build_env(runtime_root))
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    log_out.write_text(combined_output + ("\n" if combined_output and not combined_output.endswith("\n") else ""), encoding="utf-8")
    build_log_text = log_out.read_text(encoding="utf-8", errors="replace") if log_out.is_file() else ""
    output_exists = output_path.is_file() or output_path.is_dir()
    status = "pass" if completed.returncode == 0 and output_exists else "fail"
    payload = {
        "schema": "cesium.godot_example_build.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "detail": "Godot example build completed" if status == "pass" else "Godot example build failed",
        "godot_version": godot_version,
        "build_target": args.build_target,
        "project_dir": str(project_dir),
        "staged_project_dir": str(staged_project_dir),
        "stage_token": stage_token,
        "public_search_roots": public_search_roots,
        "template_root": str(template_root),
        "template_paths": [str(path) for path in template_paths],
        "missing_template_paths": missing_template_paths,
        "editor_path": str(install["executable"]),
        "command": command,
        "output_path": str(output_path),
        "output_exists": output_exists,
        "output_size_bytes": output_path.stat().st_size if output_path.is_file() else None,
        "log_out": str(log_out),
        "exit_code": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout or ""),
        "stderr_tail": _tail_lines(completed.stderr or ""),
        "build_log_tail": _tail_lines(build_log_text),
        "failure_signals": [*_failure_signals(_tail_lines(build_log_text)), *_missing_template_signals(template_paths)],
        "next_steps": [
            "If the lane failed on missing templates, install the matching Godot export template pack into the discovered template root.",
            "If the lane failed on discovery, place the editor under one of the public search roots or set FASTDIS_GODOT_ROOTS.",
        ],
    }
    _write_report(payload, json_out, md_out)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
