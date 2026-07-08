#!/usr/bin/env python3
"""Cesium example-project workflow wrapper for this repository."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROUTE_ROOT = ROOT / "external" / "cesium"
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "reports" / "cesium_examples"

ENGINE_SPECS: dict[str, dict[str, object]] = {
    "unreal": {
        "label": "Cesium Unreal Example",
        "preferred_version": "5.7",
        "source_checkout": SOURCE_ROUTE_ROOT / "cesium-unreal",
        "sample_checkout": SOURCE_ROUTE_ROOT / "cesium-unreal-samples",
        "sample_plugin_bridge": SOURCE_ROUTE_ROOT / "cesium-unreal-samples" / "Plugins" / "cesium-unreal",
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject",
    },
    "unity": {
        "label": "Cesium Unity Example",
        "preferred_version": "6000.5",
        "source_checkout": SOURCE_ROUTE_ROOT / "cesium-unity",
        "sample_checkout": None,
        "sample_plugin_bridge": None,
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "ProjectSettings" / "ProjectVersion.txt",
    },
    "godot": {
        "label": "Cesium Godot Example",
        "preferred_version": "4.7",
        "source_checkout": SOURCE_ROUTE_ROOT / "3D-Tiles-For-Godot",
        "sample_checkout": None,
        "sample_plugin_bridge": None,
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample" / "project.godot",
    },
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _workflow_commands(engine: str) -> dict[str, str]:
    return {
        "prepare_source_route": "python extensions/cesium/tools/prepare_cesium_source_route.py",
        "discover": f"python extensions/cesium/tools/cesium_example_workflow.py discover --engine {engine}",
        "doctor": f"python extensions/cesium/tools/cesium_example_workflow.py doctor --engine {engine}",
        "report": f"python extensions/cesium/tools/cesium_example_workflow.py report --engine {engine}",
        "full": f"python extensions/cesium/tools/cesium_example_workflow.py full --engine {engine}",
    }


def _check_path(name: str, path: Path | None, *, required: bool) -> dict[str, object]:
    if path is None:
        return {"name": name, "status": "unsupported" if not required else "fail", "detail": "not applicable"}
    if path.is_dir():
        return {"name": name, "status": "ok", "detail": str(path)}
    if path.is_file():
        return {"name": name, "status": "ok", "detail": str(path)}
    return {"name": name, "status": "warn" if not required else "fail", "detail": f"missing: {path}"}


def discover_payload(engine: str) -> dict[str, object]:
    spec = ENGINE_SPECS[engine]
    return {
        "schema": "cesium.example_lane_discovery.v1",
        "generated_at": _now(),
        "engine": engine,
        "label": spec["label"],
        "preferred_version": spec["preferred_version"],
        "source_route_root": str(SOURCE_ROUTE_ROOT),
        "source_checkout": _display_path(Path(spec["source_checkout"])),
        "sample_checkout": _display_path(Path(spec["sample_checkout"])) if spec["sample_checkout"] else None,
        "example_root": _display_path(Path(spec["example_root"])),
        "project_marker": _display_path(Path(spec["project_marker"])),
        "workflow_commands": _workflow_commands(engine),
    }


def doctor_payload(engine: str) -> dict[str, object]:
    spec = ENGINE_SPECS[engine]
    source_checkout = Path(spec["source_checkout"])
    sample_checkout = spec["sample_checkout"]
    sample_plugin_bridge = spec.get("sample_plugin_bridge")
    example_root = Path(spec["example_root"])
    project_marker = Path(spec["project_marker"])

    checks = [
        _check_path("source_route_root", SOURCE_ROUTE_ROOT, required=True),
        _check_path("source_checkout", source_checkout, required=True),
        _check_path("example_root", example_root, required=True),
        _check_path("project_marker", project_marker, required=True),
    ]
    if engine == "unreal":
        checks.append(_check_path("sample_checkout", Path(sample_checkout) if sample_checkout else None, required=False))
        checks.append(_check_path("sample_plugin_bridge", Path(sample_plugin_bridge) if sample_plugin_bridge else None, required=True))

    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    status = "ok" if not failures else "needs-attention"
    next_steps: list[str] = []
    if not SOURCE_ROUTE_ROOT.is_dir():
        next_steps.append("Run `python extensions/cesium/tools/prepare_cesium_source_route.py` to create the public Cesium checkouts.")
    if not source_checkout.is_dir():
        next_steps.append(f"Prepare the {engine} source checkout before treating the example lane as green.")
    if not example_root.is_dir():
        next_steps.append(f"Restore the example scaffold under {_display_path(example_root)}.")
    if not project_marker.is_file():
        next_steps.append(f"Restore the project marker under {_display_path(project_marker)}.")
    if engine == "unreal" and sample_checkout is not None and not Path(sample_checkout).is_dir():
        next_steps.append("Fetch the Cesium Unreal samples checkout for the richer Unreal example lane.")
    if engine == "unreal" and sample_plugin_bridge is not None and not Path(sample_plugin_bridge).exists():
        next_steps.append("Expose the Cesium Unreal plugin inside the samples checkout at Plugins/cesium-unreal.")

    return {
        "schema": "cesium.example_lane_doctor.v1",
        "generated_at": _now(),
        "engine": engine,
        "label": spec["label"],
        "preferred_version": spec["preferred_version"],
        "source_route_root": str(SOURCE_ROUTE_ROOT),
        "source_checkout": str(source_checkout),
        "sample_checkout": str(sample_checkout) if sample_checkout is not None else None,
        "sample_plugin_bridge": str(sample_plugin_bridge) if sample_plugin_bridge is not None else None,
        "example_root": str(example_root),
        "project_marker": str(project_marker),
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "next_steps": next_steps,
        "workflow_commands": _workflow_commands(engine),
    }


def report_payload(engine: str) -> dict[str, object]:
    doctor = doctor_payload(engine)
    workflow = dict(doctor["workflow_commands"])
    return {
        "mode": "report",
        **doctor,
        "schema": "cesium.example_lane_report.v1",
        "readiness": {
            "source_route_ready": doctor["source_checkout"] is not None and Path(str(doctor["source_checkout"])).is_dir(),
            "example_scaffold_ready": Path(str(doctor["example_root"])).is_dir() and Path(str(doctor["project_marker"])).is_file(),
        },
        "summary": {
            "overall_status": doctor["status"],
            "prepare_source_route": workflow["prepare_source_route"],
            "example_lane_ready": doctor["status"] == "ok",
        },
    }


def full_payload(engine: str) -> dict[str, object]:
    report = report_payload(engine)
    workflow = dict(report["workflow_commands"])
    return {
        **report,
        "schema": "cesium.example_lane_full.v1",
        "mode": "full",
        "execution_plan": [
            workflow["prepare_source_route"],
            workflow["doctor"],
            workflow["report"],
        ],
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        f"# {payload['label']}",
        "",
        f"- engine: `{payload['engine']}`",
        f"- status: `{payload['status']}`",
        f"- preferred_version: `{payload.get('preferred_version', '')}`",
        f"- source_route_root: `{payload.get('source_route_root', '')}`",
        f"- source_checkout: `{payload.get('source_checkout', '')}`",
        f"- example_root: `{payload.get('example_root', '')}`",
    ]
    if payload.get("sample_checkout") is not None:
        lines.append(f"- sample_checkout: `{payload.get('sample_checkout') or 'missing'}`")
    if payload.get("sample_plugin_bridge") is not None:
        lines.append(f"- sample_plugin_bridge: `{payload.get('sample_plugin_bridge') or 'missing'}`")
    if payload.get("project_marker") is not None:
        lines.append(f"- project_marker: `{payload.get('project_marker') or 'missing'}`")
    if payload.get("checks"):
        lines.extend(["", "## Checks", ""])
        for check in payload["checks"]:
            lines.append(f"- `{check['name']}`: `{check['status']}`")
            lines.append(f"  detail: `{check['detail']}`")
    if payload.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in payload["next_steps"]:
            lines.append(f"- {step}")
    if payload.get("workflow_commands"):
        lines.extend(["", "## Workflow Commands", ""])
        for key, value in payload["workflow_commands"].items():
            lines.append(f"- `{key}`: `{value}`")
    if payload.get("execution_plan"):
        lines.extend(["", "## Full Plan", ""])
        for command in payload["execution_plan"]:
            lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def print_text(payload: dict[str, object]) -> None:
    print(payload["label"])
    print(f"status: {payload['status']}")
    print(f"preferred_version: {payload.get('preferred_version', '')}")
    print(f"source_route_root: {payload.get('source_route_root', '')}")
    print(f"source_checkout: {payload.get('source_checkout', '')}")
    print(f"example_root: {payload.get('example_root', '')}")
    if payload.get("sample_checkout") is not None:
        print(f"sample_checkout: {payload.get('sample_checkout') or 'missing'}")
    if payload.get("sample_plugin_bridge") is not None:
        print(f"sample_plugin_bridge: {payload.get('sample_plugin_bridge') or 'missing'}")
    if payload.get("project_marker") is not None:
        print(f"project_marker: {payload.get('project_marker') or 'missing'}")
    print("checks:")
    for check in payload.get("checks", []):
        print(f"  - {check['name']}: {check['status']} ({check['detail']})")
    if payload.get("next_steps"):
        print("next:")
        for step in payload["next_steps"]:
            print(f"  - {step}")
    if payload.get("workflow_commands"):
        print("workflow_commands:")
        for key, value in payload["workflow_commands"].items():
            print(f"  - {key}: {value}")
    if payload.get("execution_plan"):
        print("execution_plan:")
        for command in payload["execution_plan"]:
            print(f"  - {command}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("discover", "doctor", "report", "full"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--engine", choices=sorted(ENGINE_SPECS), required=True)
        sub.add_argument("--format", choices=("text", "json"), default="text")
        if name in {"report", "full"}:
            sub.add_argument("--json-out", type=Path)
            sub.add_argument("--md-out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "discover":
        payload = discover_payload(args.engine)
    elif args.command == "doctor":
        payload = doctor_payload(args.engine)
    elif args.command == "report":
        payload = report_payload(args.engine)
        json_out = args.json_out or (DEFAULT_REPORT_DIR / f"{args.engine}.json")
        md_out = args.md_out or (DEFAULT_REPORT_DIR / f"{args.engine}.md")
        write_report(payload, json_out, md_out)
    elif args.command == "full":
        payload = full_payload(args.engine)
        json_out = args.json_out or (DEFAULT_REPORT_DIR / f"{args.engine}_full.json")
        md_out = args.md_out or (DEFAULT_REPORT_DIR / f"{args.engine}_full.md")
        write_report(payload, json_out, md_out)
    else:
        raise SystemExit(f"Unknown command: {args.command}")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print_text(payload)
    return 0 if payload.get("status", "ok") in {"ok", "pass", "dry-run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
