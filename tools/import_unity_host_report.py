#!/usr/bin/env python3
"""Import a portable Cesium Unity host report archive into the local report root."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST_ROOT = ROOT / "artifacts" / "verification_reports" / "unity_hosts"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--host-root", default=str(DEFAULT_HOST_ROOT))
    return parser.parse_args(argv)


def import_archive(archive: Path, host_root: Path) -> Path:
    if not archive.is_file():
        raise FileNotFoundError(f"Archive not found: {archive}")
    host_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(host_root)
    return host_root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    archive = args.archive.expanduser().resolve()
    host_root = Path(args.host_root).expanduser().resolve()
    import_archive(archive, host_root)
    print(f"Imported Cesium Unity host report archive into: {host_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
