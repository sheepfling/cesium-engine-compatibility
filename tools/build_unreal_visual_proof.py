#!/usr/bin/env python3
"""Build the Unreal Windows visual-proof runner report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from tools import build_cesium_visual_proof


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "unreal_visual_proof"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "unreal_visual_proof.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "unreal_visual_proof.md"
EXPECTED_ENGINE = "unreal"
EXPECTED_NATIVE_TARGET = "windows"
EXPECTED_ARCHITECTURE = "x86_64"
HARNESS_PATH = (
    ROOT
    / "external"
    / "cesium"
    / "cesium-unreal"
    / "Source"
    / "CesiumRuntime"
    / "Private"
    / "Tests"
    / "CesiumVisualProof.spec.cpp"
)


def _resolve_unreal_editor_command(version: str | None = None) -> dict[str, Any]:
    editors = engine_root_discovery.discover_unreal_windows_editors()
    if version:
        editors = [
            entry
            for entry in editors
            if str(entry.get("root", "")).replace("\\", "/").rstrip("/").endswith(f"UE_{version}")
        ]
    if not editors:
        return {
            "status": "missing",
            "selected_root": None,
            "selected_executable": None,
            "available_editors": [],
            "command": None,
        }
    selected = editors[0]
    return {
        "status": "present",
        "selected_root": str(selected["root"]),
        "selected_executable": str(selected["executable"]),
        "available_editors": [
            {
                "root": str(entry["root"]),
                "executable": str(entry["executable"]),
                "command": str(entry["command"]),
            }
            for entry in editors
        ],
        "command": str(selected["command"]),
    }


def build_payload(version: str | None = None) -> dict[str, Any]:
    visual_proof = build_cesium_visual_proof.build_payload()
    target = None
    for candidate in visual_proof.get("targets", []):
        if not isinstance(candidate, dict):
            continue
        if (
            candidate.get("engine") == EXPECTED_ENGINE
            and candidate.get("native_target") == EXPECTED_NATIVE_TARGET
            and candidate.get("architecture") == EXPECTED_ARCHITECTURE
        ):
            target = candidate
            break
    if target is None:
        raise RuntimeError("Could not locate the Unreal Windows visual-proof target.")
    proof_runner = target.get("proof_runner") if isinstance(target.get("proof_runner"), dict) else {}
    editor = _resolve_unreal_editor_command(version)
    command = str(target.get("preflight_command") or proof_runner.get("command") or "")
    raw_capture_root = str(target.get("raw_capture_root") or proof_runner.get("raw_capture_root") or "")
    capture_root = str(target.get("capture_root") or proof_runner.get("normalized_capture_root") or "")
    manifest_path = str(target.get("manifest_path") or proof_runner.get("manifest_path") or "")
    normalize_command = str(target.get("normalization_command") or proof_runner.get("normalize_command") or "")
    launcher_command = None
    launcher_commands: list[str] = []
    if editor["status"] == "present":
        proxy_command = (
            f'"{editor["command"]}" '
            f'"{ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject"}" '
            '-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache '
            '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"'
        )
        cesium_command = (
            f'"{editor["command"]}" '
            f'"{ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject"}" '
            '-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache '
            '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.CesiumEarth; Quit"'
        )
        launcher_commands = [proxy_command, cesium_command]
        launcher_command = (
            proxy_command
        )
    return {
        "schema": "cesium.unreal_visual_proof.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "commandable" if editor["status"] == "present" else "planned",
        "engine": EXPECTED_ENGINE,
        "native_target": EXPECTED_NATIVE_TARGET,
        "architecture": EXPECTED_ARCHITECTURE,
        "engine_version": version,
        "example_project": str(
            ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject"
        ),
        "engine_side_harness_status": "present",
        "engine_side_harness_path": str(HARNESS_PATH),
        "editor_discovery": editor,
        "command": command,
        "launcher_command": launcher_command,
        "launcher_commands": launcher_commands,
        "raw_capture_root": raw_capture_root,
        "normalized_capture_root": capture_root,
        "manifest_path": manifest_path,
        "normalize_command": normalize_command,
        "windows_tests": list(proof_runner.get("windows_tests", [])) if isinstance(proof_runner, dict) else [],
        "capture_focus": list(target.get("notes") and [target["notes"]] or []),
        "camera_shots": visual_proof.get("camera_shots", []),
        "expected_pngs": list(target.get("expected_pngs", [])),
        "next_steps": [
            "If an Unreal Windows editor is installed, run the launcher_command to execute the ProxyEarth and CesiumEarth automation tests.",
            "Wire the Unreal automation tests to emit the canonical proxy-earth and Cesium-earth PNGs under the raw screenshot root.",
            "Normalize the raw capture root into the shared proof packet root and run the compare gate.",
            "Keep the Unreal runner payload aligned with the Unity and Godot runner shapes so downstream auditing stays uniform.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Unreal Visual Proof",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- engine: `{payload['engine']}`",
        f"- native_target: `{payload['native_target']}`",
        f"- architecture: `{payload['architecture']}`",
        f"- command: `{payload['command']}`",
        f"- launcher_command: `{payload.get('launcher_command')}`",
        f"- raw_capture_root: `{payload['raw_capture_root']}`",
        f"- normalized_capture_root: `{payload['normalized_capture_root']}`",
        f"- manifest_path: `{payload['manifest_path']}`",
        f"- normalize_command: `{payload['normalize_command']}`",
        "",
        "## Windows Tests",
        "",
    ]
    for test_name in payload.get("windows_tests", []):
        lines.append(f"- `{test_name}`")
    lines.extend(["", "## Editor Discovery", ""])
    editor = payload.get("editor_discovery", {})
    if isinstance(editor, dict):
        lines.append(f"- status: `{editor.get('status')}`")
        if editor.get("selected_root") is not None:
            lines.append(f"- selected_root: `{editor.get('selected_root')}`")
        if editor.get("selected_executable") is not None:
            lines.append(f"- selected_executable: `{editor.get('selected_executable')}`")
        if editor.get("available_editors"):
            lines.append("- available_editors:")
            for entry in editor.get("available_editors", []):
                lines.append(f"  - `{entry.get('command')}`")
    lines.extend(["", "## Expected PNGs", ""])
    for path in payload.get("expected_pngs", []):
        lines.append(f"- `{path}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args(argv)

    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"planned", "commandable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
