#!/usr/bin/env python3
"""Validate manifest-backed visual-proof capture roots for all engines."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import build_cesium_visual_proof


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_visual_proof_roots"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_roots.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_roots.md"
EXPECTED_SHOTS = ("overview", "oblique", "close")
EXPECTED_VARIANTS = ("proxy", "cesium")
EXPECTED_ENGINES = ("unreal", "unity", "godot")


def _discover_default_scan_roots() -> list[Path]:
    roots: list[Path] = []
    for engine in ("unreal", "unity", "godot"):
        for candidate in ROOT.glob(f"artifacts/reports/cesium_visual_proof/{engine}/*/*"):
            if candidate.is_dir():
                roots.append(candidate)
    return roots


def _load_manifest(root: Path) -> dict[str, Any] | None:
    manifest_path = root / "visual_proof_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _expected_png_names(manifest: dict[str, Any]) -> list[str]:
    capture_paths = manifest.get("capture_paths")
    if isinstance(capture_paths, list):
        names = [Path(str(item)).name for item in capture_paths if str(item).strip()]
        if names:
            return names
    return [f"{variant}_{shot}.png" for variant in EXPECTED_VARIANTS for shot in EXPECTED_SHOTS]


def _shot_names(manifest: dict[str, Any], expected_png_names: list[str]) -> list[str]:
    shot_names = manifest.get("shot_names")
    if isinstance(shot_names, list):
        names = [str(item).strip() for item in shot_names if str(item).strip()]
        if names:
            return names
    names: list[str] = []
    for name in expected_png_names:
        stem = Path(name).stem
        if "_" in stem:
            shot = stem.split("_", 1)[1]
            if shot not in names:
                names.append(shot)
    return names


def _expected_camera_shots() -> list[dict[str, Any]]:
    return [
        {
            "name": shot.name,
            "camera_position": list(shot.camera_position),
            "look_at": list(shot.look_at),
            "up": list(shot.up),
            "fov_degrees": shot.fov_degrees,
        }
        for shot in build_cesium_visual_proof.CAMERA_SHOTS
    ]


def validate_root(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    manifest = _load_manifest(root)
    manifest_path = root / "visual_proof_manifest.json"
    png_names = sorted(path.name for path in root.glob("*.png"))

    findings: list[str] = []
    status = "fail"
    if manifest is None:
        findings.append("missing or invalid manifest")
    else:
        if manifest.get("schema") != "cesium.visual_proof_manifest.v1":
            findings.append("unexpected manifest schema")
        if not manifest.get("engine"):
            findings.append("missing engine")
        if not manifest.get("native_target"):
            findings.append("missing native_target")
        if not manifest.get("architecture"):
            findings.append("missing architecture")
        if str(manifest.get("engine") or "").lower() == "unity":
            # Older generic roots do not have runtime metadata. New Unity
            # captures do, and those must pass the live-content gate.
            if "cesium_configured" in manifest or "cesium_ready" in manifest:
                if manifest.get("cesium_configured") is not True:
                    findings.append("unity Cesium proof was not configured with a live tileset source")
                if manifest.get("cesium_ready") is not True:
                    findings.append("unity Cesium proof did not report rendered tile content")
                if not isinstance(manifest.get("cesium_renderer_count"), int) or manifest.get("cesium_renderer_count", 0) < 1:
                    findings.append("unity Cesium proof has no rendered tile renderer")
        if str(manifest.get("engine") or "").lower() == "godot":
            if "cesium_configured" in manifest or "cesium_ready" in manifest:
                if manifest.get("cesium_configured") is not True:
                    findings.append("godot Cesium proof was not configured with a live tileset source")
                if manifest.get("cesium_ready") is not True:
                    findings.append("godot Cesium proof did not report rendered tile content")
                if not isinstance(manifest.get("cesium_renderer_count"), int) or manifest.get("cesium_renderer_count", 0) < 1:
                    findings.append("godot Cesium proof has no rendered tile mesh")
        version = manifest.get("version")
        requested_selector = manifest.get("requested_selector")
        camera_shots = manifest.get("camera_shots")
        expected_camera_shots = _expected_camera_shots()
        if not isinstance(camera_shots, list):
            findings.append("missing camera_shots")
        else:
            normalized_camera_shots: list[dict[str, Any]] = []
            for item in camera_shots:
                if not isinstance(item, dict):
                    normalized_camera_shots = []
                    break
                normalized_camera_shots.append(item)
            if not normalized_camera_shots:
                findings.append("invalid camera_shots")
            else:
                if len(normalized_camera_shots) != len(expected_camera_shots):
                    findings.append("unexpected camera_shot count")
                else:
                    for expected, actual in zip(expected_camera_shots, normalized_camera_shots, strict=False):
                        if actual.get("name") != expected["name"]:
                            findings.append(f"unexpected camera_shot name: {actual.get('name')}")
                            break
                        if actual.get("camera_position") != expected["camera_position"]:
                            findings.append(f"unexpected camera_shot position: {actual.get('name')}")
                            break
                        if actual.get("look_at") != expected["look_at"]:
                            findings.append(f"unexpected camera_shot look_at: {actual.get('name')}")
                            break
                        if actual.get("up") != expected["up"]:
                            findings.append(f"unexpected camera_shot up: {actual.get('name')}")
                            break
                        if actual.get("fov_degrees") != expected["fov_degrees"]:
                            findings.append(f"unexpected camera_shot fov: {actual.get('name')}")
                            break

        expected_names = _expected_png_names(manifest)
        missing_pngs = [name for name in expected_names if name not in png_names]
        unexpected_pngs = [name for name in png_names if name not in expected_names]

        if missing_pngs:
            findings.append(f"missing_pngs: {', '.join(missing_pngs)}")
        if unexpected_pngs:
            findings.append(f"unexpected_pngs: {', '.join(unexpected_pngs)}")

        if not findings:
            status = "pass"

        shot_names = _shot_names(manifest, expected_names)

        return {
            "root": str(root),
            "manifest_path": str(manifest_path),
            "status": status,
            "engine": manifest.get("engine"),
            "native_target": manifest.get("native_target"),
            "architecture": manifest.get("architecture"),
            "version": version,
            "requested_selector": requested_selector,
            "variant_count": len(manifest.get("capture_variants") or []),
            "shot_count": len(shot_names),
            "shot_names": shot_names,
            "camera_shots": camera_shots if isinstance(camera_shots, list) else [],
            "expected_png_names": expected_names,
            "actual_png_names": png_names,
            "findings": findings,
            "manifest_exists": True,
            "png_count": len(png_names),
        }

    return {
        "root": str(root),
        "manifest_path": str(manifest_path),
        "status": status,
        "engine": None,
        "native_target": None,
        "architecture": None,
        "version": None,
        "requested_selector": None,
        "variant_count": 0,
        "shot_count": 0,
        "shot_names": [],
        "expected_png_names": [f"{variant}_{shot}.png" for variant in EXPECTED_VARIANTS for shot in EXPECTED_SHOTS],
        "actual_png_names": png_names,
        "findings": findings,
        "manifest_exists": False,
        "png_count": len(png_names),
    }


def build_payload(scan_roots: list[Path] | None = None) -> dict[str, Any]:
    roots = scan_roots if scan_roots is not None else _discover_default_scan_roots()
    validations = [validate_root(root) for root in roots]
    pass_count = sum(1 for item in validations if item["status"] == "pass")
    fail_count = sum(1 for item in validations if item["status"] == "fail")
    present_engines = sorted(
        {
            str(item["engine"])
            for item in validations
            if item["status"] == "pass" and item.get("engine")
        }
    )
    missing_engines = [engine for engine in EXPECTED_ENGINES if engine not in present_engines]
    if validations and fail_count == 0 and not missing_engines:
        overall_status = "pass"
    elif validations and fail_count == 0:
        overall_status = "partial"
    else:
        overall_status = "fail"
    return {
        "schema": "cesium.visual_proof_roots.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "scan_roots": [str(root) for root in roots],
        "validations": validations,
        "summary": {
            "root_count": len(validations),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "manifest_count": sum(1 for item in validations if item["manifest_exists"]),
            "png_count": sum(item["png_count"] for item in validations),
            "expected_engines": list(EXPECTED_ENGINES),
            "present_engines": present_engines,
            "missing_engines": missing_engines,
            "expected_engine_count": len(EXPECTED_ENGINES),
            "present_engine_count": len(present_engines),
            "missing_engine_count": len(missing_engines),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Visual Proof Roots",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Roots",
        "",
    ]
    for item in payload.get("validations", []):
        lines.append(f"### {item['engine'] or 'unknown'}")
        lines.append(f"- status: `{item['status']}`")
        lines.append(f"- root: `{item['root']}`")
        lines.append(f"- manifest_path: `{item['manifest_path']}`")
        lines.append(f"- png_count: `{item['png_count']}`")
        if item.get("version") is not None:
            lines.append(f"- version: `{item['version']}`")
        if item.get("requested_selector") is not None:
            lines.append(f"- requested_selector: `{item['requested_selector']}`")
        if item.get("findings"):
            lines.append("- findings:")
            for finding in item["findings"]:
                lines.append(f"  - `{finding}`")
    summary = payload.get("summary", {})
    if summary:
        lines.extend(["", "## Engine Coverage", ""])
        lines.append(f"- expected_engines: `{summary.get('expected_engines')}`")
        lines.append(f"- present_engines: `{summary.get('present_engines')}`")
        lines.append(f"- missing_engines: `{summary.get('missing_engines')}`")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", action="append", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args(argv)

    payload = build_payload(args.scan_root)
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
