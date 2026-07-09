#!/usr/bin/env python3
"""Aggressively launch the Godot visual-proof scene across installed versions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions.cesium.tools import engine_root_discovery
from tools import godot_versioning


PROJECT_DIR = ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "godot_aggressive_launcher"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "godot_aggressive_launcher.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "godot_aggressive_launcher.md"
DEFAULT_LOG_DIR = DEFAULT_OUT_DIR / "logs"
DEFAULT_SCENE = "res://scenes/Main.tscn"
DEFAULT_CAPTURE_ROOT = ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample" / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
STALE_EXTENSION_ENTRY = "res://CesiumVanillaExample.gdextension"
HEALTH_PROBE_SCRIPT = "res://scripts/StartupHealthProbe.gd"
EXPECTED_PNGS = (
    "proxy_overview.png",
    "proxy_oblique.png",
    "proxy_close.png",
    "cesium_overview.png",
    "cesium_oblique.png",
    "cesium_close.png",
)


@dataclass(frozen=True)
class Attempt:
    version: str
    executable: Path
    strategy: str


def _repo_alias_root(root: Path) -> Path:
    resolved = root.resolve()
    if platform.system().lower() != "windows":
        return resolved
    alias_root = Path(os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp"))) / "cesium_godot" / "repo"
    alias_root.parent.mkdir(parents=True, exist_ok=True)
    if alias_root.exists() or alias_root.is_symlink():
        return alias_root
    try:
        alias_root.symlink_to(resolved, target_is_directory=True)
        return alias_root
    except OSError:
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(alias_root), str(resolved)],
                check=True,
                capture_output=True,
                text=True,
            )
            if alias_root.exists():
                return alias_root
        except (OSError, subprocess.SubprocessError):
            pass
    return resolved


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    parser.add_argument("--godot-selector", help="Optional Godot version selector such as 4.7-stable..4.8-dev1")
    parser.add_argument("--max-versions", type=int, default=0, help="Optional cap on how many installed versions to try")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


def _discover_versions(native_target: str) -> list[dict[str, object]]:
    if native_target == "windows":
        return engine_root_discovery.discover_godot_windows_versions()
    if native_target == "linux":
        return engine_root_discovery.discover_godot_linux_versions()
    return engine_root_discovery.discover_godot_macos_versions()


def _ordered_versions(
    native_target: str,
    selector: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    rows = _discover_versions(native_target)
    versions = [str(row.get("version") or "") for row in rows if str(row.get("version") or "")]
    ordered = godot_versioning.select_versions(versions, selector, limit=limit)
    ordered_rows: list[dict[str, object]] = []
    for version in ordered:
        for row in rows:
            if str(row.get("version") or "") == version:
                ordered_rows.append(row)
                break
    return ordered_rows


def _pick_executables(install: dict[str, object]) -> list[tuple[str, Path]]:
    executables: list[tuple[str, Path]] = []
    console = install.get("console_executable")
    executable = install.get("executable")
    if isinstance(console, Path) and console.is_file():
        executables.append(("console", console))
    if isinstance(executable, Path) and executable.is_file():
        if not executables or executables[-1][1] != executable:
            executables.append(("gui", executable))
    return executables


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    system = platform.system().lower()
    if system == "darwin":
        runtime_root = DEFAULT_OUT_DIR / "_work" / "runtime"
        home = runtime_root / "Home"
        cache = home / ".cache"
        config = home / ".config"
        data = home / ".local" / "share"
        temp_dir = runtime_root / "Temp"
        for path in (home, cache, config, data, temp_dir):
            path.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
        env["CFFIXED_USER_HOME"] = str(home)
        env["TMPDIR"] = str(temp_dir)
        env["XDG_CACHE_HOME"] = str(cache)
        env["XDG_CONFIG_HOME"] = str(config)
        env["XDG_DATA_HOME"] = str(data)
        return env
    if system != "windows":
        return env
    runtime_root = DEFAULT_OUT_DIR / "_work" / "runtime"
    user_profile = runtime_root / "UserProfile"
    localappdata = runtime_root / "LocalAppData"
    appdata = runtime_root / "RoamingAppData"
    temp_dir = runtime_root / "Temp"
    godot_user_dir = runtime_root / "GodotUser"
    for path in (user_profile, localappdata, appdata, temp_dir, godot_user_dir):
        path.mkdir(parents=True, exist_ok=True)
    (godot_user_dir / "logs").mkdir(parents=True, exist_ok=True)
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


def _sanitize_project_extension_cache(project_dir: Path) -> list[str]:
    extension_list = project_dir / ".godot" / "extension_list.cfg"
    if not extension_list.is_file():
        return []
    lines = extension_list.read_text(encoding="utf-8").splitlines()
    removed = [line for line in lines if line.strip() == STALE_EXTENSION_ENTRY]
    if not removed:
        return []
    kept = [line for line in lines if line.strip() and line.strip() != STALE_EXTENSION_ENTRY]
    if kept:
        extension_list.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        extension_list.unlink()
    return removed


def _capture_paths(capture_root: Path) -> list[Path]:
    return [capture_root / name for name in EXPECTED_PNGS]


def _launch_flags(native_target: str) -> list[str]:
    if native_target == "windows":
        return ["--audio-driver", "Dummy", "--rendering-driver", "opengl3"]
    return ["--audio-driver", "Dummy"]


def _health_probe_command(executable: Path, project_dir: Path) -> list[str]:
    return [
        str(executable),
        "--headless",
        "--audio-driver",
        "Dummy",
        "--path",
        str(project_dir),
        "--script",
        HEALTH_PROBE_SCRIPT,
    ]


def _attempt_command(executable: Path, project_dir: Path, scene: str, capture_root: Path, native_target: str) -> list[str]:
    return [
        str(executable),
        *_launch_flags(native_target),
        "--path",
        str(project_dir),
        "--scene",
        scene,
    ]


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _build_attempts(args: argparse.Namespace) -> list[Attempt]:
    ordered = _ordered_versions(args.native_target, args.godot_selector, args.max_versions or None)
    attempts: list[Attempt] = []
    for row in ordered:
        version = str(row.get("version") or "")
        for strategy, executable in _pick_executables(row):
            attempts.append(Attempt(version=version, executable=executable, strategy=strategy))
    return attempts


def _run_attempt(
    *,
    attempt: Attempt,
    args: argparse.Namespace,
    env: dict[str, str],
    log_path: Path,
) -> dict[str, Any]:
    command = _attempt_command(attempt.executable, args.project_dir, args.scene, args.capture_root, args.native_target)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=env)
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(combined_output + ("\n" if combined_output and not combined_output.endswith("\n") else ""), encoding="utf-8")
    capture_paths = _capture_paths(args.capture_root)
    capture_exists = all(path.is_file() for path in capture_paths)
    return {
        "version": attempt.version,
        "strategy": attempt.strategy,
        "executable": str(attempt.executable),
        "command": command,
        "log_path": str(log_path),
        "exit_code": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout or ""),
        "stderr_tail": _tail_lines(completed.stderr or ""),
        "capture_root": str(args.capture_root),
        "capture_paths": [str(path) for path in capture_paths],
        "capture_exists": capture_exists,
        "success": completed.returncode == 0 and capture_exists,
    }


def _run_health_probe(
    *,
    executable: Path,
    project_dir: Path,
    env: dict[str, str],
    log_path: Path,
) -> dict[str, Any]:
    command = _health_probe_command(executable, project_dir)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=env)
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(combined_output + ("\n" if combined_output and not combined_output.endswith("\n") else ""), encoding="utf-8")
    stdout_tail = _tail_lines(completed.stdout or "")
    stderr_tail = _tail_lines(completed.stderr or "")
    startup_ok = completed.returncode == 0
    return {
        "executable": str(executable),
        "command": command,
        "log_path": str(log_path),
        "exit_code": completed.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "startup_ok": startup_ok,
        "success": startup_ok,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Godot Aggressive Launcher",
        "",
        f"- status: `{payload['status']}`",
        f"- requested_selector: `{payload.get('requested_selector') or 'none'}`",
        f"- capture_root: `{payload.get('capture_root')}`",
        f"- project_dir: `{payload.get('project_dir')}`",
        f"- attempts: `{len(payload.get('attempts', []))}`",
        f"- successful_attempt: `{payload.get('successful_attempt_index')}`",
    ]
    startup_health = payload.get("startup_health")
    if isinstance(startup_health, dict):
        lines.extend([
            "",
            "## Startup Health",
            "",
            f"- executable: `{startup_health.get('executable')}`",
            f"- exit_code: `{startup_health.get('exit_code')}`",
            f"- success: `{startup_health.get('success')}`",
            f"- log_path: `{startup_health.get('log_path')}`",
        ])
    if payload.get("attempts"):
        lines.extend(["", "## Attempts", ""])
        for attempt in payload["attempts"]:
            if not isinstance(attempt, dict):
                continue
            lines.append(f"### {attempt.get('version')} / {attempt.get('strategy')}")
            lines.append(f"- executable: `{attempt.get('executable')}`")
            lines.append(f"- exit_code: `{attempt.get('exit_code')}`")
            lines.append(f"- success: `{attempt.get('success')}`")
            lines.append(f"- log_path: `{attempt.get('log_path')}`")
            if attempt.get("capture_paths"):
                lines.append("- capture_paths:")
                for path in attempt["capture_paths"]:
                    lines.append(f"  - `{path}`")
    if payload.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in payload["next_steps"]:
            lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(_render_markdown(payload), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = _repo_alias_root(args.project_dir.expanduser())
    capture_root = args.capture_root.expanduser().resolve()
    if capture_root == DEFAULT_CAPTURE_ROOT.resolve():
        capture_root = project_dir / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
    capture_paths = _capture_paths(capture_root)
    sanitized_extension_entries = _sanitize_project_extension_cache(project_dir)
    attempts = _build_attempts(args)
    ordered_versions: list[str] = []
    for attempt in attempts:
        if attempt.version in ordered_versions:
            continue
        ordered_versions.append(attempt.version)
    payload: dict[str, Any] = {
        "schema": "cesium.godot_aggressive_launcher.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "project_dir": str(project_dir),
        "scene": args.scene,
        "capture_root": str(capture_root),
        "native_target": args.native_target,
        "capture_paths": [str(path) for path in capture_paths],
        "requested_selector": args.godot_selector,
        "installed_versions_order": ordered_versions,
        "sanitized_extension_entries": sanitized_extension_entries,
        "startup_health": None,
        "attempts": [],
        "successful_attempt_index": None,
        "status": "dry-run" if args.dry_run else "needs-attention",
        "next_steps": [
            f"Use the newest installed {args.native_target.title()} Godot version first, then fall through to older installs if the scene fails.",
            "Keep the console binary as the preferred launcher and fall back to the GUI binary when needed.",
            "Use the capture root from the report so repeated runs land in a stable proof folder.",
        ],
    }
    if args.dry_run:
        first_attempt = attempts[0] if attempts else None
        payload["startup_health"] = {
            "executable": str(first_attempt.executable) if first_attempt else None,
            "command": _health_probe_command(first_attempt.executable, project_dir) if first_attempt else None,
            "log_path": str(args.log_dir / "startup_health_probe.log"),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "startup_ok": False,
            "success": False,
        }
        payload["attempts"] = [
            {
                "version": attempt.version,
                "strategy": attempt.strategy,
                "executable": str(attempt.executable),
                "command": _attempt_command(attempt.executable, project_dir, args.scene, capture_root, args.native_target),
                "log_path": str(args.log_dir / f"{_slug(attempt.version)}_{attempt.strategy}.log"),
                "exit_code": None,
                "stdout_tail": [],
                "stderr_tail": [],
                "capture_root": str(capture_root),
                "capture_paths": [str(path) for path in capture_paths],
                "capture_exists": False,
                "success": False,
            }
            for attempt in attempts
        ]
        return payload

    env = _build_env()
    if attempts:
        startup_log_path = args.log_dir / "startup_health_probe.log"
        startup_result = _run_health_probe(
            executable=attempts[0].executable,
            project_dir=project_dir,
            env=env,
            log_path=startup_log_path,
        )
        payload["startup_health"] = startup_result
        if not startup_result["success"]:
            payload["status"] = "fail"
            payload["next_steps"] = [
                "Fix the startup health probe before running the visual proof lane.",
                "Inspect the health probe log for shader-cache or extension-registration errors.",
            ]
            return payload

    success_index: int | None = None
    for index, attempt in enumerate(attempts):
        log_path = args.log_dir / f"{_slug(attempt.version)}_{attempt.strategy}.log"
        result = _run_attempt(attempt=attempt, args=args, env=env, log_path=log_path)
        payload["attempts"].append(result)
        if result["success"]:
            success_index = index
            break

    payload["successful_attempt_index"] = success_index
    payload["status"] = "pass" if success_index is not None else "fail"
    if success_index is not None:
        payload["next_steps"] = [
            f"The first successful {args.native_target.title()} Godot install can be reused for visual proof on this host.",
            "If you want a different version order, pass --godot-selector or lower --max-versions.",
        ]
    else:
        payload["next_steps"] = [
            f"No {args.native_target.title()} Godot install completed the proof scene successfully.",
            "Try a different selector, or inspect the per-attempt logs under the report directory.",
        ]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
