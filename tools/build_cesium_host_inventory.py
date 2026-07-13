#!/usr/bin/env python3
"""Inventory the installed engines, platforms, architectures, and core apps on this host."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import shutil
from pathlib import Path
import platform
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from tools import godot_versioning, unity_env


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_host_inventory"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_host_inventory.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_host_inventory.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--godot-selector",
        help="Optional Godot version selector such as 4.7-stable..4.8-dev1 or 4.7-stable,4.8-dev1",
    )
    parser.add_argument("--max-godot-matches", type=int, default=5, help="Maximum Godot versions to include in the filtered runway view")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _application_status(name: str, candidates: list[str]) -> dict[str, object]:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return {"name": name, "status": "present", "path": found, "command": candidate}
    return {"name": name, "status": "missing", "path": None, "command": candidates[0] if candidates else name}


def _godot_inventory(selector: str | None = None, limit: int | None = None) -> dict[str, Any]:
    windows_versions = [str(row.get("version") or "") for row in engine_root_discovery.discover_godot_windows_versions()]
    linux_versions = [str(row.get("version") or "") for row in engine_root_discovery.discover_godot_linux_versions()]
    mac_versions = [str(row.get("version") or "") for row in engine_root_discovery.discover_godot_macos_versions()]
    all_versions = [*windows_versions, *linux_versions, *mac_versions]
    filtered = godot_versioning.select_versions(all_versions, selector, limit=limit)
    return {
        "public_search_roots": [str(path) for path in engine_root_discovery.public_engine_search_roots()["godot"]],
        "requested_selector": selector,
        "max_matches": limit,
        "available_versions": all_versions,
        "selected_versions": filtered,
        "windows_versions": windows_versions,
        "linux_versions": linux_versions,
        "mac_versions": mac_versions,
    }


def _unity_inventory() -> dict[str, Any]:
    host = unity_env.describe_host()
    installs = host.get("installs", [])
    versions = [str(row.get("version") or "") for row in installs if isinstance(row, dict)]
    editor_paths = [str(row.get("editor_path") or "") for row in installs if isinstance(row, dict) and row.get("editor_path")]
    return {
        "platform": host.get("platform"),
        "arch": host.get("arch"),
        "public_roots": host.get("public_roots", []),
        "installed_versions": versions,
        "editor_paths": editor_paths,
        "default_install": host.get("default_install"),
        "recommended_editor_overrides": host.get("recommended_editor_overrides", {}),
    }


def _unreal_inventory() -> dict[str, Any]:
    public_roots = engine_root_discovery.public_engine_search_roots()["unreal"]
    mac_public_roots = [str(path) for path in public_roots if platform.system().lower() == "darwin"]
    windows_platform_support_roots = [root / "Engine" / "Platforms" / "Linux" for root in public_roots]
    return {
        "public_search_roots": [str(path) for path in public_roots],
        "mac_public_roots": mac_public_roots,
        "linux_roots": [str(path) for path in engine_root_discovery.discover_unreal_linux_roots()],
        "linux_archives": [str(path) for path in engine_root_discovery.discover_unreal_linux_archives()],
        "windows_platform_support_roots": [str(path) for path in windows_platform_support_roots],
    }


def _generic_tools() -> list[dict[str, object]]:
    return [
        _application_status("python", ["python", "python3"]),
        _application_status("git", ["git"]),
        _application_status("docker", ["docker"]),
        _application_status("dotnet", ["dotnet"]),
    ]


def build_payload(args: argparse.Namespace | None = None) -> dict[str, object]:
    if args is None:
        args = parse_args([])
    host = {
        "platform": platform.system(),
        "arch": platform.machine(),
    }
    godot = _godot_inventory(args.godot_selector, args.max_godot_matches)
    unity = _unity_inventory()
    unreal = _unreal_inventory()

    return {
        "schema": "cesium.host_inventory.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "host": host,
        "tools": _generic_tools(),
        "engines": {
            "unreal": unreal,
            "unity": unity,
            "godot": godot,
        },
        "runway": {
            "unreal": bool(unreal["public_search_roots"] or unreal["linux_roots"] or unreal["linux_archives"]),
            "unity": bool(unity["installed_versions"]),
            "godot": bool(godot["selected_versions"]),
        },
        "next_steps": [
            "Use the engine-specific doctor commands once the inventory shows a viable install or public root.",
            "Use cesium-godot-bootstrap when Godot is missing but the archive can be staged from the official downloads.",
            "Use the lane runner after the runway is lit to see which routes are already possible on this host.",
        ],
    }


def render_markdown(payload: dict[str, object]) -> str:
    engines = payload.get("engines", {})
    godot = engines.get("godot", {}) if isinstance(engines, dict) else {}
    requested_selector = godot.get("requested_selector") if isinstance(godot, dict) else None
    max_matches = godot.get("max_matches") if isinstance(godot, dict) else None
    selected_versions = godot.get("selected_versions", []) if isinstance(godot, dict) else []
    lines = [
        "# Cesium Host Inventory",
        "",
        f"- platform: `{payload['host']['platform']}`",
        f"- arch: `{payload['host']['arch']}`",
        f"- status: `{payload['status']}`",
        f"- godot_selector: `{requested_selector or 'none'}`",
        f"- godot_max_matches: `{max_matches or 'none'}`",
        f"- godot_selected_versions: `{', '.join(selected_versions) or 'none'}`",
        "",
        "## Tools",
        "",
    ]
    for tool in payload.get("tools", []):
        if not isinstance(tool, dict):
            continue
        lines.append(f"- `{tool.get('name')}`: `{tool.get('status')}`")
        if tool.get("path"):
            lines.append(f"  path: `{tool.get('path')}`")
    lines.extend(["", "## Engines", ""])
    for engine_name, engine in payload.get("engines", {}).items():
        if not isinstance(engine, dict):
            continue
        lines.append(f"### {engine_name.title()}")
        for key, value in engine.items():
            if isinstance(value, list):
                lines.append(f"- {key}: `{', '.join(str(item) for item in value) or 'none'}`")
            else:
                lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Runway", ""])
    runway = payload.get("runway", {})
    if isinstance(runway, dict):
        for engine_name, ready in runway.items():
            lines.append(f"- {engine_name}: `{ready}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
