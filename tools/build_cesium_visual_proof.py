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
VISUAL_PROOF_MANIFEST = "visual_proof_manifest.json"
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
    CameraShot("close", (4300.0, 800.0, 1400.0), (3600.0, 400.0, 1300.0), (0.0, 0.0, 1.0), 50.0),
)
CAPTURE_VARIANTS: tuple[str, ...] = ("proxy", "cesium")


def _example_root(engine: str) -> Path:
    return ROOT / "extensions" / "cesium" / "examples" / engine / "CesiumVanillaExample"


def canonical_shot_names() -> tuple[str, ...]:
    return tuple(shot.name for shot in CAMERA_SHOTS)


def canonical_capture_variants() -> tuple[str, ...]:
    return CAPTURE_VARIANTS


def _visual_proof_manifest_path(capture_root: Path) -> Path:
    return capture_root / VISUAL_PROOF_MANIFEST


def _write_visual_proof_manifest(capture_root: Path, payload: dict[str, Any]) -> None:
    _visual_proof_manifest_path(capture_root).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _variant_name_from_path(path: Path) -> str:
    stem = path.stem.lower()
    if "cesiumearth" in stem or stem.startswith("cesium_") or stem.startswith("cesium-"):
        return "cesium"
    if "proxyearth" in stem or stem.startswith("proxy_") or stem.startswith("proxy-"):
        return "proxy"
    return "default"


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


