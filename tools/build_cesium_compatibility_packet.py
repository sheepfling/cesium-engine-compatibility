#!/usr/bin/env python3
"""Build a single compatibility packet from the current matrix and audit reports."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import (
    build_cesium_engine_matrix,
    build_cesium_fork_workpack,
    build_cesium_execution_audit,
    build_cesium_planned_routes,
    build_unity_native_matrix,
    build_cesium_visual_proof,
    build_windows_visual_proof,
    build_unreal_visual_proof,
    compare_cesium_visual_proof,
    proof_runs,
    validate_visual_proof_audit,
    validate_visual_proof_roots,
)


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_compatibility_packet"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_compatibility_packet.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_compatibility_packet.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args(argv)


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = f"{row.get('kind') or 'unknown'}::{row.get('path') or row.get('command') or row.get('lane') or row.get('surface') or ''}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _visual_proof_root_gaps(visual_roots: dict[str, Any], visual_audit: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    summary = visual_roots.get("summary") if isinstance(visual_roots.get("summary"), dict) else {}
    missing_engines = summary.get("missing_engines") if isinstance(summary, dict) else None
    if isinstance(missing_engines, list) and missing_engines:
        joined = ", ".join(str(engine) for engine in missing_engines if str(engine))
        if joined:
            gaps.append(f"visual proof root coverage still missing: {joined}")
    root_engine_coverage_status = visual_audit.get("summary", {}).get("root_engine_coverage_status") if isinstance(visual_audit.get("summary"), dict) else None
    if root_engine_coverage_status == "partial" and not gaps:
        gaps.append("visual proof root coverage is partial")
    return gaps


def build_payload() -> dict[str, object]:
    matrix = build_cesium_engine_matrix.build_payload()
    fork_workpack = build_cesium_fork_workpack.build_payload()
    unity_native = build_unity_native_matrix.build_payload()
    audit = build_cesium_execution_audit.build_payload()
    planned_routes = build_cesium_planned_routes.build_payload()
    visual_proof = build_cesium_visual_proof.build_payload()
    windows_visual_proof = build_windows_visual_proof.build_payload()
    unreal_visual_proof = build_unreal_visual_proof.build_payload()
    visual_compare = compare_cesium_visual_proof.build_payload()
    visual_roots = validate_visual_proof_roots.build_payload()
    visual_audit = validate_visual_proof_audit.build_payload()
    matrix_evidence = matrix.get("evidence") if isinstance(matrix.get("evidence"), list) else []
    unity_evidence = unity_native.get("evidence") if isinstance(unity_native.get("evidence"), list) else []
    audit_evidence = audit.get("evidence") if isinstance(audit.get("evidence"), list) else []
    visual_evidence = [
        {
            "surface": f"{target['engine']}-{target['native_target']}-{target['architecture']}",
            "kind": "visual_proof_target",
            "path": str(target.get("capture_root") or ""),
        }
        for target in visual_proof.get("targets", [])
        if isinstance(target, dict)
    ]
    visual_runner_evidence = [
        {
            "surface": f"{target['engine']}-{target['native_target']}-{target['architecture']}-runner",
            "kind": "visual_proof_runner",
            "path": str(target.get("proof_runner", {}).get("normalized_capture_root") or target.get("capture_root") or ""),
        }
        for target in visual_proof.get("targets", [])
        if isinstance(target, dict) and isinstance(target.get("proof_runner"), dict)
    ]
    visual_compare_evidence = [
        {
            "surface": "visual-proof-compare",
            "kind": "visual_proof_comparison",
            "path": str(ROOT / "artifacts" / "reports" / "cesium_visual_proof_compare" / "cesium_visual_proof_compare.json"),
        }
    ]
    windows_visual_proof_evidence = [
        {
            "surface": "windows-visual-proof",
            "kind": "windows_visual_proof_report",
            "path": str(ROOT / "artifacts" / "reports" / "windows_visual_proof" / "windows_visual_proof.json"),
        }
    ]
    windows_visual_proof_run_evidence = [
        {
            "surface": "windows-visual-proof-run",
            "kind": "windows_visual_proof_run_report",
            "path": str(ROOT / "artifacts" / "reports" / "windows_visual_proof_run" / "windows_visual_proof_run.json"),
        }
    ]
    visual_roots_evidence = [
        {
            "surface": f"visual-proof-root-{root.get('engine') or 'unknown'}",
            "kind": "visual_proof_root_validation",
            "path": str(root.get("manifest_path") or root.get("root") or ""),
        }
        for root in visual_roots.get("validations", [])
        if isinstance(root, dict)
    ]
    visual_audit_evidence = [
        {
            "surface": "visual-proof-audit",
            "kind": "visual_proof_audit",
            "path": str(ROOT / "artifacts" / "reports" / "cesium_visual_proof_audit" / "cesium_visual_proof_audit.json"),
        }
    ]
    unreal_visual_proof_evidence = [
        {
            "surface": "unreal-visual-proof",
            "kind": "unreal_visual_proof_report",
            "path": str(ROOT / "artifacts" / "reports" / "unreal_visual_proof" / "unreal_visual_proof.json"),
        }
    ]
    evidence = _dedupe_rows([
        *matrix_evidence,
        *unity_evidence,
        *audit_evidence,
        *visual_evidence,
        *visual_runner_evidence,
        *windows_visual_proof_evidence,
        *windows_visual_proof_run_evidence,
        *unreal_visual_proof_evidence,
        *visual_compare_evidence,
        *visual_roots_evidence,
        *visual_audit_evidence,
    ])
    claim_boundaries = [
        "This packet unions the matrix and audit so the final cross-platform picture is visible in one place.",
        "Verified lanes remain distinct from planned lanes; a packet-level rollup is not a substitute for live build evidence.",
        "Unreal Linux still needs the mounted platform-support tree, Unity Linux/Docker has a live Docker report but not build-green proof, Unity macOS remains planned, and Godot macOS remains the live follow-up surface.",
        "The Unity native matrix is folded into the packet so installed-editor spread and target planning stay tied to the same proof set.",
        "The visual-proof packet captures the canonical screenshot camera poses and output paths, but it still needs an engine-side capture harness before those images can count as live proof.",
        "The Unreal Windows visual-proof report is now a dedicated packet entry that records the exact automation tests and normalize command for the shared capture root, and it leverages the upstream CesiumVisualProof.spec.cpp harness from the external Cesium Unreal checkout.",
        "The visual-proof comparison report adds a perceptual-image drift gate so black screens, flat fills, and large cross-engine divergences are visible before the packet is defended.",
        "The visual-proof-root validator audits the manifest-backed proof roots so live PNG sets can be checked programmatically once a lane runs.",
        "The visual-proof audit composes the contract, root, and comparison gates into one machine-checkable pass for the full visual-proof stack.",
        "The fork workpack records the exact Cesium workspace revision and the per-engine/per-host green checklist so fork work stays reproducible.",
    ]
    matrix_gaps = matrix.get("gaps") if isinstance(matrix.get("gaps"), list) else []
    unity_gaps = unity_native.get("gaps") if isinstance(unity_native.get("gaps"), list) else []
    audit_gaps = audit.get("gaps") if isinstance(audit.get("gaps"), list) else []
    visual_gaps = _visual_proof_root_gaps(visual_roots, visual_audit)
    gaps = list(dict.fromkeys([*matrix_gaps, *unity_gaps, *audit_gaps, *visual_gaps]))
    status = "fail" if any(report.get("status") == "fail" or report.get("overall_status") == "fail" for report in (matrix, audit)) else "partial"
    if status != "fail" and not gaps:
        status = "pass"
    return {
        "schema": "cesium.compatibility_packet.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "claim_boundaries": claim_boundaries,
        "evidence": evidence,
        "gaps": gaps,
        "related_packets": {
            "engine_matrix": {
                "status": matrix.get("status"),
                "path": "artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json",
            },
            "unity_native_matrix": {
                "status": unity_native.get("status"),
                "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
            },
            "execution_audit": {
                "status": audit.get("overall_status"),
                "path": "artifacts/reports/cesium_execution_audit/cesium_execution_audit.json",
            },
            "planned_routes": {
                "status": planned_routes.get("status"),
                "path": "artifacts/reports/cesium_planned_routes/cesium_planned_routes.json",
            },
            "fork_workpack": {
                "status": fork_workpack.get("status"),
                "path": "artifacts/reports/cesium_fork_workpack/cesium_fork_workpack.json",
            },
            "visual_proof": {
                "status": visual_proof.get("status"),
                "path": "artifacts/reports/cesium_visual_proof/cesium_visual_proof.json",
            },
            "windows_visual_proof": {
                "status": windows_visual_proof.get("status"),
                "path": "artifacts/reports/windows_visual_proof/windows_visual_proof.json",
            },
            "windows_visual_proof_run": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "windows_visual_proof_run" / "windows_visual_proof_run.json").is_file() else "missing",
                "path": "artifacts/reports/windows_visual_proof_run/windows_visual_proof_run.json",
            },
            "unreal_visual_proof": {
                "status": unreal_visual_proof.get("status"),
                "path": "artifacts/reports/unreal_visual_proof/unreal_visual_proof.json",
            },
            "visual_proof_compare": {
                "status": visual_compare.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_compare/cesium_visual_proof_compare.json",
            },
            "visual_proof_roots": {
                "status": visual_roots.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_roots/cesium_visual_proof_roots.json",
            },
            "visual_proof_audit": {
                "status": visual_audit.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_audit/cesium_visual_proof_audit.json",
            },
        },
        "summary": {
            "matrix_status": matrix.get("status"),
            "unity_native_status": unity_native.get("status"),
            "audit_status": audit.get("overall_status"),
            "planned_routes_status": planned_routes.get("status"),
            "fork_workpack_status": fork_workpack.get("status"),
            "visual_proof_status": visual_proof.get("status"),
            "windows_visual_proof_status": windows_visual_proof.get("status"),
            "unreal_visual_proof_status": unreal_visual_proof.get("status"),
            "visual_proof_compare_status": visual_compare.get("status"),
            "visual_proof_roots_status": visual_roots.get("status"),
            "visual_proof_audit_status": visual_audit.get("status"),
            "lane_count": matrix.get("lane_count"),
            "verified_lane_count": matrix.get("summary", {}).get("verified_lane_count") if isinstance(matrix.get("summary"), dict) else None,
            "planned_lane_count": matrix.get("summary", {}).get("planned_lane_count") if isinstance(matrix.get("summary"), dict) else None,
            "evidence_count": len(evidence),
            "next_proof_runs": proof_runs.next_proof_runs(),
        },
        "reports": {
            "engine_matrix": {
                "status": matrix.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_engine_matrix" / "cesium_engine_matrix.json").relative_to(ROOT)),
            },
            "unity_native_matrix": {
                "status": unity_native.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "unity_native_matrix" / "unity_native_matrix.json").relative_to(ROOT)),
            },
            "execution_audit": {
                "status": audit.get("overall_status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_execution_audit" / "cesium_execution_audit.json").relative_to(ROOT)),
            },
            "planned_routes": {
                "status": "present" if (ROOT / "artifacts" / "reports" / "cesium_planned_routes" / "cesium_planned_routes.json").is_file() else "missing",
                "path": str((ROOT / "artifacts" / "reports" / "cesium_planned_routes" / "cesium_planned_routes.json").relative_to(ROOT)),
            },
            "fork_workpack": {
                "status": fork_workpack.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_fork_workpack" / "cesium_fork_workpack.json").relative_to(ROOT)),
            },
            "visual_proof": {
                "status": visual_proof.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_visual_proof" / "cesium_visual_proof.json").relative_to(ROOT)),
            },
            "windows_visual_proof": {
                "status": windows_visual_proof.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "windows_visual_proof" / "windows_visual_proof.json").relative_to(ROOT)),
            },
            "unreal_visual_proof": {
                "status": unreal_visual_proof.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "unreal_visual_proof" / "unreal_visual_proof.json").relative_to(ROOT)),
            },
            "visual_proof_compare": {
                "status": visual_compare.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_visual_proof_compare" / "cesium_visual_proof_compare.json").relative_to(ROOT)),
            },
            "visual_proof_roots": {
                "status": visual_roots.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_visual_proof_roots" / "cesium_visual_proof_roots.json").relative_to(ROOT)),
            },
            "visual_proof_audit": {
                "status": visual_audit.get("status"),
                "path": str((ROOT / "artifacts" / "reports" / "cesium_visual_proof_audit" / "cesium_visual_proof_audit.json").relative_to(ROOT)),
            },
            "packet_summary": {
                "path": "docs/CESIUM_PR_PACKET_SUMMARY.md",
                "exists": (ROOT / "docs" / "CESIUM_PR_PACKET_SUMMARY.md").is_file(),
            },
        },
        "matrix": matrix,
        "fork_workpack": fork_workpack,
        "audit": audit,
        "visual_proof": visual_proof,
        "visual_proof_compare": visual_compare,
        "visual_proof_roots": visual_roots,
        "visual_proof_audit": visual_audit,
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Cesium Compatibility Packet",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for note in payload.get("claim_boundaries", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Evidence", ""])
    for row in payload.get("evidence", []):
        lines.append(f"- `{row['surface']}`: `{row['kind']}` -> `{row['path']}`")
    lines.extend(["", "## Packet Graph", ""])
    for packet in [
        "cesium-engine-matrix",
        "cesium-unity-native-matrix",
        "cesium-execution-audit",
        "cesium-planned-routes",
        "cesium-visual-proof",
        "cesium-visual-proof-roots",
        "cesium-visual-proof-audit",
    ]:
        lines.append(f"- `{packet}`")
    lines.extend(["", "## Packet Status", ""])
    related = payload.get("related_packets", {})
    if isinstance(related, dict):
        for name, report in related.items():
            if isinstance(report, dict):
                lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Gaps", ""])
    if payload.get("gaps"):
        for gap in payload["gaps"]:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "## Reports", ""])
    for name, report in payload.get("reports", {}).items():
        if isinstance(report, dict):
            lines.append(f"- `{name}`: `{report.get('status') or report.get('overall_status') or 'n/a'}`")
            for key, value in report.items():
                lines.append(f"  - `{key}`: `{value}`")
        else:
            lines.append(f"- `{name}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    lines.append(f"- matrix_status: `{summary.get('matrix_status')}`")
    lines.append(f"- audit_status: `{summary.get('audit_status')}`")
    lines.append(f"- planned_routes_status: `{summary.get('planned_routes_status')}`")
    lines.append(f"- lane_count: `{summary.get('lane_count')}`")
    lines.append(f"- verified_lane_count: `{summary.get('verified_lane_count')}`")
    lines.append(f"- planned_lane_count: `{summary.get('planned_lane_count')}`")
    lines.append(f"- evidence_count: `{summary.get('evidence_count')}`")
    lines.extend(["", "## Next Proof Runs", ""])
    for run in summary.get("next_proof_runs", []):
        lines.append(f"- `{run['surface']}`: `{run['command']}`")
        for focus in run.get("capture_focus", []):
            lines.append(f"  - {focus}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, object], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload()
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
