#!/usr/bin/env python3
"""Run the Cesium lane set with stable presets and rerunnable reports."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shlex
import subprocess
import sys
import threading
from typing import Any
from extensions.cesium.tools import cesium_example_workflow, unreal_linux_lane
from tools import unity_env


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_lane_runner"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_plugin_lanes.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_plugin_lanes.md"
DEFAULT_LOG_DIR = DEFAULT_OUT_DIR / "logs"


def preferred_python() -> str:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable or "python"


def _py(command: str) -> str:
    if not command.startswith("python "):
        return command
    return f"{shlex.quote(preferred_python())} {command[len('python '):]}"


@dataclass(frozen=True)
class LaneTask:
    id: str
    label: str
    commands: tuple[str, ...]
    artifacts: tuple[str, ...]
    accepted_returncodes: tuple[int, ...] = (0,)


@dataclass(frozen=True)
class LaneSpec:
    id: str
    label: str
    artifact_namespace: str
    lane_kind: str
    commands_source: str
    parallel_safe: bool
    tasks: tuple[LaneTask, ...]


def _unreal_linux_version_rows() -> list[dict[str, object]]:
    report = unreal_linux_lane.report_payload()
    rows = report.get("version_matrix")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _unity_install_rows() -> list[dict[str, object]]:
    installs = unity_env.discover_installs()
    if installs:
        return [install.to_dict() for install in installs]
    fallback = cesium_example_workflow.report_payload("unity")
    rows = fallback.get("compatibility_tracking", {}).get("version_matrix", [])
    if isinstance(rows, list):
        return [{"version": str(row.get("version") or "6000.5.0f1"), "install_root": "", "editor_path": None} for row in rows if isinstance(row, dict)]
    return [{"version": "6000.5.0f1", "install_root": "", "editor_path": None}]


def _unity_example_build_rows() -> list[dict[str, object]]:
    return _unity_install_rows()


def _godot_version_rows(native_target: str) -> list[dict[str, object]]:
    payload = cesium_example_workflow.report_payload("godot", native_target=native_target)
    tracking = payload.get("compatibility_tracking")
    if not isinstance(tracking, dict):
        return []
    rows = tracking.get("windows_version_matrix" if native_target == "windows" else "linux_version_matrix")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _unreal_linux_lane_spec() -> LaneSpec:
    version_rows = _unreal_linux_version_rows() or [{"engine_version": "5.7"}, {"engine_version": "5.8"}]
    tasks: list[LaneTask] = []
    for row in version_rows:
        version = str(row.get("engine_version") or row.get("version") or "unknown")
        build_plan_command = _py(
            f"python -m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version {version}"
        )
        build_command = _py(f"python -m extensions.cesium.tools.unreal_linux_docker build --engine-version {version}")
        tasks.append(
            LaneTask(
                id=f"unreal-linux-build-plan-{version.replace('.', '_')}",
                label=f"Unreal Linux Build Plan {version}",
                commands=(build_plan_command,),
                artifacts=(),
            )
        )
        tasks.append(
            LaneTask(
                id=f"unreal-linux-build-{version.replace('.', '_')}",
                label=f"Unreal Linux Build {version}",
                commands=(build_command,),
                artifacts=(
                    f"artifacts/reports/unreal_linux_docker/cesium_{version.replace('.', '_')}_linux_docker.json",
                    f"artifacts/reports/unreal_linux_docker/cesium_{version.replace('.', '_')}_linux_docker.md",
                ),
            )
        )
    return LaneSpec(
        "unreal-linux-docker",
        "Cesium Unreal Linux Docker",
        "unreal_linux",
        "docker",
        "matrix:unreal_linux_version_rows",
        False,
        tuple(tasks),
    )


def _unity_host_lane_spec(*, native_target: str = "windows", lane_id: str = "unity-host") -> LaneSpec:
    installs = _unity_install_rows()
    tasks: list[LaneTask] = []
    for install in installs:
        version = str(install.get("version") or "6000.5.0f1")
        version_slug = version.replace(".", "_").replace("-", "_")
        out_dir = f"artifacts/reports/unity_host_{version_slug}"
        host_label = f"local-host-{version_slug}"
        tasks.append(
            LaneTask(
                id=f"unity-capture-{version_slug}",
                label=f"Unity Host Capture {version}",
                commands=(f"cesium-capture-unity-host-report --unity-version {version} --native-target {native_target} --out-dir {out_dir}",),
                artifacts=(
                    f"{out_dir}/unity_host_report.json",
                    f"{out_dir}/unity_host_report.md",
                ),
            )
        )
        tasks.append(
            LaneTask(
                id=f"unity-stage-{version_slug}",
                label=f"Unity Host Stage {version}",
                commands=(f"cesium-stage-unity-host-report --source-dir {out_dir} --host-label {host_label} --overwrite",),
                artifacts=(
                    f"artifacts/verification_reports/unity_hosts/{host_label}/unity_host_report_manifest.json",
                    f"artifacts/verification_reports/unity_hosts/{host_label}/unity_host_report_manifest.md",
                ),
            )
        )
    tasks.append(
        LaneTask(
            id="unity-export",
            label="Unity Host Export",
            commands=("cesium-export-unity-host-handoff",),
            artifacts=(
                "dist/unity_host_handoff/cesium-unity-host-handoff.zip",
                "dist/unity_host_handoff/cesium-unity-host-handoff.zip.sha256",
            ),
        )
    )
    return LaneSpec(
        lane_id,
        f"Cesium Unity Host Handoff ({native_target})",
        f"unity_host_{native_target}",
        "host",
        "matrix:unity_install_rows",
        True,
        tuple(tasks),
    )


def _unity_linux_docker_lane_spec() -> LaneSpec:
    installs = _unity_install_rows()
    tasks: list[LaneTask] = []
    for install in installs:
        version = str(install.get("version") or "6000.5.0f1")
        version_slug = version.replace(".", "_").replace("-", "_")
        command = (
            _py("python -m extensions.cesium.tools.unity_linux_docker ")
            + (
                "--native-target linux "
                "--docker-log-mode tee "
                "--log-tail-lines 120 "
                "--timeout-seconds 900 "
                "--preserve "
                f"--preserve-label unity-linux-{version_slug}"
            )
        )
        tasks.append(
            LaneTask(
                id=f"unity-linux-docker-{version_slug}",
                label=f"Unity Linux Docker {version}",
                commands=(command,),
                artifacts=(
                    "artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json",
                    "artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.md",
                ),
            )
        )
    return LaneSpec(
        "unity-host-linux-docker",
        "Cesium Unity Linux/Docker Handoff",
        "unity_host_linux",
        "host",
        "matrix:unity_install_rows",
        True,
        tuple(tasks),
    )


def _unity_example_build_lane_spec() -> LaneSpec:
    installs = _unity_example_build_rows()
    tasks: list[LaneTask] = []
    for install in installs:
        version = str(install.get("version") or "6000.5.0f1")
        version_slug = version.replace(".", "_").replace("-", "_")
        out_dir = f"artifacts/reports/unity_example_build/{version_slug}"
        command = _py(
            "python -m tools.build_unity_example "
            f"--unity-version {version} --build-target windows --out-dir {out_dir}"
        )
        tasks.append(
            LaneTask(
                id=f"unity-example-build-{version_slug}",
                label=f"Unity Example Build {version}",
                commands=(command,),
                artifacts=(
                    f"{out_dir}/unity_example_build_{version_slug}_windows.json",
                    f"{out_dir}/unity_example_build_{version_slug}_windows.md",
                ),
            )
        )
    return LaneSpec(
        "unity-example-build",
        "Cesium Unity Example Build",
        "unity_example_build",
        "host",
        "matrix:unity_install_rows",
        True,
        tuple(tasks),
    )


def _godot_lane_spec(native_target: str) -> LaneSpec:
    rows = _godot_version_rows(native_target) or [{"version": "4.7"}]
    tasks: list[LaneTask] = []
    for row in rows:
        version = str(row.get("version") or "4.7")
        version_slug = version.replace(".", "_").replace("-", "_")
        tasks.append(
            LaneTask(
                id=f"godot-report-{native_target}-{version_slug}",
                label=f"Godot {native_target.title()} Report {version}",
                commands=(f"cesium-example report --engine godot --native-target {native_target}",),
                artifacts=(
                    f"artifacts/reports/cesium_examples/godot-{native_target}.json",
                    f"artifacts/reports/cesium_examples/godot-{native_target}.md",
                ),
            )
        )
        if native_target == "mac":
            tasks.append(
                LaneTask(
                    id=f"godot-build-{native_target}-{version_slug}",
                    label=f"Godot {native_target.title()} Build {version}",
                    commands=(f"cesium-godot-example-build --build-target mac --godot-version {version}",),
                    artifacts=(
                        f"artifacts/reports/godot_example_build/godot_example_build_{version_slug}_mac.json",
                        f"artifacts/reports/godot_example_build/godot_example_build_{version_slug}_mac.md",
                    ),
                )
            )
    return LaneSpec(
        f"godot-host-{native_target}",
        f"Cesium Godot {native_target.title()} Host Matrix",
        "godot_host",
        "host",
        f"matrix:godot_{native_target}_version_rows",
        True,
        tuple(tasks),
    )


def _godot_linux_docker_lane_spec() -> LaneSpec:
    return LaneSpec(
        "godot-linux-docker",
        "Cesium Godot Linux Docker",
        "godot_linux_docker",
        "docker",
        "custom:godot_linux_docker",
        False,
        (
            LaneTask(
                id="godot-linux-docker-report",
                label="Godot Linux Docker Report",
                commands=(
                    _py("python -m extensions.cesium.tools.godot_linux_docker ")
                    + (
                        "--native-target linux "
                        "--docker-log-mode tee "
                        "--log-tail-lines 120 "
                        "--timeout-seconds 900 "
                        "--preserve "
                        "--preserve-label godot-linux-docker"
                    ),
                ),
                artifacts=(
                    "artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.json",
                    "artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.md",
                ),
            ),
        ),
    )


def _matrix_refresh_lane_spec() -> LaneSpec:
    return LaneSpec(
        "matrix-refresh",
        "Cesium Engine Matrix Refresh",
        "cesium_engine_matrix",
        "report",
        "custom:build_cesium_engine_matrix",
        False,
        (
            LaneTask(
                id="refresh-matrix",
                label="Refresh Cesium Engine Matrix",
                commands=("cesium-engine-matrix",),
                artifacts=(
                    "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
                    "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.md",
                ),
            ),
        ),
    )


def _execution_audit_lane_spec() -> LaneSpec:
    return LaneSpec(
        "execution-audit",
        "Cesium Execution Audit",
        "cesium_execution_audit",
        "audit",
        "custom:build_cesium_execution_audit",
        False,
        (
            LaneTask(
                id="execution-audit",
                label="Execution Audit",
                commands=("cesium-execution-audit",),
                artifacts=(
                    "artifacts/reports/cesium_execution_audit/cesium_execution_audit.json",
                    "artifacts/reports/cesium_execution_audit/cesium_execution_audit.md",
                ),
            ),
        ),
    )


def _cross_platform_planned_lane_spec() -> LaneSpec:
    planned = [
        _unreal_linux_lane_spec(),
        _unity_linux_docker_lane_spec(),
        _unity_host_lane_spec(native_target="mac", lane_id="unity-host-mac"),
        _godot_lane_spec("mac"),
    ]
    tasks = tuple(task for lane in planned for task in lane.tasks)
    return LaneSpec(
        "cross-platform-planned",
        "Cesium Cross-Platform Planned Routes",
        "cross_platform_planned",
        "bundle",
        "bundle:planned_routes",
        False,
        tasks,
    )


def lane_catalog() -> dict[str, LaneSpec]:
    return {
        "execution-audit": _execution_audit_lane_spec(),
        "cross-platform-planned": _cross_platform_planned_lane_spec(),
        "unreal-linux-docker": _unreal_linux_lane_spec(),
        "unity-host": _unity_host_lane_spec(),
        "unity-host-mac": _unity_host_lane_spec(native_target="mac", lane_id="unity-host-mac"),
        "unity-example-build": _unity_example_build_lane_spec(),
        "unity-host-linux-docker": _unity_linux_docker_lane_spec(),
        "godot-host-windows": _godot_lane_spec("windows"),
        "godot-host-linux": _godot_lane_spec("linux"),
        "godot-host-mac": _godot_lane_spec("mac"),
        "godot-linux-docker": _godot_linux_docker_lane_spec(),
        "matrix-refresh": _matrix_refresh_lane_spec(),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lanes", nargs="+", default=["all"], help="Lane ids to run, or 'all'")
    parser.add_argument("--parallel", action="store_true", help="Run compatible lanes in parallel when artifact namespaces do not overlap")
    parser.add_argument("--dry-run", action="store_true", help="Print the exact commands without executing them")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    return parser.parse_args(argv)


def resolve_lanes(selected: list[str]) -> list[LaneSpec]:
    catalog = lane_catalog()
    if selected == ["all"] or "all" in selected:
        return [catalog[lane_id] for lane_id in catalog]
    missing = [lane_id for lane_id in selected if lane_id not in catalog]
    if missing:
        raise SystemExit(f"Unknown lane ids: {', '.join(missing)}")
    return [catalog[lane_id] for lane_id in selected]


def _command_log_path(log_dir: Path, lane: LaneSpec, task: LaneTask, command_index: int) -> Path:
    return log_dir / lane.id / f"{task.id}_{command_index + 1}.log"


def _run_command(command: str, *, log_path: Path, prefix: str) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            shlex.split(command),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            print(f"[{prefix}] {line}", end="", flush=True)
        returncode = process.wait()
    return {"command": command, "log": str(log_path), "returncode": returncode}


def run_lane(lane: LaneSpec, *, log_dir: Path, dry_run: bool) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    task_rows: list[dict[str, Any]] = []
    status = "pass"
    for task in lane.tasks:
        command_rows: list[dict[str, Any]] = []
        if dry_run:
            for command_index, command in enumerate(task.commands):
                command_rows.append(
                    {
                        "command": command,
                        "log": str(_command_log_path(log_dir, lane, task, command_index)),
                        "returncode": None,
                    }
                )
            task_rows.append(
                {
                    "id": task.id,
                    "label": task.label,
                    "status": "dry-run",
                    "commands": command_rows,
                    "artifacts": list(task.artifacts),
                }
            )
            continue
        task_status = "pass"
        for command_index, command in enumerate(task.commands):
            row = _run_command(
                command,
                log_path=_command_log_path(log_dir, lane, task, command_index),
                prefix=f"{lane.id}:{task.id}",
            )
            command_rows.append(row)
            if row["returncode"] not in task.accepted_returncodes:
                task_status = "fail"
                status = "fail"
                break
        task_rows.append(
            {
                "id": task.id,
                "label": task.label,
                "status": task_status,
                "commands": command_rows,
                "artifacts": list(task.artifacts),
            }
        )
        if task_status == "fail":
            break
    completed_at = datetime.now(UTC).isoformat()
    if dry_run:
        status = "dry-run"
    return {
        "id": lane.id,
        "label": lane.label,
        "lane_kind": lane.lane_kind,
        "artifact_namespace": lane.artifact_namespace,
        "commands_source": lane.commands_source,
        "parallel_safe": lane.parallel_safe,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "tasks": task_rows,
    }


def _run_parallel_group(lanes: list[LaneSpec], *, log_dir: Path, dry_run: bool) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    print_lock = threading.Lock()

    def run_one(lane: LaneSpec) -> dict[str, Any]:
        with print_lock:
            print(f"[lane] starting {lane.id}", flush=True)
        return run_lane(lane, log_dir=log_dir, dry_run=dry_run)

    with ThreadPoolExecutor(max_workers=len(lanes)) as executor:
        future_map = {executor.submit(run_one, lane): lane.id for lane in lanes}
        for future in as_completed(future_map):
            lane_id = future_map[future]
            results[lane_id] = future.result()
    return [results[lane.id] for lane in lanes]


def execute_lanes(lanes: list[LaneSpec], *, log_dir: Path, dry_run: bool, parallel: bool) -> list[dict[str, Any]]:
    if dry_run or not parallel:
        return [run_lane(lane, log_dir=log_dir, dry_run=dry_run) for lane in lanes]

    results: list[dict[str, Any]] = []
    pending: list[LaneSpec] = []
    active_namespaces: set[str] = set()

    def flush_pending() -> None:
        nonlocal pending, active_namespaces, results
        if not pending:
            return
        if len(pending) == 1:
            results.append(run_lane(pending[0], log_dir=log_dir, dry_run=False))
        else:
            results.extend(_run_parallel_group(pending, log_dir=log_dir, dry_run=False))
        pending = []
        active_namespaces = set()

    for lane in lanes:
        if not lane.parallel_safe or lane.artifact_namespace in active_namespaces:
            flush_pending()
            results.append(run_lane(lane, log_dir=log_dir, dry_run=False))
            continue
        pending.append(lane)
        active_namespaces.add(lane.artifact_namespace)
    flush_pending()
    return results


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lanes = resolve_lanes(args.lanes)
    lane_results = execute_lanes(
        lanes,
        log_dir=args.log_dir.expanduser().resolve(),
        dry_run=args.dry_run,
        parallel=args.parallel,
    )
    statuses = [row["status"] for row in lane_results]
    if statuses and all(status == "pass" for status in statuses):
        overall_status = "pass"
    elif any(status == "fail" for status in statuses):
        overall_status = "fail"
    else:
        overall_status = "dry-run"
    return {
        "schema": "cesium.plugin_lane_runner.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": overall_status,
        "parallel_requested": bool(args.parallel),
        "dry_run": bool(args.dry_run),
        "selected_lanes": [lane.id for lane in lanes],
        "log_dir": str(args.log_dir.expanduser().resolve()),
        "lanes": lane_results,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Plugin Lane Runner",
        "",
        f"- overall_status: `{payload['overall_status']}`",
        f"- dry_run: `{payload['dry_run']}`",
        f"- parallel_requested: `{payload['parallel_requested']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- log_dir: `{payload['log_dir']}`",
        "",
        "## Lanes",
        "",
        "| Lane | Status | Kind | Source |",
        "| --- | --- | --- | --- |",
    ]
    for lane in payload.get("lanes", []):
        lines.append(
            f"| `{lane['id']}` | `{lane['status']}` | `{lane['lane_kind']}` | `{lane['commands_source']}` |"
        )
    bundle_lanes = [lane for lane in payload.get("lanes", []) if lane.get("lane_kind") == "bundle"]
    if bundle_lanes:
        lines.extend(["", "## Planned Route Bundles", ""])
        for lane in bundle_lanes:
            lines.append(f"### `{lane['id']}`")
            lines.append("")
            for task in lane.get("tasks", []):
                lines.append(f"- `{task['id']}`: `{task['status']}`")
                for command in task.get("commands", []):
                    lines.append(f"  - `{command['command']}`")
    lines.extend(["", "## Commands", ""])
    for lane in payload.get("lanes", []):
        lines.append(f"- `{lane['id']}`")
        for task in lane.get("tasks", []):
            lines.append(f"  - `{task['id']}`: `{task['status']}`")
            for command in task.get("commands", []):
                lines.append(f"    - `{command['command']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["overall_status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
