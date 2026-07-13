#!/usr/bin/env python3
"""Download and stage Godot editor and template zips into the local public roots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import shutil
import urllib.parse
import urllib.request
import zipfile
from typing import Any

from extensions.cesium.tools import engine_root_discovery
from tools import godot_versioning


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "reports" / "godot_bootstrap"

EDITOR_SPECS = {
    "windows": {
        "slug": "win64.exe.zip",
        "platform": "windows.64",
        "install_suffix": "_win64.exe",
    },
    "linux": {
        "slug": "linux.x86_64.zip",
        "platform": "linux.64",
        "install_suffix": "_linux.x86_64",
    },
    "mac": {
        "slug": "macos.universal.zip",
        "platform": "macos.universal",
        "install_suffix": "_macos.universal.app",
    },
}


@dataclass(frozen=True)
class GodotRelease:
    tag: str
    version: str
    flavor: str


def _split_release_tag(godot_version: str, flavor: str | None = None) -> GodotRelease:
    if flavor is None and "-" in godot_version:
        version, derived_flavor = godot_version.rsplit("-", 1)
        return GodotRelease(tag=godot_version, version=version, flavor=derived_flavor)
    if flavor is None:
        flavor = "stable"
    return GodotRelease(tag=f"{godot_version}-{flavor}", version=godot_version, flavor=flavor)


def _installed_version_tags(native_target: str) -> list[str]:
    if native_target == "windows":
        rows = engine_root_discovery.discover_godot_windows_versions()
    elif native_target == "linux":
        rows = engine_root_discovery.discover_godot_linux_versions()
    else:
        rows = engine_root_discovery.discover_godot_macos_versions()
    return [str(row.get("version") or "") for row in rows if isinstance(row, dict) and str(row.get("version") or "")]


def _installed_version_tags_all() -> list[str]:
    return [
        *_installed_version_tags("windows"),
        *_installed_version_tags("linux"),
        *_installed_version_tags("mac"),
    ]


def _resolve_requested_version(
    *,
    godot_version: str | None,
    godot_selector: str | None,
    installed_tags: list[str],
) -> tuple[str, str]:
    if godot_version:
        return godot_version, "exact"
    selector = godot_selector or ""
    installed = godot_versioning.select_versions(installed_tags, selector, limit=1)
    if installed:
        return installed[0], "installed"
    archive_tags = godot_versioning.fetch_archive_tags()
    downloadable = godot_versioning.select_versions(archive_tags, selector, limit=1)
    if downloadable:
        return downloadable[0], "archive"
    raise SystemExit("No Godot versions matched the requested selector.")


def build_editor_download_url(godot_version: str, native_target: str, flavor: str | None = None) -> str:
    release = _split_release_tag(godot_version, flavor)
    spec = EDITOR_SPECS[native_target]
    query = urllib.parse.urlencode(
        {
            "version": release.version,
            "flavor": release.flavor,
            "slug": spec["slug"],
            "platform": spec["platform"],
        }
    )
    return f"https://downloads.godotengine.org/?{query}"


def build_template_download_url(godot_version: str, flavor: str | None = None) -> str:
    release = _split_release_tag(godot_version, flavor)
    query = urllib.parse.urlencode(
        {
            "version": release.version,
            "flavor": release.flavor,
            "slug": "export_templates.tpz",
            "platform": "templates",
        }
    )
    return f"https://downloads.godotengine.org/?{query}"


def _default_editor_root(native_target: str) -> Path:
    if native_target in {"windows", "linux"}:
        public_root = engine_root_discovery.public_share_root()
        return public_root / "Godot" / "engines" / native_target
    return Path.home() / "Applications"


def _default_template_root(release_tag: str) -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return base / "Godot" / "export_templates" / release_tag
    if system == "darwin":
        base = Path(os.environ.get("HOME", str(Path.home())))
        return base / "Library" / "Application Support" / "Godot" / "export_templates" / release_tag
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "godot" / "export_templates" / release_tag


def _download_file(url: str, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:  # nosec: B310
        shutil.copyfileobj(response, handle)
        final_url = getattr(response, "geturl", lambda: url)()
    return {"requested_url": url, "final_url": final_url, "download_path": str(destination)}


def _safe_extract(zip_path: Path, target_dir: Path) -> list[str]:
    staging = target_dir.parent / f".{target_dir.name}.staging-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(staging)
        extracted = archive.namelist()

    entries = [path for path in sorted(staging.iterdir()) if path.exists()]
    if target_dir.exists():
        shutil.rmtree(target_dir)

    if len(entries) == 1 and entries[0].is_dir():
        entries[0].replace(target_dir)
    elif len(entries) == 1 and entries[0].is_file():
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(entries[0]), str(target_dir / entries[0].name))
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            shutil.move(str(entry), str(target_dir / entry.name))

    shutil.rmtree(staging, ignore_errors=True)
    return extracted


def _editor_install_path(release_tag: str, native_target: str, install_root: Path | None = None) -> Path:
    spec = EDITOR_SPECS[native_target]
    base_root = install_root or _default_editor_root(native_target)
    return Path(base_root) / f"Godot_v{release_tag}{spec['install_suffix']}"


def _template_install_path(release_tag: str) -> Path:
    return _default_template_root(release_tag)


def _report_paths(stem: str) -> tuple[Path, Path]:
    return (
        DEFAULT_REPORT_DIR / f"{stem}.json",
        DEFAULT_REPORT_DIR / f"{stem}.md",
    )


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Godot Bootstrap",
        "",
        f"- status: `{payload['status']}`",
        f"- mode: `{payload['mode']}`",
        f"- godot_version: `{payload['godot_version']}`",
        f"- native_target: `{payload['native_target']}`",
        f"- download_url: `{payload.get('download_url')}`",
        f"- target_path: `{payload.get('target_path')}`",
        f"- archive_path: `{payload.get('archive_path')}`",
    ]
    if payload.get("template_download_url") is not None:
        lines.append(f"- template_download_url: `{payload.get('template_download_url')}`")
    if payload.get("template_target_path") is not None:
        lines.append(f"- template_target_path: `{payload.get('template_target_path')}`")
    if payload.get("detail"):
        lines.extend(["", "## Detail", "", str(payload["detail"])])
    if payload.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in payload["next_steps"]:
            lines.append(f"- {step}")
    if payload.get("installed_files"):
        lines.extend(["", "## Installed Files", ""])
        for item in payload["installed_files"]:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _archive_page_url(release_tag: str) -> str:
    return f"https://godotengine.org/download/archive/{release_tag}/"


def _build_editor_payload(
    *,
    godot_version: str,
    native_target: str,
    install_root: Path,
    download_url: str,
    archive_path: Path,
    extracted_files: list[str],
    status: str,
    detail: str,
    version_source: str,
) -> dict[str, Any]:
    release = _split_release_tag(godot_version)
    target_path = _editor_install_path(release.tag, native_target, install_root)
    return {
        "schema": "cesium.godot_bootstrap.v1",
        "mode": "editor",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "detail": detail,
        "godot_version": release.tag,
        "requested_version_source": version_source,
        "native_target": native_target,
        "archive_page_url": _archive_page_url(release.tag),
        "download_url": download_url,
        "archive_path": str(archive_path),
        "install_root": str(install_root),
        "target_path": str(target_path),
        "installed_files": extracted_files,
    }


def bootstrap_editor(
    *,
    godot_version: str | None = None,
    godot_selector: str | None = None,
    native_target: str,
    install_root: Path | None = None,
    download_url: str | None = None,
    archive_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_version, version_source = _resolve_requested_version(
        godot_version=godot_version,
        godot_selector=godot_selector,
        installed_tags=_installed_version_tags(native_target),
    )
    release = _split_release_tag(resolved_version)
    install_root = (install_root or _default_editor_root(native_target)).expanduser().resolve()
    target_path = _editor_install_path(release.tag, native_target, install_root)
    download_url = download_url or build_editor_download_url(release.version, native_target, release.flavor)
    archive_path = archive_path or (DEFAULT_REPORT_DIR / "_cache" / f"{target_path.name}.zip")
    if dry_run:
        payload = _build_editor_payload(
            godot_version=release.tag,
            native_target=native_target,
            install_root=install_root,
            download_url=download_url,
            archive_path=archive_path,
            extracted_files=[],
            status="dry-run",
            detail="not executed; use without --dry-run to download and stage the Godot editor zip",
            version_source=version_source,
        )
        payload["next_steps"] = [
            f"Archive page: {_archive_page_url(release.tag)}",
            f"Download URL: {download_url}",
            f"Stage into: {target_path}",
        ]
        return payload

    if target_path.exists():
        detail = f"Godot editor already exists at {target_path}."
        return _build_editor_payload(
            godot_version=release.tag,
            native_target=native_target,
            install_root=install_root,
            download_url=download_url,
            archive_path=archive_path,
            extracted_files=[],
            status="present",
            detail=detail,
            version_source=version_source,
        )

    if native_target == "mac":
        install_root.mkdir(parents=True, exist_ok=True)
    else:
        install_root.mkdir(parents=True, exist_ok=True)

    download_info = _download_file(download_url, archive_path)
    extracted_files = _safe_extract(archive_path, target_path)
    status = "ok" if target_path.exists() else "needs-attention"
    detail = "Godot editor downloaded and staged." if status == "ok" else "Godot editor archive was downloaded, but the staged install path is incomplete."
    payload = _build_editor_payload(
        godot_version=release.tag,
        native_target=native_target,
        install_root=install_root,
        download_url=download_info["requested_url"],
        archive_path=Path(download_info["download_path"]),
        extracted_files=extracted_files,
        status=status,
        detail=detail,
        version_source=version_source,
    )
    payload["final_url"] = download_info["final_url"]
    payload["next_steps"] = [
        f"Verify the editor appears at {target_path}",
        f"Use the matching archive page for follow-up reference: {_archive_page_url(release.tag)}",
    ]
    return payload


def bootstrap_templates(
    *,
    godot_version: str | None = None,
    godot_selector: str | None = None,
    template_root: Path | None = None,
    download_url: str | None = None,
    archive_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_version, version_source = _resolve_requested_version(
        godot_version=godot_version,
        godot_selector=godot_selector,
        installed_tags=_installed_version_tags_all(),
    )
    release = _split_release_tag(resolved_version)
    template_root = (template_root or _default_template_root(release.tag)).expanduser().resolve()
    download_url = download_url or build_template_download_url(release.version, release.flavor)
    archive_path = archive_path or (DEFAULT_REPORT_DIR / "_cache" / f"{release.tag}_export_templates.tpz")
    if dry_run:
        return {
            "schema": "cesium.godot_bootstrap.v1",
            "mode": "templates",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "dry-run",
            "detail": "not executed; use without --dry-run to download and stage the Godot export templates",
            "godot_version": release.tag,
            "requested_version_source": version_source,
            "archive_page_url": _archive_page_url(release.tag),
            "template_download_url": download_url,
            "archive_path": str(archive_path),
            "template_target_path": str(template_root),
            "installed_files": [],
            "next_steps": [
                f"Archive page: {_archive_page_url(release.tag)}",
                f"Download URL: {download_url}",
                f"Stage templates into: {template_root}",
            ],
        }

    template_root.mkdir(parents=True, exist_ok=True)
    if any(template_root.iterdir()):
        detail = f"Godot templates already exist at {template_root}."
        return {
            "schema": "cesium.godot_bootstrap.v1",
            "mode": "templates",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "present",
            "detail": detail,
            "godot_version": release.tag,
            "requested_version_source": version_source,
            "archive_page_url": _archive_page_url(release.tag),
            "template_download_url": download_url,
            "archive_path": str(archive_path),
            "template_target_path": str(template_root),
            "installed_files": [],
            "next_steps": [],
        }

    download_info = _download_file(download_url, archive_path)
    extracted_files = _safe_extract(archive_path, template_root)
    status = "ok" if template_root.exists() else "needs-attention"
    detail = "Godot export templates downloaded and staged." if status == "ok" else "Godot export template archive was downloaded, but the staged install path is incomplete."
    return {
        "schema": "cesium.godot_bootstrap.v1",
        "mode": "templates",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "detail": detail,
        "godot_version": release.tag,
        "requested_version_source": version_source,
        "archive_page_url": _archive_page_url(release.tag),
        "template_download_url": download_info["requested_url"],
        "final_url": download_info["final_url"],
        "archive_path": str(download_info["download_path"]),
        "template_target_path": str(template_root),
        "installed_files": extracted_files,
        "next_steps": [
            f"Confirm the templates are visible under {template_root}",
            "Use the repo's Godot example build helper to validate the exported install.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    editor = subparsers.add_parser("editor", help="Download and stage a Godot editor zip")
    editor.add_argument("--godot-version", help="Exact Godot version tag, for example 4.7-stable or 4.8-dev1")
    editor.add_argument(
        "--godot-selector",
        help="Acceptable Godot version selector, for example 4.7-stable..4.8-dev1 or 4.7-stable,4.8-dev1",
    )
    editor.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    editor.add_argument("--install-root", type=Path)
    editor.add_argument("--download-url")
    editor.add_argument("--archive-path", type=Path)
    editor.add_argument("--dry-run", action="store_true")
    editor.add_argument("--json-out", type=Path)
    editor.add_argument("--md-out", type=Path)

    templates = subparsers.add_parser("templates", help="Download and stage a Godot export template pack")
    templates.add_argument("--godot-version", help="Exact Godot version tag, for example 4.7-stable or 4.8-dev1")
    templates.add_argument(
        "--godot-selector",
        help="Acceptable Godot version selector, for example 4.7-stable..4.8-dev1 or 4.7-stable,4.8-dev1",
    )
    templates.add_argument("--template-root", type=Path)
    templates.add_argument("--download-url")
    templates.add_argument("--archive-path", type=Path)
    templates.add_argument("--dry-run", action="store_true")
    templates.add_argument("--json-out", type=Path)
    templates.add_argument("--md-out", type=Path)

    all_cmd = subparsers.add_parser("all", help="Download and stage both the Godot editor zip and export templates")
    all_cmd.add_argument("--godot-version", help="Exact Godot version tag, for example 4.7-stable or 4.8-dev1")
    all_cmd.add_argument(
        "--godot-selector",
        help="Acceptable Godot version selector, for example 4.7-stable..4.8-dev1 or 4.7-stable,4.8-dev1",
    )
    all_cmd.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    all_cmd.add_argument("--install-root", type=Path)
    all_cmd.add_argument("--template-root", type=Path)
    all_cmd.add_argument("--download-url")
    all_cmd.add_argument("--template-download-url")
    all_cmd.add_argument("--editor-archive-path", type=Path)
    all_cmd.add_argument("--template-archive-path", type=Path)
    all_cmd.add_argument("--dry-run", action="store_true")
    all_cmd.add_argument("--json-out", type=Path)
    all_cmd.add_argument("--md-out", type=Path)
    return parser.parse_args(argv)


def _write_command_report(payload: dict[str, Any], json_out: Path | None, md_out: Path | None) -> None:
    if json_out is None and md_out is None:
        return
    json_path = json_out or (DEFAULT_REPORT_DIR / "godot_bootstrap.json")
    md_path = md_out or (DEFAULT_REPORT_DIR / "godot_bootstrap.md")
    _write_report(payload, json_path, md_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.godot_version and not args.godot_selector:
        raise SystemExit("Provide either --godot-version or --godot-selector.")
    if args.command == "editor":
        payload = bootstrap_editor(
            godot_version=args.godot_version,
            godot_selector=args.godot_selector,
            native_target=args.native_target,
            install_root=args.install_root,
            download_url=args.download_url,
            archive_path=args.archive_path,
            dry_run=args.dry_run,
        )
        _write_command_report(payload, args.json_out, args.md_out)
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] in {"ok", "dry-run", "present"} else 2

    if args.command == "templates":
        payload = bootstrap_templates(
            godot_version=args.godot_version,
            godot_selector=args.godot_selector,
            template_root=args.template_root,
            download_url=args.download_url,
            archive_path=args.archive_path,
            dry_run=args.dry_run,
        )
        _write_command_report(payload, args.json_out, args.md_out)
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] in {"ok", "dry-run", "present"} else 2

    editor_payload = bootstrap_editor(
        godot_version=args.godot_version,
        godot_selector=args.godot_selector,
        native_target=args.native_target,
        install_root=args.install_root,
        download_url=args.download_url,
        archive_path=args.editor_archive_path,
        dry_run=args.dry_run,
    )
    templates_payload = bootstrap_templates(
        godot_version=args.godot_version,
        godot_selector=args.godot_selector,
        template_root=args.template_root,
        download_url=args.template_download_url,
        archive_path=args.template_archive_path,
        dry_run=args.dry_run,
    )
    payload = {
        "schema": "cesium.godot_bootstrap.v1",
        "mode": "all",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok"
        if editor_payload["status"] in {"ok", "dry-run", "present"} and templates_payload["status"] in {"ok", "dry-run", "present"}
        else "needs-attention",
        "godot_version": editor_payload.get("godot_version") or templates_payload.get("godot_version") or args.godot_version,
        "native_target": args.native_target,
        "editor": editor_payload,
        "templates": templates_payload,
        "detail": "Godot editor and export templates bootstrapped." if not args.dry_run else "not executed; use without --dry-run to download and stage both packages",
        "next_steps": [
            "Confirm the editor and templates both appear at their expected roots.",
            "Run the Godot example build helper after bootstrapping to verify the lane end to end.",
        ],
    }
    _write_command_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"ok", "dry-run", "present"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
