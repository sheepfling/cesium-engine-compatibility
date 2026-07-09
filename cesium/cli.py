#!/usr/bin/env python3
"""Top-level Cesium compatibility command wrapper."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from extensions.cesium.tools import (
    cesium_example_workflow,
    godot_linux_docker,
    prepare_cesium_source_route,
    unity_linux_docker,
    unreal_linux_docker,
    unreal_linux_lane,
)
from tools import bootstrap_local_dev, build_cesium_compatibility_packet, build_cesium_cross_platform_fix_notes, build_cesium_engine_matrix, build_cesium_execution_audit, build_cesium_planned_routes, godot_doctor, run_cesium_plugin_lanes
from tools import build_unity_native_matrix


COMMAND_MAIN = {
    "bootstrap": bootstrap_local_dev.main,
    "prepare-source-route": prepare_cesium_source_route.main,
    "example": cesium_example_workflow.main,
    "godot-doctor": godot_doctor.main,
    "unreal-linux": unreal_linux_lane.main,
    "unreal-linux-docker": unreal_linux_docker.main,
    "godot-linux-docker": godot_linux_docker.main,
    "unity-linux-docker": unity_linux_docker.main,
    "engine-matrix": build_cesium_engine_matrix.main,
    "compatibility-packet": build_cesium_compatibility_packet.main,
    "cross-platform-fix-notes": build_cesium_cross_platform_fix_notes.main,
    "planned-routes": build_cesium_planned_routes.main,
    "plugin-lanes": run_cesium_plugin_lanes.main,
    "execution-audit": build_cesium_execution_audit.main,
}


def _run_command(command: str, argv: list[str]) -> int:
    runner = COMMAND_MAIN[command]
    return runner(argv)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Prepare a local Cesium dev environment and run the quick check")
    bootstrap.add_argument("--deps-prefix", type=Path, default=None)
    bootstrap.add_argument("--work-root", type=Path, default=None)
    bootstrap.add_argument("--skip-install", action="store_true")
    bootstrap.add_argument("--prepare-only", action="store_true")
    bootstrap.add_argument("dev_check_args", nargs=argparse.REMAINDER, default=[])

    prep = subparsers.add_parser("prepare-source-route", help="Prepare the public Cesium source-route checkouts")
    prep.add_argument("args", nargs=argparse.REMAINDER)

    example = subparsers.add_parser("example", help="Run the Cesium example workflow wrapper")
    example.add_argument("args", nargs=argparse.REMAINDER)

    godot_doctor = subparsers.add_parser("godot-doctor", help="Run the Godot example doctor lane")
    godot_doctor.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    godot_doctor.add_argument("--format", choices=("text", "json"), default="text")

    unreal_linux = subparsers.add_parser("unreal-linux", help="Inspect or report on the Unreal Linux lane")
    unreal_linux.add_argument("args", nargs=argparse.REMAINDER)

    unreal_linux_docker = subparsers.add_parser("unreal-linux-docker", help="Run the Unreal Linux lane inside Docker")
    unreal_linux_docker.add_argument("args", nargs=argparse.REMAINDER)

    godot_linux_docker = subparsers.add_parser("godot-linux-docker", help="Run the Godot Linux lane inside Docker")
    godot_linux_docker.add_argument("args", nargs=argparse.REMAINDER)

    unity_linux_docker = subparsers.add_parser("unity-linux-docker", help="Run the Unity Linux lane inside Docker")
    unity_linux_docker.add_argument("args", nargs=argparse.REMAINDER)

    engine_matrix = subparsers.add_parser("engine-matrix", help="Build the cross-engine Cesium matrix report")
    engine_matrix.add_argument("--json-out", type=Path, default=None)
    engine_matrix.add_argument("--md-out", type=Path, default=None)

    unity_native_matrix = subparsers.add_parser("unity-native-matrix", help="Build the Unity native target matrix report")
    unity_native_matrix.add_argument("--json-out", type=Path, default=None)
    unity_native_matrix.add_argument("--md-out", type=Path, default=None)

    compat_packet = subparsers.add_parser("compatibility-packet", help="Build the combined Cesium compatibility packet")
    compat_packet.add_argument("--json-out", type=Path, default=None)
    compat_packet.add_argument("--md-out", type=Path, default=None)

    fix_notes = subparsers.add_parser("cross-platform-fix-notes", help="Build the reviewer-facing cross-platform fix notes")
    fix_notes.add_argument("--json-out", type=Path, default=None)
    fix_notes.add_argument("--md-out", type=Path, default=None)

    planned_routes = subparsers.add_parser("planned-routes", help="Build the cross-platform planned routes packet")
    planned_routes.add_argument("--json-out", type=Path, default=None)
    planned_routes.add_argument("--md-out", type=Path, default=None)

    plugin_lanes = subparsers.add_parser("plugin-lanes", help="Run the Cesium plugin lane bundle")
    plugin_lanes.add_argument("--lanes", nargs="+", default=["all"])
    plugin_lanes.add_argument("--parallel", action="store_true")
    plugin_lanes.add_argument("--dry-run", action="store_true")
    plugin_lanes.add_argument("--json-out", type=Path, default=None)
    plugin_lanes.add_argument("--md-out", type=Path, default=None)
    plugin_lanes.add_argument("--log-dir", type=Path, default=None)

    execution_audit = subparsers.add_parser("execution-audit", help="Audit which Cesium build lanes are runnable on this host")
    execution_audit.add_argument("--json-out", type=Path, default=None)
    execution_audit.add_argument("--md-out", type=Path, default=None)

    args, extras = parser.parse_known_args(argv)
    passthrough_commands = {
        "prepare-source-route",
        "example",
        "godot-doctor",
        "unreal-linux",
        "unreal-linux-docker",
        "godot-linux-docker",
        "unity-linux-docker",
        "engine-matrix",
        "compatibility-packet",
        "cross-platform-fix-notes",
        "planned-routes",
        "unity-native-matrix",
    }
    if args.command in passthrough_commands:
        tail = list(getattr(args, "args", []))
        if extras:
            tail.extend(extras)
        args.args = tail
        return args
    if args.command == "bootstrap" and extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")
    if extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "bootstrap":
        forwarded: list[str] = []
        if args.deps_prefix is not None:
            forwarded.extend(["--deps-prefix", str(args.deps_prefix)])
        if args.work_root is not None:
            forwarded.extend(["--work-root", str(args.work_root)])
        if args.skip_install:
            forwarded.append("--skip-install")
        if args.prepare_only:
            forwarded.append("--prepare-only")
        forwarded.extend(args.dev_check_args)
        return _run_command("bootstrap", forwarded)
    if args.command == "prepare-source-route":
        return _run_command("prepare-source-route", args.args)
    if args.command == "example":
        return _run_command("example", args.args)
    if args.command == "godot-doctor":
        return _run_command("godot-doctor", ["--native-target", args.native_target, "--format", args.format])
    if args.command == "unreal-linux":
        return _run_command("unreal-linux", args.args)
    if args.command == "unreal-linux-docker":
        return _run_command("unreal-linux-docker", args.args)
    if args.command == "godot-linux-docker":
        return _run_command("godot-linux-docker", args.args)
    if args.command == "unity-linux-docker":
        return _run_command("unity-linux-docker", args.args)
    if args.command == "engine-matrix":
        forwarded: list[str] = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return _run_command("engine-matrix", forwarded)
    if args.command == "unity-native-matrix":
        forwarded = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return build_unity_native_matrix.main(forwarded)
    if args.command == "compatibility-packet":
        forwarded: list[str] = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return _run_command("compatibility-packet", forwarded)
    if args.command == "cross-platform-fix-notes":
        forwarded: list[str] = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return _run_command("cross-platform-fix-notes", forwarded)
    if args.command == "planned-routes":
        forwarded: list[str] = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return _run_command("planned-routes", forwarded)
    if args.command == "plugin-lanes":
        forwarded: list[str] = ["--lanes", *args.lanes]
        if args.parallel:
            forwarded.append("--parallel")
        if args.dry_run:
            forwarded.append("--dry-run")
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        if args.log_dir is not None:
            forwarded.extend(["--log-dir", str(args.log_dir)])
        return _run_command("plugin-lanes", forwarded)
    if args.command == "execution-audit":
        forwarded: list[str] = []
        if args.json_out is not None:
            forwarded.extend(["--json-out", str(args.json_out)])
        if args.md_out is not None:
            forwarded.extend(["--md-out", str(args.md_out)])
        return _run_command("execution-audit", forwarded)
    raise SystemExit(f"Unknown command: {args.command}")
