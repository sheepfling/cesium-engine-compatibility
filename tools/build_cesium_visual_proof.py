#!/usr/bin/env python3
"""Build a canonical screenshot-proof packet for the Cesium example projects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_visual_proof"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof.md"
UNREAL_RAW_CAPTURE_ROOT = (
    ROOT
    / "extensions"
    / "cesium"
    / "examples"
    / "unreal"
    / "CesiumVanillaExample"
    / "Saved"
    / "Screenshots"
    / "WindowsEditor"
)


@dataclass(frozen=True)
class CameraShot:
    name: str
    camera_position: tuple[float, float, float]
    look_at: tuple[float, float, float]
    up: tuple[float, float, float]
    fov_degrees: float


@dataclass(frozen=True)
class VisualProofTarget:
    engine: str
    native_target: str
    architecture: str
    subject_root: Path
    scene_path: Path | None
    preflight_command: str
    notes: str


CAMERA_SHOTS: tuple[CameraShot, ...] = (
    CameraShot("overview", (0.0, 4200.0, 3800.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 55.0),
    CameraShot("oblique", (4200.0, 1800.0, 2600.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 45.0),
    CameraShot("close", (1900.0, -900.0, 3200.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 35.0),
)


def _example_root(engine: str) -> Path:
    return ROOT / "extensions" / "cesium" / "examples" / engine / "CesiumVanillaExample"


def canonical_shot_names() -> tuple[str, ...]:
    return tuple(shot.name for shot in CAMERA_SHOTS)


def _shot_name_from_path(path: Path) -> tuple[str, str]:
    stem = path.stem
    for shot in canonical_shot_names():
        if f"_{shot}" in stem:
            prefix, _ = stem.rsplit(f"_{shot}", 1)
            return prefix or "default", shot
        if f"-{shot}" in stem:
            prefix, _ = stem.rsplit(f"-{shot}", 1)
            return prefix or "default", shot
        if stem == shot:
            return "default", shot
    return "default", stem


def normalize_unreal_visual_proof_capture(
    source_root: Path,
    capture_root: Path,
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    capture_root = capture_root.expanduser().resolve()
    capture_root.mkdir(parents=True, exist_ok=True)

    discovered = sorted(path for path in source_root.rglob("*.png") if path.is_file())
    selected: dict[str, dict[str, Any]] = {}
    leftovers: list[str] = []
    for path in discovered:
        variant, shot = _shot_name_from_path(path)
        if shot in canonical_shot_names() and shot not in selected:
            selected[shot] = {
                "source": str(path),
                "variant": variant,
            }
        else:
            leftovers.append(str(path))

    copied: list[dict[str, Any]] = []
    missing: list[str] = []
    for shot in canonical_shot_names():
        source = selected.get(shot)
        target_path = capture_root / f"{shot}.png"
        if source is None:
            missing.append(shot)
            continue
        if target_path.exists() and not overwrite:
            copied.append({"shot": shot, "source": source["source"], "target": str(target_path), "skipped": True})
            continue
        shutil.copy2(Path(source["source"]), target_path)
        copied.append({"shot": shot, "source": source["source"], "target": str(target_path), "skipped": False})

    return {
        "schema": "cesium.visual_proof_unreal_normalization.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if not missing else "partial",
        "source_root": str(source_root),
        "capture_root": str(capture_root),
        "shot_names": list(canonical_shot_names()),
        "discovered_png_count": len(discovered),
        "copied": copied,
        "missing": missing,
        "leftovers": leftovers,
        "capture_root_exists": capture_root.is_dir(),
    }


def _targets() -> list[VisualProofTarget]:
    targets: list[VisualProofTarget] = []
    for engine in ("unreal", "unity", "godot"):
        subject_root = _example_root(engine)
        scene_path = {
            "unreal": None,
            "unity": subject_root / "Assets" / "CesiumExampleBuild" / "Generated" / "CesiumVanillaExample.unity",
            "godot": subject_root / "scenes" / "Main.tscn",
        }[engine]
        for native_target in ("windows", "linux", "mac"):
            arches = ("x86_64", "arm64") if native_target == "mac" else ("x86_64",)
            for architecture in arches:
                notes = (
                    "Open the project, frame the canonical camera shots, and save PNGs under the reported output root."
                    if engine != "godot"
                    else "Use the checked-in Main.tscn as the canonical Godot scene and save PNGs under the reported output root."
                )
                preflight_command = f"cesium-example doctor --engine {engine}" + (f" --native-target {native_target}" if engine == "godot" or native_target != "windows" else "")
                if engine == "unreal" and native_target == "windows":
                    preflight_command = (
                        f'UnrealEditor-Cmd.exe "{subject_root / "CesiumVanillaExample.uproject"}" '
                        '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth,Cesium.VisualProof.Windows.CesiumEarth"'
                    )
                    notes = (
                        "Run the Cesium.VisualProof.Windows.ProxyEarth and Cesium.VisualProof.Windows.CesiumEarth automation tests, then normalize Unreal Saved/Screenshots/WindowsEditor PNGs into the shared visual-proof capture root."
                    )
                elif engine == "unreal":
                    notes = (
                        "The Windows Unreal visual-proof lane is the active proof path; keep the platform rows in the packet for planning and parity tracking."
                    )
                targets.append(
                    VisualProofTarget(
                        engine=engine,
                        native_target=native_target,
                        architecture=architecture,
                        subject_root=subject_root,
                        scene_path=scene_path,
                        preflight_command=preflight_command,
                        notes=notes,
                    )
                )
    return targets


def _startup_health_command(engine: str, native_target: str) -> str:
    if engine == "godot" and native_target == "windows":
        return "cesium-godot-aggressive-launcher --native-target windows --max-versions 1"
    if engine == "godot":
        return f"cesium-example doctor --engine godot --native-target {native_target}"
    return f"cesium-example doctor --engine {engine}" + (f" --native-target {native_target}" if native_target != "windows" else "")


def _capture_root(target: VisualProofTarget) -> Path:
    return DEFAULT_OUT_DIR / target.engine / target.native_target / target.architecture


def _target_payload(target: VisualProofTarget) -> dict[str, Any]:
    capture_root = _capture_root(target)
    expected_pngs = [capture_root / f"{shot.name}.png" for shot in CAMERA_SHOTS]
    raw_capture_root = UNREAL_RAW_CAPTURE_ROOT if target.engine == "unreal" and target.native_target == "windows" else None
    return {
        "engine": target.engine,
        "native_target": target.native_target,
        "architecture": target.architecture,
        "subject_root": str(target.subject_root),
        "scene_path": str(target.scene_path) if target.scene_path is not None else None,
        "startup_health_command": _startup_health_command(target.engine, target.native_target),
        "preflight_command": target.preflight_command,
        "capture_root": str(capture_root),
        "raw_capture_root": str(raw_capture_root) if raw_capture_root is not None else None,
        "expected_pngs": [str(path) for path in expected_pngs],
        "camera_shots": [
            {
                "name": shot.name,
                "camera_position": list(shot.camera_position),
                "look_at": list(shot.look_at),
                "up": list(shot.up),
                "fov_degrees": shot.fov_degrees,
            }
            for shot in CAMERA_SHOTS
        ],
        "notes": target.notes,
        "status": "commandable" if target.subject_root.exists() else "missing",
        "capture_step": (
            "Run the engine's screenshot capture flow, then normalize the captured PNGs into the shared capture_root directory."
            if raw_capture_root is not None
            else "Use the engine's screenshot capture flow to save the named shots into the capture_root directory."
        ),
        "startup_health_step": "Run the startup health command before attempting the visual proof capture.",
        "normalization_command": (
            f'cesium-visual-proof-normalize --engine unreal --source-root "{raw_capture_root}" --capture-root "{capture_root}"'
            if raw_capture_root is not None
            else None
        ),
    }


def _windows_first_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [target for target in targets if target["native_target"] == "windows"]


def build_payload() -> dict[str, object]:
    targets = [_target_payload(target) for target in _targets()]
    windows_targets = _windows_first_targets(targets)
    subject_counts = {
        "unreal": sum(1 for target in targets if target["engine"] == "unreal"),
        "unity": sum(1 for target in targets if target["engine"] == "unity"),
        "godot": sum(1 for target in targets if target["engine"] == "godot"),
    }
    return {
        "schema": "cesium.visual_proof.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "commandable" if all(target["status"] == "commandable" for target in targets) else "planned",
        "claim_boundaries": [
            "This packet standardizes screenshot proof targets for the Cesium example projects across Unreal, Unity, and Godot.",
            "It records the canonical camera poses and output paths, but it does not replace the engine-side screenshot harness itself.",
            "MacOS is split into Intel `x86_64` and Apple Silicon `arm64` targets so visual evidence stays architecture-aware.",
        ],
        "camera_shots": [
            {
                "name": shot.name,
                "camera_position": list(shot.camera_position),
                "look_at": list(shot.look_at),
                "up": list(shot.up),
                "fov_degrees": shot.fov_degrees,
            }
            for shot in CAMERA_SHOTS
        ],
        "targets": targets,
        "summary": {
            "target_count": len(targets),
            "shot_count": len(CAMERA_SHOTS),
            "subject_counts": subject_counts,
            "host_order": ["windows", "linux", "mac"],
            "windows_target_count": len(windows_targets),
            "capture_root": str(DEFAULT_OUT_DIR),
        },
        "next_steps": [
            "Start with the Windows native lanes so the first captures are easy to compare against the current host.",
            "Add an engine-specific capture harness that can move the camera to each canonical pose and emit PNGs.",
            "Run the perceptual-image comparison gate after capture so black frames and drift are caught automatically.",
            "Use the visual-proof packet as the output contract for those captures.",
            "Fold the resulting screenshots into the final compatibility packet once the harness exists.",
        ],
        "windows_first_runbook": [
            {
                "engine": target["engine"],
                "native_target": target["native_target"],
                "architecture": target["architecture"],
                "startup_health_command": target["startup_health_command"],
                "preflight_command": target["preflight_command"],
                "capture_root": target["capture_root"],
                "raw_capture_root": target.get("raw_capture_root"),
                "expected_pngs": target["expected_pngs"],
                "normalization_command": target.get("normalization_command"),
            }
            for target in windows_targets
        ],
        "related_packets": {
            "visual_proof_compare": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_visual_proof_compare" / "cesium_visual_proof_compare.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_visual_proof_compare/cesium_visual_proof_compare.json",
            },
            "compatibility_packet": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_compatibility_packet" / "cesium_compatibility_packet.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json",
            },
            "engine_matrix": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_engine_matrix" / "cesium_engine_matrix.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Visual Proof",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- target_count: `{payload.get('summary', {}).get('target_count')}`",
        f"- shot_count: `{payload.get('summary', {}).get('shot_count')}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Camera Shots", ""])
    for shot in payload.get("camera_shots", []):
        lines.append(
            f"- `{shot['name']}`: position `{shot['camera_position']}`, look_at `{shot['look_at']}`, up `{shot['up']}`, fov `{shot['fov_degrees']}`"
        )
    lines.extend(["", "## Targets", ""])
    for target in payload.get("targets", []):
        lines.append(f"### {target['engine']} / {target['native_target']} / {target['architecture']}")
        lines.append(f"- status: `{target['status']}`")
        lines.append(f"- subject_root: `{target['subject_root']}`")
        if target.get("scene_path") is not None:
            lines.append(f"- scene_path: `{target['scene_path']}`")
        lines.append(f"- startup_health_command: `{target['startup_health_command']}`")
        lines.append(f"- preflight_command: `{target['preflight_command']}`")
        lines.append(f"- capture_root: `{target['capture_root']}`")
        if target.get("raw_capture_root") is not None:
            lines.append(f"- raw_capture_root: `{target['raw_capture_root']}`")
        lines.append("- expected_pngs:")
        for path in target.get("expected_pngs", []):
            lines.append(f"  - `{path}`")
        lines.append(f"- capture_step: {target['capture_step']}")
        lines.append(f"- startup_health_step: {target['startup_health_step']}")
        if target.get("normalization_command") is not None:
            lines.append(f"- normalization_command: `{target['normalization_command']}`")
        lines.append(f"- notes: {target['notes']}")
    lines.extend(["", "## Windows First Runbook", ""])
    for item in payload.get("windows_first_runbook", []):
        lines.append(f"### {item['engine']} / {item['native_target']} / {item['architecture']}")
        lines.append(f"- startup_health_command: `{item['startup_health_command']}`")
        lines.append(f"- preflight_command: `{item['preflight_command']}`")
        lines.append(f"- capture_root: `{item['capture_root']}`")
        if item.get("raw_capture_root") is not None:
            lines.append(f"- raw_capture_root: `{item['raw_capture_root']}`")
        lines.append("- expected_pngs:")
        for path in item.get("expected_pngs", []):
            lines.append(f"  - `{path}`")
        if item.get("normalization_command") is not None:
            lines.append(f"- normalization_command: `{item['normalization_command']}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        lines.append(f"- target_count: `{summary.get('target_count')}`")
        lines.append(f"- shot_count: `{summary.get('shot_count')}`")
        lines.append(f"- capture_root: `{summary.get('capture_root')}`")
        lines.append(f"- windows_target_count: `{summary.get('windows_target_count')}`")
        host_order = summary.get("host_order", [])
        if isinstance(host_order, list):
            lines.append(f"- host_order: `{', '.join(str(host) for host in host_order)}`")
        subject_counts = summary.get("subject_counts", {})
        if isinstance(subject_counts, dict):
            for engine, count in subject_counts.items():
                lines.append(f"- {engine}: `{count}`")
    lines.extend(["", "## Related Packets", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