def normalize_visual_proof_capture(
    engine: str,
    source_root: Path,
    capture_root: Path,
    *,
    host: str = "windows",
    native_target: str = "windows",
    architecture: str = "x86_64",
    overwrite: bool = True,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    capture_root = capture_root.expanduser().resolve()
    capture_root.mkdir(parents=True, exist_ok=True)

    # Engine screenshot folders accumulate numbered captures across runs. Pick
    # the newest frame for each pose so normalization cannot silently reuse a
    # stale proof image from an earlier build.
    discovered = sorted(
        (path for path in source_root.rglob("*.png") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
        reverse=True,
    )
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    leftovers: list[str] = []
    for path in discovered:
        variant, shot = _shot_name_from_path(path)
        canonical_variant = _variant_name_from_path(path)
        if canonical_variant == "default":
            canonical_variant = variant
        if shot in canonical_shot_names():
            key = (canonical_variant, shot)
            if key not in selected:
                selected[key] = {
                    "source": str(path),
                    "variant": canonical_variant,
                }
        else:
            leftovers.append(str(path))

    copied: list[dict[str, Any]] = []
    missing: list[str] = []
    for variant in canonical_capture_variants():
        for shot in canonical_shot_names():
            source = selected.get((variant, shot))
            target_path = capture_root / f"{variant}_{shot}.png"
            if source is None:
                missing.append(f"{variant}/{shot}")
                continue
            source_path = Path(source["source"])
            if target_path.exists() and not overwrite:
                copied.append(
                    {
                        "variant": variant,
                        "shot": shot,
                        "source": source["source"],
                        "target": str(target_path),
                        "skipped": True,
                    }
                )
                continue
            if source_path.resolve() == target_path.resolve():
                copied.append(
                    {
                        "variant": variant,
                        "shot": shot,
                        "source": source["source"],
                        "target": str(target_path),
                        "skipped": True,
                    }
                )
                continue
            shutil.copy2(source_path, target_path)
            copied.append(
                {
                    "variant": variant,
                    "shot": shot,
                    "source": source["source"],
                    "target": str(target_path),
                    "skipped": False,
                }
            )

    manifest = {
        "schema": "cesium.visual_proof_manifest.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": engine,
        "host": host,
        "native_target": native_target,
        "architecture": architecture,
        "source_root": str(source_root),
        "capture_root": str(capture_root),
        "capture_variants": list(canonical_capture_variants()),
        "shot_names": list(canonical_shot_names()),
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
        "capture_paths": [
            str(capture_root / f"{variant}_{shot}.png")
            for variant in canonical_capture_variants()
            for shot in canonical_shot_names()
        ],
        "normalized_from": str(source_root),
        "copied_count": len([item for item in copied if not item.get("skipped")]),
        "missing": missing,
        "leftovers": leftovers,
    }
    # Preserve runtime-specific proof gates when a launcher emitted them. This
    # keeps normalization lossless without imposing Unity-only fields on the
    # generic fixture and cross-engine manifest contract.
    source_manifest_path = source_root / VISUAL_PROOF_MANIFEST
    if source_manifest_path.is_file():
        try:
            source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            source_manifest = {}
        if isinstance(source_manifest, dict):
            for key in ("cesium_configured", "cesium_source", "cesium_ready", "cesium_renderer_count", "cesium_failure"):
                if key in source_manifest:
                    manifest[key] = source_manifest[key]
    _write_visual_proof_manifest(capture_root, manifest)

    return {
        "schema": f"cesium.visual_proof_{engine}_normalization.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if not missing else "partial",
        "manifest_path": str(_visual_proof_manifest_path(capture_root)),
        "source_root": str(source_root),
        "capture_root": str(capture_root),
        "capture_variants": list(canonical_capture_variants()),
        "shot_names": list(canonical_shot_names()),
        "discovered_png_count": len(discovered),
        "copied": copied,
        "missing": missing,
        "leftovers": leftovers,
        "capture_root_exists": capture_root.is_dir(),
    }


def normalize_unreal_visual_proof_capture(
    source_root: Path,
    capture_root: Path,
    *,
    host: str = "windows",
    native_target: str = "windows",
    architecture: str = "x86_64",
    overwrite: bool = True,
) -> dict[str, Any]:
    return normalize_visual_proof_capture(
        "unreal",
        source_root,
        capture_root,
        host=host,
        native_target=native_target,
        architecture=architecture,
        overwrite=overwrite,
    )


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
                        f'UnrealEditor.exe "{subject_root / "CesiumVanillaExample.uproject"}" '
                        '-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache '
                        '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"'
                    )
                    notes = (
                        "Run Cesium.VisualProof.Windows.ProxyEarth first, then Cesium.VisualProof.Windows.CesiumEarth, and normalize Unreal Saved/Screenshots/WindowsEditor PNGs into the shared visual-proof capture root."
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
    if engine == "unity" and native_target == "windows":
        return "cesium-unity-visual-proof"
    if engine == "godot":
        return f"cesium-example doctor --engine godot --native-target {native_target}"
    if engine == "unity":
        return "cesium-unity-visual-proof"
    return f"cesium-example doctor --engine {engine}" + (f" --native-target {native_target}" if native_target != "windows" else "")


def _capture_root(target: VisualProofTarget) -> Path:
    return DEFAULT_OUT_DIR / target.engine / target.native_target / target.architecture


def _proof_runner_payload(target: VisualProofTarget, capture_root: Path, raw_capture_root: Path | None) -> dict[str, Any]:
    runner_kind = "automation" if target.engine == "unreal" else "launcher"
    windows_tests = (
        [
            "Cesium.VisualProof.Windows.ProxyEarth",
            "Cesium.VisualProof.Windows.CesiumEarth",
        ]
        if target.engine == "unreal" and target.native_target == "windows"
        else None
    )
    return {
        "kind": runner_kind,
        "command": target.preflight_command,
        "proof_variants": list(canonical_capture_variants()),
        "capture_paths": [str(capture_root / f"{variant}_{shot.name}.png") for variant in canonical_capture_variants() for shot in CAMERA_SHOTS],
        "manifest_path": str(capture_root / VISUAL_PROOF_MANIFEST),
        "windows_tests": windows_tests,
        "startup_health_command": _startup_health_command(target.engine, target.native_target),
        "raw_capture_root": str(raw_capture_root) if raw_capture_root is not None else None,
        "normalized_capture_root": str(capture_root),
        "normalize_command": (
            f'cesium-visual-proof-normalize --engine {target.engine} --source-root "{raw_capture_root}" --capture-root "{capture_root}" --native-target {target.native_target} --architecture {target.architecture}'
            if raw_capture_root is not None
            else None
        ),
    }


def _target_payload(target: VisualProofTarget) -> dict[str, Any]:
    capture_root = _capture_root(target)
    expected_pngs = [
        capture_root / f"{variant}_{shot.name}.png"
        for variant in canonical_capture_variants()
        for shot in CAMERA_SHOTS
    ]
    raw_capture_root = UNREAL_RAW_CAPTURE_ROOT if target.engine == "unreal" and target.native_target == "windows" else None
    unreal_lane_split = None
    if target.engine == "unreal":
        unreal_lane_split = {
            "baseline_version": "5.7",
            "forward_version": "5.8",
        }
    return {
        "engine": target.engine,
        "native_target": target.native_target,
        "architecture": target.architecture,
        "subject_root": str(target.subject_root),
        "scene_path": str(target.scene_path) if target.scene_path is not None else None,
        "lane_split": unreal_lane_split,
        "lane_versions": ["5.7", "5.8"] if target.engine == "unreal" else None,
        "proof_runner": _proof_runner_payload(target, capture_root, raw_capture_root),
        "startup_health_command": _startup_health_command(target.engine, target.native_target),
        "preflight_command": target.preflight_command,
        "capture_root": str(capture_root),
        "raw_capture_root": str(raw_capture_root) if raw_capture_root is not None else None,
        "capture_variants": list(canonical_capture_variants()),
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
            "Run the engine's screenshot capture flow, then normalize the captured proxy and Cesium PNGs into the shared capture_root directory."
            if raw_capture_root is not None
            else "Use the engine's screenshot capture flow to save the proxy and Cesium named shots into the capture_root directory."
        ),
        "startup_health_step": "Run the startup health command before attempting the visual proof capture.",
        "manifest_path": str(capture_root / VISUAL_PROOF_MANIFEST),
        "normalization_command": (
            f'cesium-visual-proof-normalize --engine {target.engine} --source-root "{raw_capture_root}" --capture-root "{capture_root}" --native-target {target.native_target} --architecture {target.architecture}'
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
            "variant_count": len(CAPTURE_VARIANTS),
            "expected_capture_count": len(CAMERA_SHOTS) * len(CAPTURE_VARIANTS),
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
                "lane_split": target.get("lane_split"),
                "lane_versions": target.get("lane_versions"),
                "proof_runner": target.get("proof_runner"),
                "startup_health_command": target["startup_health_command"],
                "preflight_command": target["preflight_command"],
                "capture_root": target["capture_root"],
                "manifest_path": target["manifest_path"],
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
            "windows_visual_proof": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "windows_visual_proof" / "windows_visual_proof.json").is_file() else "missing",
                "path": "artifacts/reports/windows_visual_proof/windows_visual_proof.json",
            },
            "windows_visual_proof_run": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "windows_visual_proof_run" / "windows_visual_proof_run.json").is_file() else "missing",
                "path": "artifacts/reports/windows_visual_proof_run/windows_visual_proof_run.json",
            },
            "unreal_visual_proof": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "unreal_visual_proof" / "unreal_visual_proof.json").is_file() else "missing",
                "path": "artifacts/reports/unreal_visual_proof/unreal_visual_proof.json",
            },
            "unity_visual_proof": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "unity_visual_proof" / "unity_visual_proof.json").is_file() else "missing",
                "path": "artifacts/reports/unity_visual_proof/unity_visual_proof.json",
            },
            "godot_visual_proof": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "godot_visual_proof" / "godot_visual_proof.json").is_file() else "missing",
                "path": "artifacts/reports/godot_visual_proof/godot_visual_proof.json",
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
        if target.get("manifest_path") is not None:
            lines.append(f"- manifest_path: `{target['manifest_path']}`")
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
        if item.get("lane_split"):
            lines.append(f"- lane_split: `{item['lane_split']}`")
        if item.get("lane_versions") is not None:
            lines.append(f"- lane_versions: `{item['lane_versions']}`")
        proof_runner = item.get("proof_runner")
        if isinstance(proof_runner, dict):
            lines.append("- proof_runner:")
            lines.append(f"  - kind: `{proof_runner.get('kind')}`")
            lines.append(f"  - command: `{proof_runner.get('command')}`")
            lines.append(f"  - startup_health_command: `{proof_runner.get('startup_health_command')}`")
            lines.append(f"  - manifest_path: `{proof_runner.get('manifest_path')}`")
            lines.append(f"  - normalized_capture_root: `{proof_runner.get('normalized_capture_root')}`")
            if proof_runner.get("raw_capture_root") is not None:
                lines.append(f"  - raw_capture_root: `{proof_runner.get('raw_capture_root')}`")
            if proof_runner.get("windows_tests") is not None:
                lines.append(f"  - windows_tests: `{proof_runner.get('windows_tests')}`")
            if proof_runner.get("capture_paths") is not None:
                lines.append("  - capture_paths:")
                for path in proof_runner.get("capture_paths", []):
                    lines.append(f"    - `{path}`")
        lines.append(f"- startup_health_command: `{item['startup_health_command']}`")
        lines.append(f"- preflight_command: `{item['preflight_command']}`")
        lines.append(f"- capture_root: `{item['capture_root']}`")
        lines.append(f"- manifest_path: `{item['manifest_path']}`")
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
        lines.append(f"- variant_count: `{summary.get('variant_count')}`")
        lines.append(f"- expected_capture_count: `{summary.get('expected_capture_count')}`")
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
