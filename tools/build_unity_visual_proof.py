#!/usr/bin/env python3
"""Build the Unity Windows visual-proof runner report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

from tools import build_cesium_visual_proof, unity_env


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "unity_visual_proof"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "unity_visual_proof.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "unity_visual_proof.md"
EXPECTED_ENGINE = "unity"
EXPECTED_NATIVE_TARGET = "windows"
EXPECTED_ARCHITECTURE = "x86_64"
HARNESS_PATH = (
    ROOT
    / "extensions"
    / "cesium"
    / "examples"
    / "unity"
    / "CesiumVanillaExample"
    / "Assets"
    / "CesiumVisualProofCapture.cs"
)


def _resolve_unity_editor_command() -> dict[str, Any]:
    installs = unity_env.discover_installs()
    if not installs:
        return {
            "status": "missing",
            "selected_root": None,
            "selected_executable": None,
            "available_editors": [],
            "command": None,
        }
    selected = installs[0]
    command = str(selected.editor_path or "")
    return {
        "status": "present",
        "selected_root": str(selected.install_root or ""),
        "selected_executable": command,
        "available_editors": [
            {
                "version": str(entry.version or ""),
                "root": str(entry.install_root or ""),
                "executable": str(entry.editor_path or ""),
                "command": str(entry.editor_path or ""),
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
        raise RuntimeError("Could not locate the Unity Windows visual-proof target.")
    proof_runner = target.get("proof_runner") if isinstance(target.get("proof_runner"), dict) else {}
    editor = _resolve_unity_editor_command()
    project_dir = ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample"
    selected_install = unity_env.resolve_install()
    license_probe = unity_env.probe_unity_license(
        selected_install,
        project_dir=project_dir,
        log_path=ROOT / "artifacts" / "reports" / "unity_visual_proof" / "unity_license_probe.log",
        timeout_seconds=float(os.environ.get("CESIUM_UNITY_LICENSE_PROBE_TIMEOUT_SECONDS", "15")),
    )
    auto_open_hub = os.environ.get("CESIUM_UNITY_AUTO_OPEN_HUB", "1").strip().lower() not in {"0", "false", "no", "off"}
    hub_bootstrap = {"status": "not-needed", "enabled": auto_open_hub}
    if auto_open_hub and license_probe.get("status") in {"blocked", "unknown", "timeout", "error"}:
        hub_bootstrap = unity_env.ensure_unity_hub_open(
            settle_seconds=float(os.environ.get("CESIUM_UNITY_HUB_SETTLE_SECONDS", "8")),
        )
        hub_bootstrap["reason"] = f"license_probe:{license_probe.get('status')}"
    command = str(proof_runner.get("startup_health_command") or editor.get("command") or proof_runner.get("command") or target.get("preflight_command") or "")
    capture_root = str(target.get("capture_root") or proof_runner.get("normalized_capture_root") or "")
    manifest_path = str(target.get("manifest_path") or proof_runner.get("manifest_path") or "")
    launcher_command = (
        f'"{editor.get("command")}" -batchmode -nographics -quit -projectPath "{project_dir}"'
        if editor.get("command")
        else None
    )
    normalization_command = (
        str(target.get("normalization_command") or proof_runner.get("normalize_command") or "")
        or f'cesium-visual-proof-normalize --engine {EXPECTED_ENGINE} --source-root "{capture_root}" --capture-root "{capture_root}" --native-target {EXPECTED_NATIVE_TARGET} --architecture {EXPECTED_ARCHITECTURE}'
    )
    return {
        "schema": "cesium.unity_visual_proof.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "commandable" if editor["status"] == "present" else "planned",
        "engine": EXPECTED_ENGINE,
        "native_target": EXPECTED_NATIVE_TARGET,
        "architecture": EXPECTED_ARCHITECTURE,
        "example_project": str(
            ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample" / "CesiumVanillaExample.unity"
        ),
        "engine_side_harness_status": "present",
        "engine_side_harness_path": str(HARNESS_PATH),
        "editor_discovery": editor,
        "license_probe": license_probe,
        "hub_bootstrap": hub_bootstrap,
        "license_ready": license_probe.get("status") == "available",
        "command": command,
        "launcher_command": launcher_command,
        "raw_capture_root": capture_root,
        "normalized_capture_root": capture_root,
        "manifest_path": manifest_path,
        "normalize_command": normalization_command,
        "capture_focus": [
            "version-aware CesiumVisualProofCapture.cs harness",
            "proxy-earth and Cesium-earth capture variants",
            "visual_proof_manifest.json beside the normalized PNGs",
            "normalize-and-compare path shared with the other engines",
        ],
        "camera_shots": visual_proof.get("camera_shots", []),
        "expected_pngs": list(target.get("expected_pngs", [])),
        "next_steps": [
            "If the license probe is blocked, finish activation in the Unity Hub window left open by this report.",
            "Rerun the report after Hub has settled so the license probe can prove availability.",
            "If a Unity editor and license are available, run the launcher command to execute the visual-proof capture harness.",
            "Normalize the raw capture root into the shared proof packet root and run the compare gate.",
            "Keep the Unity runner payload aligned with the Unreal and Godot runner shapes so downstream auditing stays uniform.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Unity Visual Proof",
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
        f"- license_ready: `{payload.get('license_ready')}`",
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
                lines.append(f"  - `{entry.get('command')}`")
    license_probe = payload.get("license_probe")
    if isinstance(license_probe, dict):
        lines.extend(["", "## License Probe", "", f"- status: `{license_probe.get('status')}`", f"- log_path: `{license_probe.get('log_path')}`"])
    hub_bootstrap = payload.get("hub_bootstrap")
    if isinstance(hub_bootstrap, dict):
        lines.extend(["", "## Unity Hub", "", f"- status: `{hub_bootstrap.get('status')}`", f"- executable: `{hub_bootstrap.get('executable')}`", f"- left_running: `{hub_bootstrap.get('left_running')}`"])
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
