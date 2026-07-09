#!/usr/bin/env python3
"""Run the Cesium Godot example lane inside Docker with reusable log/preserve helpers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import shlex
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from extensions.cesium.tools import cesium_example_workflow
from extensions.cesium.tools import linux_docker_runner as docker_runner


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IMAGE = "cesium-linux-proof:ubuntu24.04"
DEFAULT_PLATFORM = "linux/amd64"
DEFAULT_CACHE_VOLUME = "cesium-godot-linux-proof-cache"
DEFAULT_CONTAINER_NAME_PREFIX = "cesium-godot-linux-proof"
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "reports" / "godot_linux_docker"
DEFAULT_JSON_OUT = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker.json"
DEFAULT_MD_OUT = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker.md"
DEFAULT_INNER_JSON = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker_inner.json"
DEFAULT_INNER_MD = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker_inner.md"
DEFAULT_INNER_LOG = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker_inner.log"
DEFAULT_DOCKER_LOG = DEFAULT_REPORT_DIR / "cesium-godot_linux_docker_stdout.log"
DEFAULT_PRESERVE_ROOT = ROOT / "artifacts" / "preserved"
DEFAULT_CONTAINER_GODOT_ROOT_BASE = "/opt/Godot"
DEFAULT_SCRATCH_HOME = "/tmp/cesium_godot/home"
DEFAULT_SCRATCH_CACHE = "/tmp/cesium_godot/home/.cache"
DEFAULT_SCRATCH_CONFIG = "/tmp/cesium_godot/home/.config"
DEFAULT_SCRATCH_DATA = "/tmp/cesium_godot/home/.local/share"
DEFAULT_SCRATCH_WORK_ROOT = "/tmp/cesium_godot"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="godot")
    parser.add_argument("--native-target", choices=("linux", "windows", "mac"), default="linux")
    parser.add_argument("--mode", choices=("report", "build"), default="report")
    parser.add_argument("--godot-version", help="Godot version prefix to select when running the build helper")
    parser.add_argument("--build-target", choices=("windows", "linux"), default="linux")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--cache-volume", default=DEFAULT_CACHE_VOLUME)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--inner-json-out", type=Path, default=DEFAULT_INNER_JSON)
    parser.add_argument("--inner-md-out", type=Path, default=DEFAULT_INNER_MD)
    parser.add_argument("--inner-log-out", type=Path, default=DEFAULT_INNER_LOG)
    parser.add_argument("--docker-log-out", type=Path, default=DEFAULT_DOCKER_LOG)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--docker-log-mode", choices=("capture", "tee"), default="tee")
    parser.add_argument("--log-tail-lines", type=int, default=40)
    parser.add_argument("--container-name")
    parser.add_argument("--preserve", action="store_true")
    parser.add_argument("--preserve-label", default="godot-linux-docker")
    parser.add_argument("--preserve-root", type=Path, default=DEFAULT_PRESERVE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _container_path(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT)
    return "/src/" + relative.as_posix()


def _shell_join(*parts: str | Path) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _mount_name(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path.name)


def _host_godot_roots() -> list[Path]:
    discovered: list[Path] = []
    for row in [
        *engine_root_discovery.discover_godot_windows_versions(),
        *engine_root_discovery.discover_godot_linux_versions(),
    ]:
        root = row.get("root")
        if isinstance(root, Path) and root.is_dir():
            discovered.append(root)
    if discovered:
        unique: list[Path] = []
        seen: set[str] = set()
        for root in discovered:
            marker = str(root)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(root)
        return unique
    roots: list[Path] = []
    for root in engine_root_discovery.public_engine_search_roots()["godot"]:
        if root.is_dir():
            roots.append(root)
    return roots


def _godot_mounts() -> tuple[list[str], list[str]]:
    mounts: list[str] = []
    container_roots: list[str] = []
    for root in _host_godot_roots():
        container_root = f"{DEFAULT_CONTAINER_GODOT_ROOT_BASE}/{_mount_name(root)}"
        mounts.extend(["-v", f"{root}:{container_root}:ro"])
        container_roots.append(str(container_root))
    return mounts, container_roots


def _public_search_roots() -> list[str]:
    return [str(path) for path in engine_root_discovery.public_engine_search_roots()["godot"]]


def resolved_container_name(args: argparse.Namespace) -> str:
    return docker_runner.resolved_container_name(
        DEFAULT_CONTAINER_NAME_PREFIX,
        identifier=args.native_target,
        explicit=args.container_name,
    )


def build_inner_command(args: argparse.Namespace) -> str:
    inner_json = _container_path(args.inner_json_out)
    inner_md = _container_path(args.inner_md_out)
    inner_log = _container_path(args.inner_log_out)
    if args.mode == "build":
        command = [
            "python3",
            "-m",
            "tools.build_godot_example",
            "--build-target",
            args.build_target,
            "--json-out",
            inner_json,
            "--md-out",
            inner_md,
            "--log-out",
            inner_log,
        ]
        if args.godot_version is not None:
            command.extend(["--godot-version", args.godot_version])
        return "\n".join(
            [
                "set -euo pipefail",
                "export FASTDIS_GODOT_ROOTS=/opt/Godot",
                f"export CESIUM_GODOT_WORK_ROOT={DEFAULT_SCRATCH_WORK_ROOT}",
                f"export HOME={DEFAULT_SCRATCH_HOME}",
                f"export XDG_CACHE_HOME={DEFAULT_SCRATCH_CACHE}",
                f"export XDG_CONFIG_HOME={DEFAULT_SCRATCH_CONFIG}",
                f"export XDG_DATA_HOME={DEFAULT_SCRATCH_DATA}",
                _shell_join("mkdir", "-p", DEFAULT_SCRATCH_CACHE, DEFAULT_SCRATCH_CONFIG, DEFAULT_SCRATCH_DATA),
                _shell_join(
                    "python3",
                    "-c",
                    "from pathlib import Path; Path('/tmp/cesium_godot/home/.curlrc').write_text('http1.1\\n', encoding='utf-8')",
                ),
                _shell_join("cd", "/src"),
                _shell_join(*command),
            ]
        )
    lines = [
        "set -euo pipefail",
        "export CESIUM_GODOT_WORK_ROOT=/tmp/cesium_godot",
        "export HOME=/tmp/cesium_godot/home",
        "export XDG_CACHE_HOME=/tmp/cesium_godot/home/.cache",
        "export XDG_CONFIG_HOME=/tmp/cesium_godot/home/.config",
        "export XDG_DATA_HOME=/tmp/cesium_godot/home/.local/share",
        "export FASTDIS_GODOT_ROOTS=/opt/Godot",
        _shell_join("mkdir", "-p", "/tmp/cesium_godot/home/.cache", "/tmp/cesium_godot/home/.config", "/tmp/cesium_godot/home/.local/share"),
        _shell_join(
            "python3",
            "-c",
            "from pathlib import Path; Path('/tmp/cesium_godot/home/.curlrc').write_text('http1.1\\n', encoding='utf-8')",
        ),
        _shell_join("cd", "/src"),
    ]
    command = [
        "python3",
        "-m",
        "extensions.cesium.tools.cesium_example_workflow",
        "report",
        "--engine",
        args.engine,
        "--native-target",
        args.native_target,
        "--json-out",
        inner_json,
        "--md-out",
        inner_md,
    ]
    lines.append(_shell_join(*command) + f" 2>&1 | tee {shlex.quote(inner_log)}")
    return "\n".join(lines)


def build_docker_command(args: argparse.Namespace) -> list[str]:
    mounts, container_roots = _godot_mounts()
    fastdis_roots = ":".join(container_roots)
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        resolved_container_name(args),
        "--platform",
        args.platform,
        *mounts,
        "-v",
        f"{ROOT}:/src",
        "-v",
        f"{args.cache_volume}:/tmp/cesium_godot",
        "-w",
        "/src",
        args.image,
        "bash",
        "-lc",
        build_inner_command(args) if not fastdis_roots else build_inner_command(args).replace("export FASTDIS_GODOT_ROOTS=/opt/Godot", f"export FASTDIS_GODOT_ROOTS={fastdis_roots}"),
    ]


def _outer_payload(
    *,
    args: argparse.Namespace,
    command: list[str],
    container_name: str,
    returncode: int | None,
    stdout_tail: list[str],
    stderr_tail: list[str],
    combined_output: str,
) -> dict[str, Any]:
    inner_payload = None
    if args.inner_json_out.is_file():
        try:
            loaded = json.loads(args.inner_json_out.read_text(encoding="utf-8"))
            inner_payload = loaded if isinstance(loaded, dict) else None
        except Exception:
            inner_payload = None
    status = "pass" if returncode == 0 else "fail"
    detail = "\n".join([*stdout_tail[-5:], *stderr_tail[-5:]]).strip()
    return {
        "schema": "cesium.godot_linux_docker.v1",
        "generated_at": docker_runner.now(),
        "engine": args.engine,
        "native_target": args.native_target,
        "mode": args.mode,
        "status": status,
        "container_name": container_name,
        "public_search_roots": _public_search_roots(),
        "host_godot_roots": [str(path) for path in _host_godot_roots()],
        "container_godot_roots": container_roots,
        "scratch_home": DEFAULT_SCRATCH_HOME,
        "scratch_cache": DEFAULT_SCRATCH_CACHE,
        "scratch_config": DEFAULT_SCRATCH_CONFIG,
        "scratch_data": DEFAULT_SCRATCH_DATA,
        "scratch_work_root": DEFAULT_SCRATCH_WORK_ROOT,
        "cache_volume": args.cache_volume,
        "command": command,
        "docker_log": str(args.docker_log_out),
        "inner_json": str(args.inner_json_out),
        "inner_md": str(args.inner_md_out),
        "inner_log": str(args.inner_log_out),
        "exit_code": returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "detail": detail or ("godot docker lane completed" if status == "pass" else "godot docker lane failed"),
        "inner_report": inner_payload,
        "combined_output": combined_output[-4000:],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Godot Linux Docker",
        "",
        f"- engine: `{payload['engine']}`",
        f"- native_target: `{payload['native_target']}`",
        f"- mode: `{payload.get('mode')}`",
        f"- status: `{payload['status']}`",
        f"- container_name: `{payload['container_name']}`",
        f"- scratch_home: `{payload.get('scratch_home')}`",
        f"- cache_volume: `{payload.get('cache_volume')}`",
        f"- exit_code: `{payload.get('exit_code')}`",
        f"- docker_log: `{payload['docker_log']}`",
        f"- inner_json: `{payload['inner_json']}`",
        f"- inner_md: `{payload['inner_md']}`",
    ]
    if payload.get("public_search_roots"):
        lines.extend(["", "## Public Search Roots", ""])
        for row in payload["public_search_roots"]:
            lines.append(f"- {row}")
    if payload.get("host_godot_roots"):
        lines.extend(["", "## Host Godot Roots", ""])
        for row in payload["host_godot_roots"]:
            lines.append(f"- {row}")
    if payload.get("container_godot_roots"):
        lines.extend(["", "## Container Godot Roots", ""])
        for row in payload["container_godot_roots"]:
            lines.append(f"- {row}")
    if payload.get("inner_report") and isinstance(payload["inner_report"], dict):
        lines.extend(["", "## Inner Report", ""])
        inner = payload["inner_report"]
        lines.append(f"- status: `{inner.get('status')}`")
        lines.append(f"- preferred_version: `{inner.get('preferred_version')}`")
        lines.append(f"- source_checkout: `{inner.get('source_checkout')}`")
        if inner.get("build_target") is not None:
            lines.append(f"- build_target: `{inner.get('build_target')}`")
        if inner.get("output_path") is not None:
            lines.append(f"- output_path: `{inner.get('output_path')}`")
    if payload.get("stdout_tail"):
        lines.extend(["", "## Stdout Tail", ""])
        for row in payload["stdout_tail"]:
            lines.append(f"- {row}")
    if payload.get("stderr_tail"):
        lines.extend(["", "## Stderr Tail", ""])
        for row in payload["stderr_tail"]:
            lines.append(f"- {row}")
    if payload.get("detail"):
        lines.extend(["", "## Detail", "", str(payload["detail"])])
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], args: argparse.Namespace) -> None:
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    container_name = resolved_container_name(args)
    command = build_docker_command(args)
    if args.dry_run:
        payload = {
        "schema": "cesium.godot_linux_docker.v1",
        "generated_at": docker_runner.now(),
        "engine": args.engine,
        "native_target": args.native_target,
        "mode": args.mode,
        "status": "dry-run",
            "container_name": container_name,
            "public_search_roots": _public_search_roots(),
            "host_godot_roots": [str(path) for path in _host_godot_roots()],
            "container_godot_roots": _godot_mounts()[1],
            "scratch_home": DEFAULT_SCRATCH_HOME,
            "scratch_cache": DEFAULT_SCRATCH_CACHE,
            "scratch_config": DEFAULT_SCRATCH_CONFIG,
            "scratch_data": DEFAULT_SCRATCH_DATA,
            "scratch_work_root": DEFAULT_SCRATCH_WORK_ROOT,
            "cache_volume": args.cache_volume,
            "command": command,
            "docker_log": str(args.docker_log_out),
            "inner_json": str(args.inner_json_out),
            "inner_md": str(args.inner_md_out),
            "inner_log": str(args.inner_log_out),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "detail": "not executed; use without --dry-run to probe the Linux container lane",
            "inner_report": None,
            "combined_output": "",
        }
        write_report(payload, args)
        print(json.dumps(payload, indent=2))
        return 0
    returncode, stdout_tail, stderr_tail, combined_output = docker_runner.run_command_with_logging(
        command,
        log_out=args.docker_log_out,
        log_mode=args.docker_log_mode,
        timeout_seconds=args.timeout_seconds,
        log_tail_lines=args.log_tail_lines,
        container_name=container_name,
    )
    payload = _outer_payload(
        args=args,
        command=command,
        container_name=container_name,
        returncode=returncode,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        combined_output=combined_output,
    )
    write_report(payload, args)
    if args.preserve:
        docker_runner.preserve_artifact(args.json_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="json")
        docker_runner.preserve_artifact(args.md_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="md")
        docker_runner.preserve_artifact(args.docker_log_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="docker")
        docker_runner.preserve_artifact(args.inner_json_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="inner")
        docker_runner.preserve_artifact(args.inner_md_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="inner")
        docker_runner.preserve_artifact(args.inner_log_out, preserve_root=args.preserve_root, preserve_label=args.preserve_label, prefix="inner")
    print(json.dumps(payload, indent=2))
    return returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
