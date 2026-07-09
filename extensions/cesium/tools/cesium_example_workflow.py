#!/usr/bin/env python3
"""Cesium example-project workflow wrapper for this repository."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from extensions.cesium.tools.engine_root_discovery import (
    discover_godot_linux_versions,
    discover_godot_windows_versions,
    public_engine_search_roots,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROUTE_ROOT = ROOT / "external" / "cesium"
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "reports" / "cesium_examples"


def _godot_native_lane_commands() -> dict[str, dict[str, str]]:
    return {
        "windows": {
            "target": "windows",
            "host_note": "Windows remains the pinned baseline lane at 4.7.",
            "command": "cesium-example doctor --engine godot --native-target windows",
        },
        "linux": {
            "target": "linux",
            "host_note": "Linux should be exercised as a separate native import/open lane.",
            "command": "cesium-example doctor --engine godot --native-target linux",
        },
        "mac": {
            "target": "mac",
            "host_note": "macOS should be exercised as a separate native import/open lane.",
            "command": "cesium-example doctor --engine godot --native-target mac",
        },
    }


def _godot_windows_version_matrix() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in discover_godot_windows_versions():
        rows.append(
            {
                "version": item["version"],
                "lane_role": "current baseline" if item["version"] == "4.7" else ("forward verification" if item["version"].startswith("4.8") else "compatibility evidence"),
                "platform": item["platform"],
                "root": str(item["root"]),
                "executable": str(item["executable"]),
                "console_executable": str(item["console_executable"]),
            }
        )
    return rows


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _unity_project_version() -> str | None:
    version_file = ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.is_file():
        return None
    for line in version_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return None


def _unity_package_dependencies() -> dict[str, str]:
    manifest = ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "Packages" / "manifest.json"
    payload = _read_json(manifest) or {}
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in dependencies.items():
        if isinstance(key, str) and isinstance(value, str):
            result[key] = value
    return dict(sorted(result.items()))


def _unity_version_matrix() -> list[dict[str, object]]:
    version = _unity_project_version() or "6000.5.0f1"
    dependencies = _unity_package_dependencies()
    return [
        {
            "version": version,
            "lane_role": "current example-project version",
            "proof_lane_version": "6000.5.0f1",
            "package_count": len(dependencies),
            "package_dependencies": dependencies,
            "project_version_file": str(
                ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "ProjectSettings" / "ProjectVersion.txt"
            ),
            "manifest_file": str(
                ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "Packages" / "manifest.json"
            ),
        }
    ]


def _godot_linux_version_lane_role(version: str) -> str:
    if version == "4.7":
        return "current baseline"
    if version == "4.6.3-stable":
        return "compatibility evidence"
    if version == "4.7.1-rc1":
        return "release-candidate evidence"
    if version.startswith("4.8"):
        return "forward verification"
    return "compatibility evidence"


def _godot_linux_version_matrix() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in discover_godot_linux_versions():
        version = str(item["version"])
        rows.append(
            {
                "version": version,
                "lane_role": _godot_linux_version_lane_role(version),
                "platform": item["platform"],
                "root": str(item["root"]),
                "executable": str(item["executable"]),
                "console_executable": str(item["console_executable"]),
            }
        )
    return rows


def _unreal_version_matrix() -> list[dict[str, object]]:
    return [
        {
            "version": "5.7",
            "lane_role": "current baseline",
            "focus": "Confirm the current Windows-facing Unreal 5.7 proof lane before widening Linux or samples coverage.",
        },
        {
            "version": "5.8",
            "lane_role": "forward verification",
            "focus": "Confirm the next Unreal 5.x release stays compatible with the repo-owned example and source-route notes.",
        },
    ]


def _compatibility_tracking(engine: str) -> dict[str, object] | None:
    spec = ENGINE_SPECS[engine]
    tracking = spec.get("compatibility_tracking")
    if tracking is None:
        return None
    tracking_copy = dict(tracking)
    if engine == "unity":
        tracking_copy["version_matrix"] = _unity_version_matrix()
    if engine == "godot":
        tracking_copy["windows_version_matrix"] = _godot_windows_version_matrix()
        tracking_copy["linux_version_matrix"] = _godot_linux_version_matrix()
    return tracking_copy


ENGINE_SPECS: dict[str, dict[str, object]] = {
    "unreal": {
        "label": "Cesium Unreal Example",
        "preferred_version": "5.7",
        "source_checkout": SOURCE_ROUTE_ROOT / "cesium-unreal",
        "sample_checkout": SOURCE_ROUTE_ROOT / "cesium-unreal-samples",
        "sample_plugin_bridge": SOURCE_ROUTE_ROOT / "cesium-unreal-samples" / "Plugins" / "cesium-unreal",
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject",
        "compatibility_tracking": {
            "supported_native_targets": ["windows", "linux", "mac"],
            "version_matrix": _unreal_version_matrix(),
            "linux_lane": "Track Linux as a separate host/toolchain proof lane, not as a Windows source-route surrogate.",
            "forward_compatibility": "Track Linux build, package, and editor-open drift when the lane is exercised on newer Unreal 5.x hosts.",
            "backward_compatibility": "Track Linux source, toolchain, or dependency drift when the lane is exercised on older Unreal 5.x hosts.",
            "evidence_note": "Record exact Unreal version, Linux host image, toolchain, and failure mode in docs/CESIUM_UNREAL_LINUX_NOTES.md before widening the lane.",
            "public_search_roots": [str(path) for path in public_engine_search_roots()["unreal"]],
        },
    },
    "unity": {
        "label": "Cesium Unity Example",
        "preferred_version": "6000.5",
        "source_checkout": SOURCE_ROUTE_ROOT / "cesium-unity",
        "sample_checkout": None,
        "sample_plugin_bridge": None,
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "ProjectSettings" / "ProjectVersion.txt",
        "compatibility_tracking": {
            "pinned_editor": "6000.5.0f1",
            "example_project_version": _unity_project_version() or "6000.5.0f1",
            "native_target": "windows",
            "supported_native_targets": ["windows", "linux", "mac"],
            "native_lane_commands": {
                "windows": {
                    "target": "windows",
                    "host_note": "Windows is the pinned baseline lane for the Unity proof path.",
                    "command": "cesium-example doctor --engine unity --native-target windows",
                },
                "linux": {
                    "target": "linux",
                    "host_note": "Linux should be exercised as a separate native import/open lane.",
                    "command": "cesium-example doctor --engine unity --native-target linux",
                },
                "mac": {
                    "target": "mac",
                    "host_note": "macOS should be exercised as a separate native import/open lane.",
                    "command": "cesium-example doctor --engine unity --native-target mac",
                },
            },
            "forward_compatibility": "Track any API or package drift when the lane is exercised on newer 6000.x editors.",
            "backward_compatibility": "Track any API, import, or serialized-project drift when the lane is exercised on older 6000.x editors.",
            "evidence_note": "Record exact editor version, package revision, and failure mode in docs/CESIUM_UNITY_6000_5_FINDINGS.md before widening the lane.",
            "public_search_roots": [str(path) for path in public_engine_search_roots()["unity"]],
        },
    },
    "godot": {
        "label": "Cesium Godot Example",
        "preferred_version": "4.7",
        "source_checkout": SOURCE_ROUTE_ROOT / "3D-Tiles-For-Godot",
        "sample_checkout": None,
        "sample_plugin_bridge": None,
        "example_root": ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample",
        "project_marker": ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample" / "project.godot",
        "compatibility_tracking": {
            "pinned_editor": "4.7",
            "native_target": "windows",
            "supported_native_targets": ["windows", "linux", "mac"],
            "native_lane_commands": _godot_native_lane_commands(),
            "windows_version_matrix": _godot_windows_version_matrix(),
            "linux_version_matrix": _godot_linux_version_matrix(),
            "forward_compatibility": "Track target-specific renderer, export, or import drift when the lane is exercised on newer Godot 4.x editors.",
            "backward_compatibility": "Track target-specific import, addon, or project-format drift when the lane is exercised on older Godot 4.x editors.",
            "evidence_note": "Record exact editor version, addon revision, host OS, and failure mode in docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md before widening the lane.",
            "windows_note": "Windows remains the pinned baseline lane at 4.7 for the current proof path.",
            "linux_note": "Linux should be treated as a separate native import/open lane, not a Windows surrogate.",
            "mac_note": "macOS should be treated as a separate native import/open lane, not a Windows surrogate.",
            "public_search_roots": [str(path) for path in public_engine_search_roots()["godot"]],
        },
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
        "prepare_source_route": "cesium-prepare-source-route",
        "discover": f"cesium-example discover --engine {engine}",
        "doctor": f"cesium-example doctor --engine {engine}",
        "report": f"cesium-example report --engine {engine}",
        "full": f"cesium-example full --engine {engine}",
    }


def _godot_windows_version_lane_role(version: str) -> str:
    if version == "4.7":
        return "current baseline"
    if version == "4.6.3":
        return "compatibility evidence"
    if version == "4.7.1-rc1":
        return "release-candidate evidence"
    if version.startswith("4.8"):
        return "forward verification"
    return "compatibility evidence"


def _godot_windows_version_matrix() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in discover_godot_windows_versions():
        version = str(item["version"])
        rows.append(
            {
                "version": version,
                "lane_role": _godot_windows_version_lane_role(version),
                "platform": item["platform"],
                "root": str(item["root"]),
                "executable": str(item["executable"]),
                "console_executable": str(item["console_executable"]),
            }
        )
    return rows


def _check_path(name: str, path: Path | None, *, required: bool) -> dict[str, object]:
    if path is None:
        return {"name": name, "status": "unsupported" if not required else "fail", "detail": "not applicable"}
    if path.is_dir():
        return {"name": name, "status": "ok", "detail": str(path)}
    if path.is_file():
        return {"name": name, "status": "ok", "detail": str(path)}
    return {"name": name, "status": "warn" if not required else "fail", "detail": f"missing: {path}"}


def discover_payload(engine: str, *, native_target: str | None = None) -> dict[str, object]:
    spec = ENGINE_SPECS[engine]
    return {
        "schema": "cesium.example_lane_discovery.v1",
        "generated_at": _now(),
        "engine": engine,
        "native_target": native_target,
        "label": spec["label"],
        "preferred_version": spec["preferred_version"],
        "compatibility_tracking": _compatibility_tracking(engine),
        "source_route_root": str(SOURCE_ROUTE_ROOT),
        "source_checkout": _display_path(Path(spec["source_checkout"])),
        "sample_checkout": _display_path(Path(spec["sample_checkout"])) if spec["sample_checkout"] else None,
        "example_root": _display_path(Path(spec["example_root"])),
        "project_marker": _display_path(Path(spec["project_marker"])),
        "workflow_commands": _workflow_commands(engine),
    }


def doctor_payload(engine: str, *, native_target: str | None = None) -> dict[str, object]:
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
    if engine == "godot":
        checks.append(_check_path("windows_native_renderer", project_marker.parent / "scenes" / "Main.tscn", required=True))

    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    status = "ok" if not failures else "needs-attention"
    next_steps: list[str] = []
    if not SOURCE_ROUTE_ROOT.is_dir():
        next_steps.append("Run `cesium-prepare-source-route` to create the public Cesium checkouts.")
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
    if engine == "unreal":
        next_steps.append("Keep Unreal Linux host/toolchain evidence in docs/CESIUM_UNREAL_LINUX_NOTES.md.")
    if engine == "godot" and not (example_root / "scenes" / "Main.tscn").is_file():
        next_steps.append("Materialize the Windows-native Godot scene at scenes/Main.tscn.")
    if engine == "godot":
        next_steps.append("Keep Windows, Linux, and macOS Godot proof notes separated even though they share the same source-route checkout.")

    return {
        "schema": "cesium.example_lane_doctor.v1",
        "generated_at": _now(),
        "engine": engine,
        "native_target": native_target,
        "label": spec["label"],
        "preferred_version": spec["preferred_version"],
        "compatibility_tracking": _compatibility_tracking(engine),
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


def report_payload(engine: str, *, native_target: str | None = None) -> dict[str, object]:
    doctor = doctor_payload(engine, native_target=native_target)
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


def full_payload(engine: str, *, native_target: str | None = None) -> dict[str, object]:
    report = report_payload(engine, native_target=native_target)
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
        f"- native_target: `{payload.get('native_target') or 'default'}`",
        f"- status: `{payload['status']}`",
        f"- preferred_version: `{payload.get('preferred_version', '')}`",
        f"- source_route_root: `{payload.get('source_route_root', '')}`",
        f"- source_checkout: `{payload.get('source_checkout', '')}`",
        f"- example_root: `{payload.get('example_root', '')}`",
    ]
    if payload.get("compatibility_tracking") is not None:
        lines.extend(["", "## Compatibility Tracking", ""])
        for key, value in payload["compatibility_tracking"].items():
            lines.append(f"- `{key}`: {value}")
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


def _report_stem(engine: str, native_target: str | None) -> str:
    if engine == "godot":
        target = native_target or "windows"
        return f"{engine}-{target}"
    return engine


def print_text(payload: dict[str, object]) -> None:
    print(payload["label"])
    print(f"status: {payload['status']}")
    print(f"preferred_version: {payload.get('preferred_version', '')}")
    print(f"source_route_root: {payload.get('source_route_root', '')}")
    print(f"source_checkout: {payload.get('source_checkout', '')}")
    print(f"example_root: {payload.get('example_root', '')}")
    if payload.get("compatibility_tracking") is not None:
        print("compatibility_tracking:")
        for key, value in payload["compatibility_tracking"].items():
            print(f"  - {key}: {value}")
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
        sub.add_argument("--native-target", choices=("windows", "linux", "mac"))
        sub.add_argument("--format", choices=("text", "json"), default="text")
        if name in {"report", "full"}:
            sub.add_argument("--json-out", type=Path)
            sub.add_argument("--md-out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "discover":
        payload = discover_payload(args.engine, native_target=args.native_target)
    elif args.command == "doctor":
        payload = doctor_payload(args.engine, native_target=args.native_target)
    elif args.command == "report":
        payload = report_payload(args.engine, native_target=args.native_target)
        stem = _report_stem(args.engine, args.native_target)
        json_out = args.json_out or (DEFAULT_REPORT_DIR / f"{stem}.json")
        md_out = args.md_out or (DEFAULT_REPORT_DIR / f"{stem}.md")
        write_report(payload, json_out, md_out)
    elif args.command == "full":
        payload = full_payload(args.engine, native_target=args.native_target)
        stem = _report_stem(args.engine, args.native_target)
        json_out = args.json_out or (DEFAULT_REPORT_DIR / f"{stem}_full.json")
        md_out = args.md_out or (DEFAULT_REPORT_DIR / f"{stem}_full.md")
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
