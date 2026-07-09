#!/usr/bin/env python3
"""Export a portable Cesium Unity host handoff archive."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "dist" / "unity_host_handoff"
TOOL_FILES = (
    "tools/unity_env.py",
    "tools/capture_unity_host_report.py",
    "tools/stage_unity_host_report.py",
)
DOC_FILES = (
    "docs/CESIUM_UNITY_6000_5_FINDINGS.md",
    "docs/CESIUM_UNITY_VERSION_MATRIX.md",
    "docs/CESIUM_FORK_LEDGER.md",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--host-report-root", default=str(ROOT / "artifacts" / "verification_reports" / "unity_hosts"))
    return parser.parse_args(argv)


def handoff_paths(host_report_root: Path) -> list[Path]:
    paths = [ROOT / relative for relative in TOOL_FILES + DOC_FILES]
    if host_report_root.is_dir():
        for path in sorted(host_report_root.rglob("*")):
            if path.is_file():
                paths.append(path)
    return paths


def validate_handoff_paths(paths: list[Path]) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Unity host handoff kit is missing required files:\n" + "\n".join(f"- {path}" for path in missing))


def package_version() -> str:
    return "cesium-unity-host-handoff"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_archive(archive_path: Path, host_report_root: Path) -> Path:
    paths = handoff_paths(host_report_root)
    validate_handoff_paths(paths)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_root = Path(package_version())
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in paths:
            try:
                relative = source.relative_to(ROOT)
            except ValueError:
                relative = source.relative_to(host_report_root.parent)
            archive.write(source, arcname=str(bundle_root / relative))
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_path.write_text(f"{sha256_file(archive_path)}  {archive_path.name}\n", encoding="utf-8")
    return archive_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir).expanduser().resolve()
    host_report_root = Path(args.host_report_root).expanduser().resolve()
    archive_path = out_dir / f"{package_version()}.zip"
    export_archive(archive_path, host_report_root)
    print(f"Exported Cesium Unity host handoff archive: {archive_path}")
    print(f"Archive checksum: {archive_path.with_suffix(archive_path.suffix + '.sha256')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
