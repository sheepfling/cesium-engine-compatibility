#!/usr/bin/env python3
"""Validate the checked-in visual-proof contracts for Unreal, Unity, and Godot."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_visual_proof_contracts"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_contracts.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "cesium_visual_proof_contracts.md"

CONTRACTS: tuple[dict[str, Any], ...] = (
    {
        "engine": "unreal",
        "contract_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "unreal"
        / "CesiumVanillaExample"
        / "VisualProofContract.md",
        "readme_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "unreal"
        / "CesiumVanillaExample"
        / "README.md",
        "harness_path": ROOT
        / "external"
        / "cesium"
        / "cesium-unreal"
        / "Source"
        / "CesiumRuntime"
        / "Private"
        / "Tests"
        / "CesiumVisualProof.spec.cpp",
        "support_path": ROOT
        / "external"
        / "cesium"
        / "cesium-unreal"
        / "Source"
        / "CesiumRuntime"
        / "Private"
        / "Tests"
        / "CesiumLoadTestCore.cpp",
        "required_phrases": (
            "Saved/Screenshots/WindowsEditor",
            "visual_proof_manifest.json",
            "proxy_overview.png",
            "Cesium.VisualProof.",
        ),
        "required_harness_phrases": (
            "IMPLEMENT_SIMPLE_AUTOMATION_TEST",
            "CESIUM_VISUAL_PROOF_PLATFORM",
            "Cesium.VisualProof.",
            "ProxyEarth",
            "CesiumEarth",
        ),
        "required_support_phrases": (
            "FScreenshotRequest::RequestScreenshot",
            "LoadTestScreenshotCommand::Update",
            "Saved/Screenshots/WindowsEditor",
        ),
        "required_readme_phrases": (
            "version-specific Unreal variant",
            "lane report",
            "base scaffold",
        ),
    },
    {
        "engine": "unity",
        "contract_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "unity"
        / "CesiumVanillaExample"
        / "VisualProofContract.md",
        "readme_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "unity"
        / "CesiumVanillaExample"
        / "README.md",
        "required_phrases": (
            "visual_proof_manifest.json",
            "proxy_overview.png",
            "Assets/CesiumVisualProofCapture.cs",
        ),
        "required_readme_phrases": (
            "version-aware proof harness",
            "separate project workpack",
            "baseline proof lane remains",
        ),
    },
    {
        "engine": "godot",
        "contract_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "godot"
        / "CesiumVanillaExample"
        / "VisualProofContract.md",
        "readme_path": ROOT
        / "extensions"
        / "cesium"
        / "examples"
        / "godot"
        / "CesiumVanillaExample"
        / "README.md",
        "required_phrases": (
            "visual_proof_manifest.json",
            "proxy_overview.png",
            "scripts/VisualProofRunner.gd",
        ),
        "required_readme_phrases": (
            "version-aware proof harness",
            "separate workpack or report tree",
            "current proof lane",
        ),
    },
)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_payload() -> dict[str, Any]:
    contracts: list[dict[str, Any]] = []
    findings: list[str] = []

    for spec in CONTRACTS:
        contract_path: Path = spec["contract_path"]
        readme_path: Path = spec["readme_path"]
        harness_path: Path | None = spec.get("harness_path")
        support_path: Path | None = spec.get("support_path")
        contract_exists = contract_path.is_file()
        readme_exists = readme_path.is_file()
        harness_exists = harness_path.is_file() if isinstance(harness_path, Path) else True
        support_exists = support_path.is_file() if isinstance(support_path, Path) else True
        contract_content = contract_path.read_text(encoding="utf-8") if contract_exists else ""
        readme_content = readme_path.read_text(encoding="utf-8") if readme_exists else ""
        harness_content = harness_path.read_text(encoding="utf-8") if harness_exists and isinstance(harness_path, Path) else ""
        support_content = support_path.read_text(encoding="utf-8") if support_exists and isinstance(support_path, Path) else ""

        missing_phrases = [phrase for phrase in spec["required_phrases"] if phrase not in contract_content]
        missing_harness_phrases = [
            phrase for phrase in spec.get("required_harness_phrases", ()) if phrase not in harness_content
        ]
        missing_support_phrases = [
            phrase for phrase in spec.get("required_support_phrases", ()) if phrase not in support_content
        ]
        readme_link_missing = contract_path.name not in readme_content
        missing_readme_phrases = [
            phrase for phrase in spec.get("required_readme_phrases", ()) if phrase not in readme_content
        ]

        status = "pass"
        if (
            not contract_exists
            or not readme_exists
            or not harness_exists
            or not support_exists
            or missing_phrases
            or missing_harness_phrases
            or missing_support_phrases
            or readme_link_missing
            or missing_readme_phrases
        ):
            status = "fail"
        if not contract_exists:
            findings.append(f"{spec['engine']}: missing contract file")
        if not readme_exists:
            findings.append(f"{spec['engine']}: missing README file")
        if not harness_exists:
            findings.append(f"{spec['engine']}: missing harness file")
        if not support_exists:
            findings.append(f"{spec['engine']}: missing support file")
        for phrase in missing_phrases:
            findings.append(f"{spec['engine']}: contract missing phrase {phrase}")
        for phrase in missing_harness_phrases:
            findings.append(f"{spec['engine']}: harness missing phrase {phrase}")
        for phrase in missing_support_phrases:
            findings.append(f"{spec['engine']}: support missing phrase {phrase}")
        if readme_link_missing:
            findings.append(f"{spec['engine']}: README does not reference {contract_path.name}")
        for phrase in missing_readme_phrases:
            findings.append(f"{spec['engine']}: README missing phrase {phrase}")

        contracts.append(
            {
                "engine": spec["engine"],
                "contract_path": _rel(contract_path),
                "readme_path": _rel(readme_path),
                "harness_path": _rel(harness_path) if isinstance(harness_path, Path) else None,
                "support_path": _rel(support_path) if isinstance(support_path, Path) else None,
                "contract_exists": contract_exists,
                "readme_exists": readme_exists,
                "harness_exists": harness_exists,
                "support_exists": support_exists,
                "missing_phrases": missing_phrases,
                "missing_harness_phrases": missing_harness_phrases,
                "missing_support_phrases": missing_support_phrases,
                "missing_readme_phrases": missing_readme_phrases,
                "readme_link_missing": readme_link_missing,
                "status": status,
            }
        )

    overall_status = "pass" if all(item["status"] == "pass" for item in contracts) else "fail"
    return {
        "schema": "cesium.visual_proof_contracts.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "contracts": contracts,
        "findings": findings,
        "summary": {
            "contract_count": len(contracts),
            "pass_count": sum(1 for item in contracts if item["status"] == "pass"),
            "fail_count": sum(1 for item in contracts if item["status"] == "fail"),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Visual Proof Contracts",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Contracts",
        "",
    ]
    for contract in payload.get("contracts", []):
        lines.append(f"### {contract['engine']}")
        lines.append(f"- status: `{contract['status']}`")
        lines.append(f"- contract_path: `{contract['contract_path']}`")
        lines.append(f"- readme_path: `{contract['readme_path']}`")
        if contract.get("harness_path") is not None:
            lines.append(f"- harness_path: `{contract['harness_path']}`")
        if contract.get("support_path") is not None:
            lines.append(f"- support_path: `{contract['support_path']}`")
        if contract.get("missing_phrases"):
            lines.append("- missing_phrases:")
            for phrase in contract["missing_phrases"]:
                lines.append(f"  - `{phrase}`")
        if contract.get("missing_harness_phrases"):
            lines.append("- missing_harness_phrases:")
            for phrase in contract["missing_harness_phrases"]:
                lines.append(f"  - `{phrase}`")
        if contract.get("missing_support_phrases"):
            lines.append("- missing_support_phrases:")
            for phrase in contract["missing_support_phrases"]:
                lines.append(f"  - `{phrase}`")
        if contract.get("missing_readme_phrases"):
            lines.append("- missing_readme_phrases:")
            for phrase in contract["missing_readme_phrases"]:
                lines.append(f"  - `{phrase}`")
        lines.append(f"- readme_link_missing: `{contract['readme_link_missing']}`")
    if payload.get("findings"):
        lines.extend(["", "## Findings", ""])
        for finding in payload["findings"]:
            lines.append(f"- {finding}")
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
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
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
