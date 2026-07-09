#!/usr/bin/env python3
"""Stage a local Cesium Unity host report into a reusable bundle."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "artifacts" / "reports"
DEFAULT_DEST_ROOT = ROOT / "artifacts" / "verification_reports" / "unity_hosts"
REQUIRED_FILES = ("unity_host_report.json", "unity_host_report.md")
HOST_MANIFEST = "unity_host_report_manifest.json"
HOST_MANIFEST_MD = "unity_host_report_manifest.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--dest-root", default=str(DEFAULT_DEST_ROOT))
    parser.add_argument("--host-label", default="local-host")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_payload(source_dir: Path, host_label: str, required_files: tuple[str, ...]) -> dict[str, object]:
    return {
        "host_label": host_label,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_report_dir": str(source_dir),
        "required_files": list(required_files),
        "report_digest_sha256": hashlib.sha256(
            "".join(sha256_file(source_dir / name) for name in required_files).encode("utf-8")
        ).hexdigest(),
    }


def render_manifest_markdown(manifest: dict[str, object]) -> str:
    lines = [
        "# Cesium Unity Host Report Manifest",
        "",
        f"- host_label: `{manifest['host_label']}`",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- source_report_dir: `{manifest['source_report_dir']}`",
        f"- report_digest_sha256: `{manifest['report_digest_sha256']}`",
        "",
        "## Included Files",
        "",
    ]
    for name in manifest["required_files"]:
        lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)


def stage_report_set(source_dir: Path, dest_dir: Path, required_files: tuple[str, ...], *, overwrite: bool) -> None:
    missing = [name for name in required_files if not (source_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("Source report directory is missing required Unity proof files:\n" + "\n".join(f"- {name}" for name in missing))
    if dest_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dest_dir}")
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in required_files:
        shutil.copy2(source_dir / name, dest_dir / name)
    manifest = manifest_payload(source_dir, dest_dir.name, required_files)
    (dest_dir / HOST_MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (dest_dir / HOST_MANIFEST_MD).write_text(render_manifest_markdown(manifest), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_dir = Path(args.source_dir).expanduser().resolve()
    dest_root = Path(args.dest_root).expanduser().resolve()
    dest_dir = dest_root / args.host_label
    stage_report_set(source_dir, dest_dir, REQUIRED_FILES, overwrite=args.overwrite)
    print(f"Staged Cesium Unity host report set: {dest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
