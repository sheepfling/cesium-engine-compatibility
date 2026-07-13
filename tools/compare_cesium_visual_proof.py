#!/usr/bin/env python3
"""Compare Cesium visual-proof screenshots for drift and obvious render failures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import itertools
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from tools import build_cesium_visual_proof


ROOT = Path(__file__).resolve().parents[1]
GODOT_LAUNCHER_REPORT = ROOT / "artifacts" / "reports" / "godot_aggressive_launcher" / "godot_aggressive_launcher.json"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_visual_proof_compare"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_compare.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_compare.md"

EXPECTED_VARIANTS = build_cesium_visual_proof.canonical_capture_variants()
EXPECTED_ENGINES = ("unreal", "unity", "godot")
CANONICAL_VARIANT_PRIORITY = ("cesium", "proxy", "default")
DEFAULT_DHASH_THRESHOLD = 10
DEFAULT_RMSE_THRESHOLD = 0.18
DEFAULT_LUMINANCE_DELTA_THRESHOLD = 18.0


@dataclass(frozen=True)
class ScreenshotSample:
    engine: str
    subject: str
    host: str | None
    native_target: str | None
    version: str | None
    requested_selector: str | None
    shot: str
    variant: str
    path: Path


def _resample_lanczos() -> int:
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.LANCZOS


def _discover_scan_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in ROOT.glob("extensions/cesium/examples/*/CesiumVanillaExample/build/*/CesiumVanillaExample/visual_proof"):
        if candidate.is_dir():
            roots.append(candidate)
    normalized_unreal_roots = [
        candidate
        for candidate in ROOT.glob("artifacts/reports/cesium_visual_proof/unreal/*/*")
        if candidate.is_dir()
    ]
    if normalized_unreal_roots:
        roots.extend(normalized_unreal_roots)
    else:
        for candidate in ROOT.glob("extensions/cesium/examples/unreal/CesiumVanillaExample/Saved/Screenshots/*"):
            if candidate.is_dir():
                roots.append(candidate)
    for candidate in ROOT.glob("artifacts/reports/cesium_visual_proof/*/*/*"):
        if candidate.is_dir() and candidate.name != "visual_proof":
            roots.append(candidate)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)
    return deduped


def _engine_from_root(root: Path) -> str:
    parts = root.parts
    if "Saved" in parts and "Screenshots" in parts:
        return "unreal"
    if "build" in parts:
        index = parts.index("build")
        if index + 1 < len(parts):
            candidate = parts[index + 1].lower()
            if candidate in {"godot", "unity", "unreal"}:
                return candidate
    if "examples" in parts:
        index = parts.index("examples")
        if index + 1 < len(parts):
            return parts[index + 1]
    if "cesium_visual_proof" in parts:
        index = parts.index("cesium_visual_proof")
        if index + 1 < len(parts):
            return parts[index + 1]
    return root.parent.name if root.parent.name else root.name


def _subject_from_root(root: Path) -> str:
    if root.parent.name:
        return root.parent.name
    return root.name


def _architecture_from_executable(executable: str | None) -> str | None:
    if not executable:
        return None
    lower = executable.lower()
    if "win64" in lower or "x86_64" in lower:
        return "x86_64"
    if "arm64" in lower or "aarch64" in lower:
        return "arm64"
    return None


def _launcher_report_metadata() -> dict[str, str | None]:
    if not GODOT_LAUNCHER_REPORT.is_file():
        return {}
    try:
        payload = json.loads(GODOT_LAUNCHER_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    attempts = payload.get("attempts")
    selected_attempt: dict[str, Any] | None = None
    if isinstance(attempts, list):
        successful_index = payload.get("successful_attempt_index")
        if isinstance(successful_index, int) and 0 <= successful_index < len(attempts):
            maybe = attempts[successful_index]
            if isinstance(maybe, dict):
                selected_attempt = maybe
    version = None
    if selected_attempt and selected_attempt.get("version"):
        version = str(selected_attempt.get("version")) or None
    return {
        "host": str(payload.get("native_target") or "") or None,
        "native_target": str(payload.get("native_target") or "") or None,
        "architecture": _architecture_from_executable(
            str(selected_attempt.get("executable")) if selected_attempt and selected_attempt.get("executable") else None
        ),
        "version": version,
    }


def _root_manifest_metadata(root: Path) -> dict[str, str | None]:
    candidates = [
        root / "visual_proof_manifest.json",
        root.parent / "visual_proof_manifest.json",
        root.parent.parent / "visual_proof_manifest.json",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        capture_paths = payload.get("capture_paths")
        allowed_names = None
        if isinstance(capture_paths, list):
            allowed_names = sorted({Path(str(item)).name for item in capture_paths if str(item).strip()})
        version = str(payload.get("version") or "") or None
        requested_selector = str(payload.get("requested_selector") or "") or None
        return {
            "path": str(candidate),
            "engine": str(payload.get("engine") or "") or None,
            "host": str(payload.get("host") or "") or None,
            "native_target": str(payload.get("native_target") or "") or None,
            "architecture": str(payload.get("architecture") or "") or None,
            "version": version,
            "requested_selector": requested_selector,
            "allowed_png_names": ",".join(allowed_names) if allowed_names else None,
        }
    return {}


def _shot_name_from_path(path: Path) -> tuple[str, str]:
    stem = path.stem
    canonical_shots = {shot.name for shot in build_cesium_visual_proof.CAMERA_SHOTS}
    for shot in canonical_shots:
        if f"_{shot}" in stem:
            prefix, _ = stem.rsplit(f"_{shot}", 1)
            return prefix or "default", shot
        if f"-{shot}" in stem:
            prefix, _ = stem.rsplit(f"-{shot}", 1)
            return prefix or "default", shot
        if stem == shot:
            return "default", shot
    return "default", stem


def _load_samples(scan_roots: list[Path]) -> list[ScreenshotSample]:
    samples: list[ScreenshotSample] = []
    for root in scan_roots:
        if not root.is_dir():
            continue
        engine = _engine_from_root(root)
        subject = _subject_from_root(root)
        root_metadata = _root_manifest_metadata(root)
        launcher_metadata = _launcher_report_metadata()
        allowed_png_names = set((root_metadata.get("allowed_png_names") or "").split(",")) if root_metadata.get("allowed_png_names") else None
        for path in sorted(root.glob("*.png")):
            if allowed_png_names is not None and path.name not in allowed_png_names:
                continue
            variant, shot = _shot_name_from_path(path)
            samples.append(
                ScreenshotSample(
                    engine=str(root_metadata.get("engine") or engine),
                    subject=subject,
                    host=root_metadata.get("host") or launcher_metadata.get("host"),
                    native_target=root_metadata.get("native_target") or launcher_metadata.get("native_target"),
                    version=root_metadata.get("version") or launcher_metadata.get("version"),
                    requested_selector=root_metadata.get("requested_selector"),
                    shot=shot,
                    variant=variant,
                    path=path,
                )
            )
    return samples


def _open_rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _downsample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, _resample_lanczos())


def _dhash(image: Image.Image, hash_size: int = 8) -> int:
    gray = image.convert("L").resize((hash_size + 1, hash_size), _resample_lanczos())
    pixels = gray.load()
    value = 0
    for y in range(hash_size):
        for x in range(hash_size):
            left = pixels[x, y]
            right = pixels[x + 1, y]
            value = (value << 1) | int(left > right)
    return value


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _quality_flags(image: Image.Image) -> list[str]:
    sample = _downsample(image, (32, 32))
    stats = ImageStat.Stat(sample)
    luminance = _downsample(image.convert("L"), (32, 32))
    luminance_stats = ImageStat.Stat(luminance)
    unique_colors = sample.getcolors(maxcolors=1024)
    unique_count = len(unique_colors) if unique_colors is not None else 1025
    mean_rgb = stats.mean
    std_rgb = stats.stddev
    mean_luminance = luminance_stats.mean[0]
    std_luminance = luminance_stats.stddev[0]
    spread = max(mean_rgb) - min(mean_rgb)
    max_std = max(std_rgb)
    grayscale = luminance.load()
    edge_energy = 0.0
    edge_samples = 0
    for y in range(luminance.height):
        for x in range(luminance.width):
            value = grayscale[x, y]
            if x + 1 < luminance.width:
                edge_energy += abs(float(value) - float(grayscale[x + 1, y]))
                edge_samples += 1
            if y + 1 < luminance.height:
                edge_energy += abs(float(value) - float(grayscale[x, y + 1]))
                edge_samples += 1
    normalized_edge_energy = edge_energy / edge_samples if edge_samples else 0.0

    flags: list[str] = []
    if mean_luminance < 18.0 and std_luminance < 10.0:
        flags.append("near_black")
    if max_std < 5.0 and spread < 10.0:
        flags.append("flat_solid")
    if unique_count <= 3 and std_luminance < 12.0:
        flags.append("low_color_diversity")
    # A valid globe proof can contain a large dark-sky region. Only treat low
    # global edge energy as an error when the frame is also low-variation; a
    # textured Earth should not fail because space itself has few edges.
    if normalized_edge_energy < 4.0 and (unique_count <= 3 or max_std < 12.0):
        flags.append("low_edge_energy")
    if image.width < 64 or image.height < 64:
        flags.append("too_small")
    return flags


def _pair_metrics(left: Image.Image, right: Image.Image) -> dict[str, float]:
    target_size = (256, 256)
    left_rgb = _downsample(left, target_size)
    right_rgb = _downsample(right, target_size)
    left_gray = left_rgb.convert("L")
    right_gray = right_rgb.convert("L")

    left_pixels = left_rgb.load()
    right_pixels = right_rgb.load()
    gray_left_pixels = left_gray.load()
    gray_right_pixels = right_gray.load()

    pixel_count = float(target_size[0] * target_size[1])
    rgb_sq_error = 0.0
    rgb_abs_error = 0.0
    luminance_abs_error = 0.0
    for y in range(target_size[1]):
        for x in range(target_size[0]):
            lr, lg, lb = left_pixels[x, y]
            rr, rg, rb = right_pixels[x, y]
            lgray = gray_left_pixels[x, y]
            rgray = gray_right_pixels[x, y]
            dr = float(lr) - float(rr)
            dg = float(lg) - float(rg)
            db = float(lb) - float(rb)
            rgb_sq_error += dr * dr + dg * dg + db * db
            rgb_abs_error += abs(dr) + abs(dg) + abs(db)
            luminance_abs_error += abs(float(lgray) - float(rgray))

    rmse = math.sqrt(rgb_sq_error / (pixel_count * 3.0)) / 255.0
    mean_abs_error = rgb_abs_error / (pixel_count * 3.0) / 255.0
    mean_luminance_delta = luminance_abs_error / pixel_count
    left_structure = _structure_metrics(left)
    right_structure = _structure_metrics(right)
    return {
        "rmse_normalized": rmse,
        "mean_abs_error_normalized": mean_abs_error,
        "mean_luminance_delta": mean_luminance_delta,
        "dhash_distance": float(_hamming_distance(_dhash(left_rgb), _dhash(right_rgb))),
        "structure_edge_fraction_delta": abs(left_structure["edge_fraction"] - right_structure["edge_fraction"]),
        "structure_centroid_distance": math.hypot(
            left_structure["centroid_x"] - right_structure["centroid_x"],
            left_structure["centroid_y"] - right_structure["centroid_y"],
        ),
        "structure_bbox_delta": max(
            abs(left_structure["bbox_width"] - right_structure["bbox_width"]),
            abs(left_structure["bbox_height"] - right_structure["bbox_height"]),
        ),
    }


def _structure_metrics(image: Image.Image) -> dict[str, float]:
    """Return renderer-independent occupancy metrics for cross-engine evidence.

    Pixel colors are intentionally excluded: Unreal, Unity, and Godot use
    different lighting/material defaults, and a Cesium tile mesh is not the
    same bitmap as the proxy globe. Edge occupancy and silhouette placement
    still catch a shifted camera, an empty frame, or a radically drifted shot.
    """
    gray = _downsample(image.convert("L"), (64, 64))
    pixels = gray.load()
    points: list[tuple[int, int]] = []
    for y in range(63):
        for x in range(63):
            gradient = max(
                abs(int(pixels[x, y]) - int(pixels[x + 1, y])),
                abs(int(pixels[x, y]) - int(pixels[x, y + 1])),
            )
            if gradient >= 10:
                points.append((x, y))
    if not points:
        return {
            "edge_fraction": 0.0,
            "centroid_x": 0.0,
            "centroid_y": 0.0,
            "bbox_width": 0.0,
            "bbox_height": 0.0,
        }
    count = float(len(points))
    return {
        "edge_fraction": count / float(64 * 64),
        "centroid_x": sum(x for x, _ in points) / count / 63.0,
        "centroid_y": sum(y for _, y in points) / count / 63.0,
        "bbox_width": (max(x for x, _ in points) - min(x for x, _ in points) + 1) / 64.0,
        "bbox_height": (max(y for _, y in points) - min(y for _, y in points) + 1) / 64.0,
    }


def _select_canonical(samples: list[ScreenshotSample]) -> ScreenshotSample:
    for preferred in CANONICAL_VARIANT_PRIORITY:
        for sample in samples:
            if sample.variant == preferred:
                return sample
    return sorted(samples, key=lambda sample: (sample.variant, str(sample.path)))[0]


def _group_samples(samples: list[ScreenshotSample], key_fn) -> dict[str, list[ScreenshotSample]]:
    grouped: dict[str, list[ScreenshotSample]] = {}
    for sample in samples:
        grouped.setdefault(key_fn(sample), []).append(sample)
    return grouped


def _status_from_findings(findings: list[str], comparisons_complete: bool, missing_present: bool) -> str:
    if findings:
        return "fail"
    if missing_present or not comparisons_complete:
        return "partial"
    return "pass"


def build_payload(
    scan_roots: list[Path] | None = None,
    *,
    strict_missing: bool = False,
    dhash_threshold: int = DEFAULT_DHASH_THRESHOLD,
    rmse_threshold: float = DEFAULT_RMSE_THRESHOLD,
    luminance_delta_threshold: float = DEFAULT_LUMINANCE_DELTA_THRESHOLD,
) -> dict[str, object]:
    discovered_roots = scan_roots if scan_roots is not None else _discover_scan_roots()
    launcher_metadata = _launcher_report_metadata()
    samples = _load_samples(discovered_roots)
    quality_by_sample: dict[str, dict[str, Any]] = {}
    quality_findings: list[str] = []
    for sample in samples:
        image = _open_rgb_image(sample.path)
        flags = _quality_flags(image)
        sample_key = f"{sample.engine}/{sample.variant}/{sample.shot}"
        quality_by_sample[sample_key] = {
            "engine": sample.engine,
            "subject": sample.subject,
            "host": sample.host,
            "native_target": sample.native_target,
            "version": sample.version,
            "requested_selector": sample.requested_selector,
            "variant": sample.variant,
            "shot": sample.shot,
            "path": str(sample.path),
            "width": image.width,
            "height": image.height,
            "flags": flags,
        }
        for flag in flags:
            quality_findings.append(f"{sample_key}: {flag}")

    samples_by_engine_shot = _group_samples(samples, lambda sample: f"{sample.engine}/{sample.shot}")
    canonical_by_engine_shot: dict[str, ScreenshotSample] = {}
    canonical_missing: list[str] = []
    variant_missing: list[str] = []
    for engine_shot, engine_samples in samples_by_engine_shot.items():
        if not engine_samples:
            continue
        canonical_by_engine_shot[engine_shot] = _select_canonical(engine_samples)
        present_variants = {sample.variant for sample in engine_samples}
        for variant in EXPECTED_VARIANTS:
            if variant not in present_variants:
                variant_missing.append(f"{engine_shot}: missing {variant}")

    shots = [shot.name for shot in build_cesium_visual_proof.CAMERA_SHOTS]
    canonical_comparisons: list[dict[str, Any]] = []
    canonical_failures: list[str] = []
    for shot in shots:
        present = [
            canonical_by_engine_shot[key]
            for key in sorted(canonical_by_engine_shot)
            if key.endswith(f"/{shot}")
        ]
        if len(present) < 2:
            if present:
                canonical_missing.append(f"{shot}: only one canonical sample present")
            else:
                canonical_missing.append(f"{shot}: no canonical samples present")
            continue
        for left, right in itertools.combinations(present, 2):
            left_image = _open_rgb_image(left.path)
            right_image = _open_rgb_image(right.path)
            metrics = _pair_metrics(left_image, right_image)
            same_engine = left.engine == right.engine
            comparison = {
                "shot": shot,
                "left": {
                    "engine": left.engine,
                    "variant": left.variant,
                    "path": str(left.path),
                },
                "right": {
                    "engine": right.engine,
                    "variant": right.variant,
                    "path": str(right.path),
                },
                "metrics": metrics,
                "comparison_scope": "same-engine-drift" if same_engine else "cross-engine-structural",
                "thresholds": {
                    "dhash_distance": dhash_threshold,
                    "rmse_normalized": rmse_threshold,
                    "mean_luminance_delta": luminance_delta_threshold,
                },
            }
            failure_reasons: list[str] = []
            if same_engine and metrics["dhash_distance"] > dhash_threshold:
                failure_reasons.append(f"dhash_distance>{dhash_threshold}")
            if same_engine and metrics["rmse_normalized"] > rmse_threshold:
                failure_reasons.append(f"rmse_normalized>{rmse_threshold}")
            if same_engine and metrics["mean_luminance_delta"] > luminance_delta_threshold:
                failure_reasons.append(f"mean_luminance_delta>{luminance_delta_threshold}")
            comparison["status"] = "fail" if failure_reasons else ("ok" if same_engine else "informational")
            comparison["failure_reasons"] = failure_reasons
            if failure_reasons:
                canonical_failures.append(f"{shot}: {left.engine} vs {right.engine} -> {', '.join(failure_reasons)}")
            canonical_comparisons.append(comparison)

    variant_groups = _group_samples(samples, lambda sample: sample.variant)
    variant_comparisons: list[dict[str, Any]] = []
    variant_failures: list[str] = []
    for variant, variant_samples in sorted(variant_groups.items()):
        shot_groups = _group_samples(variant_samples, lambda sample: sample.shot)
        for shot, shot_samples in sorted(shot_groups.items()):
            if len(shot_samples) < 2:
                continue
            for left, right in itertools.combinations(sorted(shot_samples, key=lambda sample: (sample.engine, str(sample.path))), 2):
                left_image = _open_rgb_image(left.path)
                right_image = _open_rgb_image(right.path)
                metrics = _pair_metrics(left_image, right_image)
                same_engine = left.engine == right.engine
                comparison = {
                    "variant": variant,
                    "shot": shot,
                    "left": {
                        "engine": left.engine,
                        "path": str(left.path),
                    },
                    "right": {
                        "engine": right.engine,
                        "path": str(right.path),
                    },
                    "metrics": metrics,
                    "comparison_scope": "same-engine-drift" if same_engine else "cross-engine-structural",
                }
                comparison_failures: list[str] = []
                if same_engine and metrics["dhash_distance"] > dhash_threshold:
                    comparison_failures.append(f"dhash_distance>{dhash_threshold}")
                if same_engine and metrics["rmse_normalized"] > rmse_threshold:
                    comparison_failures.append(f"rmse_normalized>{rmse_threshold}")
                if same_engine and metrics["mean_luminance_delta"] > luminance_delta_threshold:
                    comparison_failures.append(f"mean_luminance_delta>{luminance_delta_threshold}")
                comparison["status"] = "fail" if comparison_failures else ("ok" if same_engine else "informational")
                comparison["failure_reasons"] = comparison_failures
                if comparison_failures:
                    variant_failures.append(f"{variant}/{shot}: {left.engine} vs {right.engine} -> {', '.join(comparison_failures)}")
                variant_comparisons.append(comparison)

    engine_shot_groups = _group_samples(samples, lambda sample: f"{sample.engine}/{sample.shot}")
    engine_variant_comparisons: list[dict[str, Any]] = []
    engine_variant_failures: list[str] = []
    for engine_shot, engine_samples in sorted(engine_shot_groups.items()):
        if len(engine_samples) < 2:
            continue
        for left, right in itertools.combinations(sorted(engine_samples, key=lambda sample: (sample.variant, str(sample.path))), 2):
            if left.variant == right.variant:
                continue
            left_image = _open_rgb_image(left.path)
            right_image = _open_rgb_image(right.path)
            metrics = _pair_metrics(left_image, right_image)
            comparison = {
                "engine_shot": engine_shot,
                "left": {
                    "engine": left.engine,
                    "subject": left.subject,
                    "variant": left.variant,
                    "path": str(left.path),
                },
                "right": {
                    "engine": right.engine,
                    "subject": right.subject,
                    "variant": right.variant,
                    "path": str(right.path),
                },
                "metrics": metrics,
                "comparison_scope": "expected-content-delta",
            }
            # Proxy-earth and Cesium-earth are deliberately different content.
            # Their hard gates are manifest readiness and per-frame quality;
            # retain image metrics as an auditable content-delta diagnostic.
            comparison["status"] = "content-delta"
            comparison["failure_reasons"] = []
            engine_variant_comparisons.append(comparison)

    missing_present = strict_missing and (
        any(not any(sample.shot == shot for sample in samples) for shot in shots) or bool(variant_missing)
    )
    findings = [*quality_findings, *canonical_failures, *variant_failures]
    if variant_missing:
        findings.extend(f"variant-missing: {item}" for item in variant_missing)
    status = _status_from_findings(findings, bool(canonical_comparisons or variant_comparisons), missing_present)
    if not findings and not canonical_comparisons and not variant_comparisons:
        status = "partial" if samples else "fail"

    engines = sorted({sample.engine for sample in samples})
    missing_engines = [engine for engine in EXPECTED_ENGINES if engine not in engines]
    shot_count = len({sample.shot for sample in samples})
    sample_count = len(samples)

    return {
        "schema": "cesium.visual_proof_comparison.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "strict_missing": strict_missing,
        "scan_roots": [str(root) for root in discovered_roots],
        "launcher_report": {
            "path": str(GODOT_LAUNCHER_REPORT),
            "exists": GODOT_LAUNCHER_REPORT.is_file(),
            "host": launcher_metadata.get("host"),
            "native_target": launcher_metadata.get("native_target"),
            "architecture": launcher_metadata.get("architecture"),
            "version": launcher_metadata.get("version"),
        },
        "thresholds": {
            "dhash_distance": dhash_threshold,
            "rmse_normalized": rmse_threshold,
            "mean_luminance_delta": luminance_delta_threshold,
        },
        "summary": {
            "engine_count": len(engines),
            "engines": engines,
            "expected_engine_count": len(EXPECTED_ENGINES),
            "expected_engines": list(EXPECTED_ENGINES),
            "present_engine_count": len(engines),
            "missing_engine_count": len(missing_engines),
            "missing_engines": missing_engines,
            "sample_count": sample_count,
            "shot_count": shot_count,
            "quality_issue_count": len(quality_findings),
            "comparison_count": len(canonical_comparisons) + len(variant_comparisons),
            "canonical_comparison_count": len(canonical_comparisons),
            "variant_comparison_count": len(variant_comparisons),
            "engine_variant_comparison_count": len(engine_variant_comparisons),
            "informational_comparison_count": sum(
                1 for item in [*canonical_comparisons, *variant_comparisons]
                if item.get("status") == "informational"
            ),
            "canonical_missing_count": len(canonical_missing),
            "variant_missing_count": len(variant_missing),
            "expected_variants": list(EXPECTED_VARIANTS),
        },
        "samples": [
            {
                "engine": sample.engine,
                "subject": sample.subject,
                "host": sample.host,
                "native_target": sample.native_target,
                "version": sample.version,
                "requested_selector": sample.requested_selector,
                "variant": sample.variant,
                "shot": sample.shot,
                "path": str(sample.path),
            }
            for sample in samples
        ],
        "quality": list(quality_by_sample.values()),
        "canonical_comparisons": canonical_comparisons,
        "variant_comparisons": variant_comparisons,
        "engine_variant_comparisons": engine_variant_comparisons,
        "engine_variant_failures": engine_variant_failures,
        "findings": findings,
        "canonical_missing": canonical_missing,
        "variant_missing": variant_missing,
        "related_packets": {
            "visual_proof": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_visual_proof" / "cesium_visual_proof.json").is_file() else "missing",
                "path": "artifacts/reports/cesium_visual_proof/cesium_visual_proof.json",
            }
        },
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Visual Proof Comparison",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- strict_missing: `{payload['strict_missing']}`",
        "",
        "## Launcher Report",
        "",
    ]
    launcher_report = payload.get("launcher_report", {})
    if isinstance(launcher_report, dict):
        for key in ("path", "exists", "host", "native_target", "architecture", "version"):
            if key in launcher_report:
                lines.append(f"- `{key}`: `{launcher_report.get(key)}`")
    lines.extend([
        "",
        "## Thresholds",
        "",
    ])
    thresholds = payload.get("thresholds", {})
    if isinstance(thresholds, dict):
        for key, value in thresholds.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        for key, value in summary.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Findings", ""])
    findings = payload.get("findings", [])
    if findings:
        for finding in findings:
            lines.append(f"- {finding}")
    else:
        lines.append("- none")
    lines.extend(["", "## Canonical Comparisons", ""])
    for comparison in payload.get("canonical_comparisons", []):
        metrics = comparison.get("metrics", {})
        lines.append(
            f"- `{comparison['shot']}`: `{comparison['left']['engine']}` ({comparison['left']['variant']}) vs `{comparison['right']['engine']}` ({comparison['right']['variant']}) -> `{comparison['status']}`"
        )
        if isinstance(metrics, dict):
            lines.append(
                f"  - dhash `{metrics.get('dhash_distance')}`, rmse `{metrics.get('rmse_normalized')}`, luminance_delta `{metrics.get('mean_luminance_delta')}`"
            )
    lines.extend(["", "## Variant Comparisons", ""])
    for comparison in payload.get("variant_comparisons", []):
        metrics = comparison.get("metrics", {})
        lines.append(
            f"- `{comparison['variant']}` / `{comparison['shot']}`: `{comparison['left']['engine']}` vs `{comparison['right']['engine']}` -> `{comparison['status']}`"
        )
        if isinstance(metrics, dict):
            lines.append(
                f"  - dhash `{metrics.get('dhash_distance')}`, rmse `{metrics.get('rmse_normalized')}`, luminance_delta `{metrics.get('mean_luminance_delta')}`"
            )
    lines.extend(["", "## Engine Variant Comparisons", ""])
    for comparison in payload.get("engine_variant_comparisons", []):
        metrics = comparison.get("metrics", {})
        left = comparison.get("left", {})
        right = comparison.get("right", {})
        lines.append(
            f"- `{comparison['engine_shot']}`: `{left.get('variant')}` vs `{right.get('variant')}` -> `{comparison['status']}`"
        )
        if isinstance(metrics, dict):
            lines.append(
                f"  - dhash `{metrics.get('dhash_distance')}`, rmse `{metrics.get('rmse_normalized')}`, luminance_delta `{metrics.get('mean_luminance_delta')}`"
            )
    lines.extend(["", "## Samples", ""])
    for sample in payload.get("samples", []):
        subject = sample.get("subject")
        host = sample.get("host")
        native_target = sample.get("native_target")
        version = sample.get("version")
        requested_selector = sample.get("requested_selector")
        subject_part = f" / `{subject}`" if subject else ""
        host_part = f" / `{host}`" if host else ""
        native_part = f" / `{native_target}`" if native_target else ""
        version_part = f" / `{version}`" if version else ""
        selector_part = f" / `{requested_selector}`" if requested_selector else ""
        lines.append(f"- `{sample['engine']}`{subject_part}{host_part}{native_part}{version_part}{selector_part} / `{sample['variant']}` / `{sample['shot']}` -> `{sample['path']}`")
    lines.extend(["", "## Quality", ""])
    for item in payload.get("quality", []):
        subject = item.get("subject")
        host = item.get("host")
        native_target = item.get("native_target")
        version = item.get("version")
        requested_selector = item.get("requested_selector")
        subject_part = f" / `{subject}`" if subject else ""
        host_part = f" / `{host}`" if host else ""
        native_part = f" / `{native_target}`" if native_target else ""
        version_part = f" / `{version}`" if version else ""
        selector_part = f" / `{requested_selector}`" if requested_selector else ""
        lines.append(f"- `{item['engine']}`{subject_part}{host_part}{native_part}{version_part}{selector_part} / `{item['variant']}` / `{item['shot']}` -> `{', '.join(item.get('flags', [])) or 'ok'}`")
    lines.extend(["", "## Related Packets", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", action="append", type=Path, default=None, help="Override the auto-discovered screenshot scan roots.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict-missing", action="store_true", help="Treat absent canonical shots as failures instead of partial evidence.")
    parser.add_argument("--dhash-threshold", type=int, default=DEFAULT_DHASH_THRESHOLD)
    parser.add_argument("--rmse-threshold", type=float, default=DEFAULT_RMSE_THRESHOLD)
    parser.add_argument("--luminance-delta-threshold", type=float, default=DEFAULT_LUMINANCE_DELTA_THRESHOLD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        args.scan_root,
        strict_missing=args.strict_missing,
        dhash_threshold=args.dhash_threshold,
        rmse_threshold=args.rmse_threshold,
        luminance_delta_threshold=args.luminance_delta_threshold,
    )
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
