#!/usr/bin/env python3
"""Build a single compatibility packet from the current matrix and audit reports."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import build_cesium_engine_matrix, build_cesium_execution_audit, build_cesium_planned_routes, build_unity_native_matrix, proof_runs


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
        key = str(row.get("path") or row.get("command") or row.get("lane") or row.get("surface") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_payload() -> dict[str, object]:
    matrix = build_cesium_engine_matrix.build_payload()
    unity_native = build_unity_native_matrix.build_payload()
    audit = build_cesium_execution_audit.build_payload()
    planned_routes = build_cesium_planned_routes.build_payload()
    matrix_evidence = matrix.get("evidence") if isinstance(matrix.get("evidence"), list) else []
    unity_evidence = unity_native.get("evidence") if isinstance(unity_native.get("evidence"), list) else []
    audit_evidence = audit.get("evidence") if isinstance(audit.get("evidence"), list) else []
    evidence = _dedupe_rows([*matrix_evidence, *unity_evidence, *audit_evidence])
    claim_boundaries = [
        "This packet unions the matrix and audit so the final cross-platform picture is visible in one place.",
        "Verified lanes remain distinct from planned lanes; a packet-level rollup is not a substitute for live build evidence.",
        "Unreal Linux still needs the mounted platform-support tree, Unity Linux/Docker has a live Docker report but not build-green proof, Unity macOS remains planned, and Godot macOS remains the live follow-up surface.",
        "The Unity native matrix is folded into the packet so installed-editor spread and target planning stay tied to the same proof set.",
    ]
    matrix_gaps = matrix.get("gaps") if isinstance(matrix.get("gaps"), list) else []
    unity_gaps = unity_native.get("gaps") if isinstance(unity_native.get("gaps"), list) else []
    audit_gaps = audit.get("gaps") if isinstance(audit.get("gaps"), list) else []
    gaps = list(dict.fromkeys([*matrix_gaps, *unity_gaps, *audit_gaps]))
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
        },
        "summary": {
            "matrix_status": matrix.get("status"),
            "unity_native_status": unity_native.get("status"),
            "audit_status": audit.get("overall_status"),
            "planned_routes_status": planned_routes.get("status"),
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
            "packet_summary": {
                "path": "docs/CESIUM_PR_PACKET_SUMMARY.md",
                "exists": (ROOT / "docs" / "CESIUM_PR_PACKET_SUMMARY.md").is_file(),
            },
        },
        "matrix": matrix,
        "audit": audit,
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
