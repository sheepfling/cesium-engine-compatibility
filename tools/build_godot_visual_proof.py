#!/usr/bin/env python3
"""Build the Godot Windows visual-proof runner report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from tools import build_cesium_visual_proof


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "godot_visual_proof"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "godot_visual_proof.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "godot_visual_proof.md"
EXPECTED_ENGINE = "godot"
EXPECTED_NATIVE_TARGET = "windows"
EXPECTED_ARCHITECTURE = "x86_64"
HARNESS_PATH = (
    ROOT
    / "extensions"
    / "cesium"
    / "examples"
    / "godot"
    / "CesiumVanillaExample"
    / "scripts"
    / "VisualProofRunner.gd"
)


def _resolve_godot_editor_command() -> dict[str, Any]:
    installs = engine_root_discovery.discover_godot_windows_versions()
    if not installs:
        return {
            "status": "missing",
            "selected_root": None,
            "selected_executable": None,
            "available_editors": [],
            "command": None,
        }
    selected = installs[0]
    command = str(selected.get("console_executable") or selected.get("executable") or "")
    return {
        "status": "present",
        "selected_root": str(selected.get("root") or ""),
        "selected_executable": command,
        "available_editors": [
            {
                "version": str(entry.get("version") or ""),
                "root": str(entry.get("root") or ""),
                "executable": str(entry.get("executable") or ""),
                "console_executable": str(entry.get("console_executable") or ""),
            }
            for entry in installs
        ],
        "command": command,
    }


def build_payload() -> dict[str, Any]:
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
        raise RuntimeError("Could not locate the Godot Windows visual-proof target.")
    proof_runner = target.get("proof_runner") if isinstance(target.get("proof_runner"), dict) else {}
    editor = _resolve_godot_editor_command()
    command = str(proof_runner.get("startup_health_command") or proof_runner.get("command") or target.get("startup_health_command") or "")
    capture_root = str(target.get("capture_root") or proof_runner.get("normalized_capture_root") or "")
    manifest_path = str(target.get("manifest_path") or proof_runner.get("manifest_path") or "")
    normalization_command = (
        str(target.get("normalization_command") or proof_runner.get("normalize_command") or "")
        or f'cesium-visual-proof-normalize --engine {EXPECTED_ENGINE} --source-root "{capture_root}" --capture-root "{capture_root}" --native-target {EXPECTED_NATIVE_TARGET} --architecture {EXPECTED_ARCHITECTURE}'
    )
    return {
        "schema": "cesium.godot_visual_proof.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "commandable" if editor["status"] == "present" else "planned",
        "engine": EXPECTED_ENGINE,
        "native_target": EXPECTED_NATIVE_TARGET,
        "architecture": EXPECTED_ARCHITECTURE,
        "example_project": str(
            ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample" / "project.godot"
        ),
        "engine_side_harness_status": "present",
        "engine_side_harness_path": str(HARNESS_PATH),
        "editor_discovery": editor,
        "command": command,
        "launcher_command": str(
            editor.get("command") or "cesium-godot-aggressive-launcher --native-target windows --max-versions 1"
        ),
        "raw_capture_root": capture_root,
        "normalized_capture_root": capture_root,
        "manifest_path": manifest_path,
        "normalize_command": normalization_command,
        "capture_focus": [
            "VisualProofRunner.gd six-shot harness",
            "proxy-earth and Cesium-earth variants",
            "visual_proof_manifest.json beside the normalized PNGs",
            "compare gate with black/gray/drift checks",
        ],
        "camera_shots": visual_proof.get("camera_shots", []),
        "expected_pngs": list(target.get("expected_pngs", [])),
        "next_steps": [
            "If a Windows Godot install is present, run the launcher command to exercise the proof lane.",
            "Normalize the raw capture root into the shared proof packet root and run the compare gate.",
            "Keep the Godot runner payload aligned with the Unreal and Unity runner shapes so downstream auditing stays uniform.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Godot Visual Proof",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- engine: `{payload['engine']}`",
        f"- native_target: `{payload['native_target']}`",
        f"- architecture: `{payload['architecture']}`",
        f"- command: `{payload['command']}`",
        f"- launcher_command: `{payload['launcher_command']}`",
        f"- raw_capture_root: `{payload['raw_capture_root']}`",
        f"- normalized_capture_root: `{payload['normalized_capture_root']}`",
        f"- manifest_path: `{payload['manifest_path']}`",
        f"- normalize_command: `{payload['normalize_command']}`",
        "",
        "## Editor Discovery",
        "",
    ]
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
                lines.append(f"  - `{entry.get('console_executable') or entry.get('executable')}`")
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
