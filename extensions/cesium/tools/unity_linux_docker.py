#!/usr/bin/env python3
"""Run the Cesium Unity native matrix inside a Linux Docker proof container."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
from typing import Any

from extensions.cesium.tools import linux_docker_runner as docker_runner
from tools import unity_env


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IMAGE = "cesium-linux-proof:ubuntu24.04"
DEFAULT_PLATFORM = "linux/amd64"
DEFAULT_CONTAINER_NAME_PREFIX = "cesium-unity-linux-proof"
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "reports" / "unity_linux_docker"
DEFAULT_JSON_OUT = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker.json"
DEFAULT_MD_OUT = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker.md"
DEFAULT_INNER_JSON = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker_inner.json"
DEFAULT_INNER_MD = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker_inner.md"
DEFAULT_INNER_LOG = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker_inner.log"
DEFAULT_DOCKER_LOG = DEFAULT_REPORT_DIR / "cesium-unity_linux_docker_stdout.log"
DEFAULT_PRESERVE_ROOT = ROOT / "artifacts" / "preserved"
DEFAULT_CONTAINER_UNITY_ROOT_BASE = "/opt/Unity/Hub/Editor"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="unity")
    parser.add_argument("--native-target", choices=("linux",), default="linux")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
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
    parser.add_argument("--preserve-label", default="unity-linux-docker")
    parser.add_argument("--preserve-root", type=Path, default=DEFAULT_PRESERVE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _container_path(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT)
    return "/src/" + relative.as_posix()


def _shell_join(*parts: str | Path) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _slug_path(path: Path) -> str:
    return str(path).replace(":", "_").replace("\\", "_").replace("/", "_").replace(" ", "_")


def _host_unity_roots() -> list[Path]:
    discovered = unity_env.discover_installs()
    roots = [Path(install.install_root) for install in discovered if install.install_root]
    if roots:
        return roots
    fallback: list[Path] = []
    for root in unity_env.default_scan_roots():
        if root.is_dir():
            fallback.append(root)
    return fallback


def _unity_mounts() -> tuple[list[str], list[str]]:
    mounts: list[str] = []
    container_roots: list[str] = []
    for root in _host_unity_roots():
        container_root = f"{DEFAULT_CONTAINER_UNITY_ROOT_BASE}/{_slug_path(root)}"
        mounts.extend(["-v", f"{root}:{container_root}:ro"])
        container_roots.append(str(container_root))
    return mounts, container_roots


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
    lines = [
        "set -euo pipefail",
        "export HOME=/tmp/cesium_unity/home",
        "export XDG_CACHE_HOME=/tmp/cesium_unity/home/.cache",
        "export XDG_CONFIG_HOME=/tmp/cesium_unity/home/.config",
        "export XDG_DATA_HOME=/tmp/cesium_unity/home/.local/share",
        "export FASTDIS_UNITY_ROOTS=/opt/Unity/Hub/Editor",
        _shell_join("mkdir", "-p", "/tmp/cesium_unity/home/.cache", "/tmp/cesium_unity/home/.config", "/tmp/cesium_unity/home/.local/share"),
        _shell_join(
            "python3",
            "-c",
            "from pathlib import Path; Path('/tmp/cesium_unity/home/.curlrc').write_text('http1.1\\n', encoding='utf-8')",
        ),
        _shell_join("cd", "/src"),
    ]
    command = [
        "python3",
        "-m",
        "tools.build_unity_native_matrix",
        "--json-out",
        inner_json,
        "--md-out",
        inner_md,
    ]
    lines.append(_shell_join(*command) + f" 2>&1 | tee {shlex.quote(inner_log)}")
    return "\n".join(lines)


def build_docker_command(args: argparse.Namespace) -> list[str]:
    mounts, container_roots = _unity_mounts()
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
        "-w",
        "/src",
        args.image,
        "bash",
        "-lc",
        build_inner_command(args) if not fastdis_roots else build_inner_command(args).replace("export FASTDIS_UNITY_ROOTS=/opt/Unity/Hub/Editor", f"export FASTDIS_UNITY_ROOTS={fastdis_roots}"),
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
    inner_status = str(inner_payload.get("status") or "") if isinstance(inner_payload, dict) else ""
    status = inner_status or ("pass" if returncode == 0 else "fail")
    detail = "\n".join([*stdout_tail[-5:], *stderr_tail[-5:]]).strip()
    blocker_signals = _blocker_signals(inner_payload)
    host_snapshot = unity_env.describe_host()
    return {
        "schema": "cesium.unity_linux_docker.v1",
        "generated_at": docker_runner.now(),
        "engine": args.engine,
        "native_target": args.native_target,
        "status": status,
        "container_name": container_name,
        "command": command,
        "docker_log": str(args.docker_log_out),
        "inner_json": str(args.inner_json_out),
        "inner_md": str(args.inner_md_out),
        "inner_log": str(args.inner_log_out),
        "exit_code": returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "detail": detail or ("unity docker lane completed" if status == "pass" else "unity docker lane failed"),
        "inner_report": inner_payload,
        "blocker_signals": blocker_signals,
        "host_snapshot": {
            "platform": host_snapshot.get("platform"),
            "arch": host_snapshot.get("arch"),
            "public_roots": host_snapshot.get("public_roots", []),
            "installed_versions": [install.get("version") for install in host_snapshot.get("installs", []) if isinstance(install, dict)],
            "default_install": host_snapshot.get("default_install"),
        },
        "combined_output": combined_output[-4000:],
    }


def _blocker_signals(inner_report: dict[str, Any] | None) -> list[str]:
    if not isinstance(inner_report, dict):
        return []
    signals: list[str] = []
    host = inner_report.get("host")
    if isinstance(host, dict):
        installs = host.get("installs", [])
        if isinstance(installs, list) and not installs:
            signals.append("The Linux container did not discover a Unity editor install, so this lane is still proof-of-commandability only.")
    summary = inner_report.get("summary")
    if isinstance(summary, dict):
        installed_versions = summary.get("installed_versions", [])
        if isinstance(installed_versions, list) and not installed_versions:
            signals.append("Unity Linux/Docker still has no installed editor versions inside the container.")
    gaps = inner_report.get("gaps", [])
    if isinstance(gaps, list):
        for gap in gaps:
            text = str(gap)
            if text and "Unity Linux/Docker" in text and text not in signals:
                signals.append(text)
    return signals


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Unity Linux Docker",
        "",
        f"- engine: `{payload['engine']}`",
        f"- native_target: `{payload['native_target']}`",
        f"- status: `{payload['status']}`",
        f"- container_name: `{payload['container_name']}`",
        f"- exit_code: `{payload.get('exit_code')}`",
        f"- docker_log: `{payload['docker_log']}`",
        f"- inner_json: `{payload['inner_json']}`",
        f"- inner_md: `{payload['inner_md']}`",
    ]
    if payload.get("inner_report") and isinstance(payload["inner_report"], dict):
        lines.extend(["", "## Inner Report", ""])
        inner = payload["inner_report"]
        lines.append(f"- status: `{inner.get('status')}`")
        lines.append(f"- note: `{inner.get('note')}`")
        lines.append(f"- installed_versions: `{', '.join(inner.get('summary', {}).get('installed_versions', [])) if isinstance(inner.get('summary'), dict) else ''}`")
    if payload.get("host_snapshot") and isinstance(payload["host_snapshot"], dict):
        lines.extend(["", "## Host Snapshot", ""])
        host = payload["host_snapshot"]
        lines.append(f"- platform: `{host.get('platform')}`")
        lines.append(f"- arch: `{host.get('arch')}`")
        lines.append(f"- public_roots: `{', '.join(host.get('public_roots', [])) or 'none'}`")
        lines.append(f"- installed_versions: `{', '.join(host.get('installed_versions', [])) or 'none'}`")
        if host.get("default_install"):
            default_install = host["default_install"]
            if isinstance(default_install, dict):
                lines.append(f"- default_install: `{default_install.get('version')}`")
    if payload.get("blocker_signals"):
        lines.extend(["", "## Blocker Signals", ""])
        for signal in payload["blocker_signals"]:
            lines.append(f"- {signal}")
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
            "schema": "cesium.unity_linux_docker.v1",
            "generated_at": docker_runner.now(),
            "engine": args.engine,
            "native_target": args.native_target,
            "status": "dry-run",
            "container_name": container_name,
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
            "blocker_signals": [],
            "host_snapshot": {
                "platform": unity_env.describe_host().get("platform"),
                "arch": unity_env.describe_host().get("arch"),
                "public_roots": unity_env.describe_host().get("public_roots", []),
                "installed_versions": [install.get("version") for install in unity_env.describe_host().get("installs", []) if isinstance(install, dict)],
                "default_install": unity_env.describe_host().get("default_install"),
            },
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
