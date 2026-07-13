#!/usr/bin/env python3
"""Run the visual-proof contract, root, and comparison checks in one pass."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from tools import (
    compare_cesium_visual_proof,
    validate_visual_proof_contracts,
    validate_visual_proof_roots,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_visual_proof_audit"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_audit.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_audit.md"


def _normalize_statuses(statuses: list[str]) -> str:
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "partial" for status in statuses):
        return "partial"
    if any(status == "commandable" for status in statuses):
        return "commandable"
    if all(status == "pass" for status in statuses):
        return "pass"
    return "partial"


def _root_coverage_status(roots: dict[str, Any]) -> str | None:
    summary = roots.get("summary")
    if not isinstance(summary, dict):
        return None
    present_engines = summary.get("present_engines")
    missing_engines = summary.get("missing_engines")
    if present_engines is None or missing_engines is None:
        return None
    if str(roots.get("status")) == "pass" and not missing_engines:
        return "pass"
    return "partial"


def _load_launch_reports(paths: list[Path] | None) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in paths or []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reports.append({"path": str(path), "status": "fail", "error": "Could not read launch report."})
            continue
        if not isinstance(payload, dict):
            reports.append({"path": str(path), "status": "fail", "error": "Launch report is not an object."})
            continue
        reports.append({
            "path": str(path),
            "status": str(payload.get("status") or "fail"),
            "schema": payload.get("schema"),
            "engine_results": [
                {
                    "engine": item.get("engine"),
                    "status": item.get("status"),
                    "reason": item.get("reason"),
                }
                for item in payload.get("engine_results", [])
                if isinstance(item, dict)
            ],
        })
    return reports


def build_payload(
    scan_roots: list[Path] | None = None,
    launch_reports: list[Path] | None = None,
) -> dict[str, Any]:
    contracts = validate_visual_proof_contracts.build_payload()
    roots = validate_visual_proof_roots.build_payload(scan_roots)
    comparisons = compare_cesium_visual_proof.build_payload(scan_roots=scan_roots, strict_missing=True)
    launches = _load_launch_reports(launch_reports)
    statuses = [
        str(contracts.get("status")),
        str(roots.get("status")),
        str(comparisons.get("status")),
        *(str(item.get("status")) for item in launches),
    ]
    status = _normalize_statuses(statuses)
    return {
        "schema": "cesium.visual_proof_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "contracts": contracts,
        "roots": roots,
        "comparisons": comparisons,
        "summary": {
            "contract_status": contracts.get("status"),
            "root_status": roots.get("status"),
            "comparison_status": comparisons.get("status"),
            "launch_status": "pass" if launches and all(item.get("status") == "pass" for item in launches) else ("not-provided" if not launches else "fail"),
            "launch_report_count": len(launches),
            "root_count": roots.get("summary", {}).get("root_count") if isinstance(roots.get("summary"), dict) else None,
            "root_expected_engines": roots.get("summary", {}).get("expected_engines") if isinstance(roots.get("summary"), dict) else None,
            "root_present_engines": roots.get("summary", {}).get("present_engines") if isinstance(roots.get("summary"), dict) else None,
            "root_missing_engines": roots.get("summary", {}).get("missing_engines") if isinstance(roots.get("summary"), dict) else None,
            "root_engine_coverage_status": _root_coverage_status(roots),
            "pass_count": sum(
                1
                for item in (contracts, roots, comparisons)
                if str(item.get("status")) == "pass"
            ),
            "partial_count": sum(
                1
                for item in (contracts, roots, comparisons)
                if str(item.get("status")) == "partial"
            ),
            "fail_count": sum(
                1
                for item in (contracts, roots, comparisons)
                if str(item.get("status")) == "fail"
            ) + sum(1 for item in launches if str(item.get("status")) == "fail"),
        },
        "launches": launches,
        "related_packets": {
            "visual_proof_contracts": {
                "status": contracts.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_contracts/cesium_visual_proof_contracts.json",
            },
            "visual_proof_roots": {
                "status": roots.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_roots/cesium_visual_proof_roots.json",
            },
            "visual_proof_compare": {
                "status": comparisons.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_compare/cesium_visual_proof_compare.json",
            },
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Visual Proof Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Related Packets",
        "",
    ]
    for name, report in payload.get("related_packets", {}).items():
        if isinstance(report, dict):
            lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Summary", ""])
    summary = payload.get("summary", {})
    lines.append(f"- contract_status: `{summary.get('contract_status')}`")
    lines.append(f"- root_status: `{summary.get('root_status')}`")
    lines.append(f"- comparison_status: `{summary.get('comparison_status')}`")
    lines.append(f"- root_count: `{summary.get('root_count')}`")
    lines.append(f"- root_expected_engines: `{summary.get('root_expected_engines')}`")
    lines.append(f"- root_present_engines: `{summary.get('root_present_engines')}`")
    lines.append(f"- root_missing_engines: `{summary.get('root_missing_engines')}`")
    lines.append(f"- root_engine_coverage_status: `{summary.get('root_engine_coverage_status')}`")
    lines.append(f"- pass_count: `{summary.get('pass_count')}`")
    lines.append(f"- partial_count: `{summary.get('partial_count')}`")
    lines.append(f"- fail_count: `{summary.get('fail_count')}`")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", action="append", type=Path, default=None)
    parser.add_argument("--launch-report", action="append", type=Path, default=None, help="Engine runner report to include as a launch gate.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args(argv)

    payload = build_payload(args.scan_root, args.launch_report)
    write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
