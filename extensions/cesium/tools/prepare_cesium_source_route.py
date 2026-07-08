#!/usr/bin/env python3
"""Prepare the public Cesium source-route checkouts for reproducible engine compatibility work."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import platform
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CHECKOUT_ROOT = ROOT / "external" / "cesium"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "cesium_source_route_prepare"


@dataclass(frozen=True)
class RepoSpec:
    key: str
    label: str
    path: Path
    remote_url: str
    target_branch: str
    fallback_branches: tuple[str, ...] = ()
    submodule_url_overrides: tuple[tuple[str, str], ...] = ()
    update_submodules: bool = False
    official: bool = True


def default_repo_specs() -> list[RepoSpec]:
    return [
        RepoSpec(
            key="unreal_plugin",
            label="Cesium Unreal plugin",
            path=CHECKOUT_ROOT / "cesium-unreal",
            remote_url="https://github.com/CesiumGS/cesium-unreal.git",
            target_branch="main",
            submodule_url_overrides=(("extern/cesium-native", "https://github.com/CesiumGS/cesium-native.git"),),
            update_submodules=True,
            official=True,
        ),
        RepoSpec(
            key="unity_plugin",
            label="Cesium Unity plugin",
            path=CHECKOUT_ROOT / "cesium-unity",
            remote_url="https://github.com/CesiumGS/cesium-unity.git",
            target_branch="main",
            submodule_url_overrides=(("native~/extern/cesium-native", "https://github.com/CesiumGS/cesium-native.git"),),
            update_submodules=True,
            official=True,
        ),
        RepoSpec(
            key="unreal_samples",
            label="Cesium Unreal samples",
            path=CHECKOUT_ROOT / "cesium-unreal-samples",
            remote_url="https://github.com/CesiumGS/cesium-unreal-samples.git",
            target_branch="main",
            update_submodules=False,
            official=True,
        ),
        RepoSpec(
            key="godot_plugin",
            label="3D Tiles for Godot",
            path=CHECKOUT_ROOT / "3D-Tiles-For-Godot",
            remote_url="https://github.com/Battle-Road-Labs/3D-Tiles-For-Godot.git",
            target_branch="main",
            fallback_branches=("master",),
            update_submodules=True,
            official=False,
        ),
    ]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        dest="repos",
        action="append",
        choices=[spec.key for spec in default_repo_specs()],
        help="Specific Cesium checkout key to prepare. Default is all known public-route repos.",
    )
    parser.add_argument("--no-fetch", action="store_true", help="Do not fetch remotes before checking out the target branch.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow branch switching even when the checkout has local modifications.")
    parser.add_argument("--skip-submodules", action="store_true", help="Do not run recursive submodule updates for repos that use them.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUT_DIR / "cesium_source_route_prepare.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_OUT_DIR / "cesium_source_route_prepare.md")
    return parser.parse_args(argv)


def _git(path: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "http.sslVerify=false", "-c", f"safe.directory={path}", "-C", str(path), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _git_output(path: Path, args: list[str]) -> str | None:
    try:
        completed = _git(path, args, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def _is_dirty(path: Path) -> bool | None:
    output = _git_output(path, ["status", "--short"])
    if output is None:
        return None
    return bool(output.strip())


def _run_logged(path: Path, args: list[str], commands: list[dict[str, Any]]) -> subprocess.CompletedProcess[str]:
    completed = _git(path, args, check=False)
    commands.append(
            {
                "cmd": ["git", "-c", "http.sslVerify=false", "-c", f"safe.directory={path}", "-C", str(path), *args],
                "returncode": completed.returncode,
                "output": completed.stdout.strip(),
            }
        )
    return completed


def _ensure_directory_link(link: Path, target: Path, commands: list[dict[str, Any]]) -> bool:
    if link.exists() or link.is_symlink():
        return True
    link.parent.mkdir(parents=True, exist_ok=True)
    if platform.system().lower() == "windows":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        commands.append(
            {
                "cmd": ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                "returncode": completed.returncode,
                "output": completed.stdout.strip(),
            }
        )
        return completed.returncode == 0
    try:
        link.symlink_to(target, target_is_directory=True)
        commands.append(
            {
                "cmd": ["python", "-c", f"link={link!s}; target={target!s}"],
                "returncode": 0,
                "output": "created directory symlink",
            }
        )
        return True
    except OSError as exc:
        commands.append(
            {
                "cmd": ["python", "-c", f"link={link!s}; target={target!s}"],
                "returncode": 1,
                "output": str(exc),
            }
        )
        return False


def _configure_submodule_overrides(spec: RepoSpec, commands: list[dict[str, Any]]) -> bool:
    for submodule_path, submodule_url in spec.submodule_url_overrides:
        completed = _run_logged(
            spec.path,
            ["config", "--local", f"submodule.{submodule_path}.url", submodule_url],
            commands,
        )
        if completed.returncode != 0:
            return False
    return True


def inspect_repo(spec: RepoSpec) -> dict[str, Any]:
    exists = spec.path.is_dir()
    is_git = exists and _is_git_checkout(spec.path)
    state = {
        "key": spec.key,
        "label": spec.label,
        "path": str(spec.path),
        "exists": exists,
        "is_git_checkout": is_git,
        "target_branch": spec.target_branch,
        "fallback_branches": list(spec.fallback_branches),
        "resolved_target_branch": None,
        "official": spec.official,
        "current_branch": None,
        "head_commit": None,
        "target_commit": None,
        "remote_url": None,
        "dirty": None,
        "has_gitmodules": False,
    }
    if not is_git:
        return state
    state["current_branch"] = _git_output(spec.path, ["branch", "--show-current"])
    state["head_commit"] = _git_output(spec.path, ["rev-parse", "HEAD"])
    resolved_branch = resolve_remote_branch(spec.path, spec)
    state["resolved_target_branch"] = resolved_branch
    if resolved_branch is not None:
        state["target_commit"] = _git_output(spec.path, ["rev-parse", f"origin/{resolved_branch}"])
    state["remote_url"] = _git_output(spec.path, ["remote", "get-url", "origin"])
    state["dirty"] = _is_dirty(spec.path)
    state["has_gitmodules"] = (spec.path / ".gitmodules").is_file()
    return state


def resolve_remote_branch(path: Path, spec: RepoSpec) -> str | None:
    for branch in (spec.target_branch, *spec.fallback_branches):
        target_commit = _git_output(path, ["rev-parse", f"origin/{branch}"])
        if target_commit:
            return branch
    return None


def prepare_repo(
    spec: RepoSpec,
    *,
    fetch: bool,
    allow_dirty: bool,
    update_submodules: bool,
) -> dict[str, Any]:
    before = inspect_repo(spec)
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    status = "prepared"
    detail = f"{spec.label} is on the expected branch `{spec.target_branch}`."

    if not before["exists"]:
        clone_cmd = ["git", "-c", "http.sslVerify=false", "clone"]
        clone_cmd.extend(["--branch", spec.target_branch, "--single-branch", spec.remote_url, str(spec.path)])
        completed = subprocess.run(
            clone_cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        commands.append(
            {
                "cmd": clone_cmd,
                "returncode": completed.returncode,
                "output": completed.stdout.strip(),
            }
        )
        if completed.returncode != 0:
            return {
                "key": spec.key,
                "label": spec.label,
                "status": "failed",
                "detail": f"{spec.label} checkout could not be cloned from its fork remote.",
                "blockers": ["git clone failed"],
                "before": before,
                "after": inspect_repo(spec),
                "commands": commands,
            }
        before = inspect_repo(spec)

    if not before["is_git_checkout"]:
        return {
            "key": spec.key,
            "label": spec.label,
            "status": "missing",
            "detail": f"{spec.label} exists but is not a Git checkout.",
            "blockers": ["checkout is not a git repository"],
            "before": before,
            "after": before,
            "commands": commands,
        }

    if fetch:
        completed = _run_logged(spec.path, ["fetch", "--all", "--prune"], commands)
        if completed.returncode != 0:
            blockers.append("git fetch failed")
            status = "failed"
            detail = f"{spec.label} fetch failed."
            after = inspect_repo(spec)
            return {
                "key": spec.key,
                "label": spec.label,
                "status": status,
                "detail": detail,
                "blockers": blockers,
                "before": before,
                "after": after,
                "commands": commands,
            }

    mid = inspect_repo(spec)
    if mid["remote_url"] != spec.remote_url:
        completed = _run_logged(spec.path, ["remote", "set-url", "origin", spec.remote_url], commands)
        if completed.returncode != 0:
            blockers.append("git remote set-url failed")
            status = "failed"
            detail = f"{spec.label} could not repoint origin to the fork remote."
            after = inspect_repo(spec)
            return {
                "key": spec.key,
                "label": spec.label,
                "status": status,
                "detail": detail,
                "blockers": blockers,
                "before": before,
                "after": after,
                "commands": commands,
            }
        mid = inspect_repo(spec)
    if mid["dirty"] and not allow_dirty:
        blockers.append("checkout has local modifications")
        status = "blocked-dirty"
        detail = f"{spec.label} has local modifications; refusing to switch branches automatically."
        return {
            "key": spec.key,
            "label": spec.label,
            "status": status,
            "detail": detail,
            "blockers": blockers,
            "before": before,
            "after": mid,
            "commands": commands,
        }

    resolved_target_branch = mid.get("resolved_target_branch")
    if not isinstance(mid["target_commit"], str) or not mid["target_commit"] or not isinstance(resolved_target_branch, str):
        branch_labels = ", ".join(f"`origin/{branch}`" for branch in (spec.target_branch, *spec.fallback_branches))
        blockers.append(f"none of {branch_labels} found")
        status = "missing-branch"
        detail = f"{spec.label} remote branch policy is unavailable."
        return {
            "key": spec.key,
            "label": spec.label,
            "status": status,
            "detail": detail,
            "blockers": blockers,
            "before": before,
            "after": mid,
            "commands": commands,
        }

    current_branch = mid["current_branch"]
    head_commit = mid["head_commit"]
    target_commit = mid["target_commit"]
    if current_branch != resolved_target_branch or head_commit != target_commit:
        completed = _run_logged(spec.path, ["checkout", "-B", resolved_target_branch, f"origin/{resolved_target_branch}"], commands)
        if completed.returncode != 0:
            blockers.append("git checkout failed")
            status = "failed"
            detail = f"{spec.label} could not switch to `origin/{resolved_target_branch}`."
            after = inspect_repo(spec)
            return {
                "key": spec.key,
                "label": spec.label,
                "status": status,
                "detail": detail,
                "blockers": blockers,
                "before": before,
                "after": after,
                "commands": commands,
            }
        detail = f"{spec.label} was switched to `{resolved_target_branch}`."

    if update_submodules and (spec.update_submodules or mid["has_gitmodules"]):
        if spec.submodule_url_overrides and not _configure_submodule_overrides(spec, commands):
            blockers.append("submodule url override failed")
            status = "failed"
            detail = f"{spec.label} could not configure its submodule URLs."
            after = inspect_repo(spec)
            return {
                "key": spec.key,
                "label": spec.label,
                "status": status,
                "detail": detail,
                "blockers": blockers,
                "before": before,
                "after": after,
                "commands": commands,
            }
        completed = _run_logged(spec.path, ["submodule", "update", "--init", "--recursive"], commands)
        if completed.returncode != 0:
            blockers.append("git submodule update failed")
            status = "failed"
            detail = f"{spec.label} could not refresh its recursive submodules."
            after = inspect_repo(spec)
            return {
                "key": spec.key,
                "label": spec.label,
                "status": status,
                "detail": detail,
                "blockers": blockers,
                "before": before,
                "after": after,
                "commands": commands,
            }

    if spec.key == "unreal_samples":
        unreal_plugin = CHECKOUT_ROOT / "cesium-unreal"
        bridge = spec.path / "Plugins" / "cesium-unreal"
        if unreal_plugin.is_dir() and not bridge.exists():
            if not _ensure_directory_link(bridge, unreal_plugin, commands):
                blockers.append("unreal samples plugin bridge failed")
                status = "failed"
                detail = f"{spec.label} could not expose the Cesium Unreal plugin inside its Plugins folder."
                after = inspect_repo(spec)
                return {
                    "key": spec.key,
                    "label": spec.label,
                    "status": status,
                    "detail": detail,
                    "blockers": blockers,
                    "before": before,
                    "after": after,
                    "commands": commands,
                }

    after = inspect_repo(spec)
    return {
        "key": spec.key,
        "label": spec.label,
        "status": status,
        "detail": detail,
        "blockers": blockers,
        "before": before,
        "after": after,
        "commands": commands,
    }


def build_report(
    specs: list[RepoSpec],
    *,
    fetch: bool,
    allow_dirty: bool,
    update_submodules: bool,
) -> dict[str, Any]:
    repos = [
        prepare_repo(
            spec,
            fetch=fetch,
            allow_dirty=allow_dirty,
            update_submodules=update_submodules,
        )
        for spec in specs
    ]
    failed = [row for row in repos if row["status"] not in {"prepared"}]
    status = "pass" if not failed else "partial"
    return {
        "schema": "cesium.source_route_prepare.v1",
        "generated_at": utc_now(),
        "status": status,
        "checkout_root": str(CHECKOUT_ROOT),
        "policy": {
            "fetch": fetch,
            "allow_dirty": allow_dirty,
            "update_submodules": update_submodules,
        },
        "repos": repos,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Cesium Source Route Prepare",
        "",
        f"- status: `{report['status']}`",
        f"- checkout_root: `{report['checkout_root']}`",
        f"- fetch: `{report['policy']['fetch']}`",
        f"- allow_dirty: `{report['policy']['allow_dirty']}`",
        f"- update_submodules: `{report['policy']['update_submodules']}`",
        "",
    ]
    for repo in report["repos"]:
        lines.extend(
            [
                f"## {repo['label']}",
                "",
                f"- status: `{repo['status']}`",
                f"- detail: `{repo['detail']}`",
                f"- official: `{repo['before'].get('official')}`",
                f"- path: `{repo['before']['path']}`",
                f"- remote_url: `{repo['before'].get('remote_url')}`",
                f"- target_branch: `{repo['before']['target_branch']}`",
                f"- resolved_target_branch: `{repo['after'].get('resolved_target_branch')}`",
                f"- before_branch: `{repo['before'].get('current_branch')}`",
                f"- after_branch: `{repo['after'].get('current_branch')}`",
                f"- before_commit: `{repo['before'].get('head_commit')}`",
                f"- after_commit: `{repo['after'].get('head_commit')}`",
                "",
            ]
        )
        blockers = repo.get("blockers") or []
        lines.append("### Blockers")
        lines.append("")
        if blockers:
            for blocker in blockers:
                lines.append(f"- {blocker}")
        else:
            lines.append("- none")
        lines.append("")
    return "\n".join(lines)


def selected_specs(repo_keys: list[str] | None) -> list[RepoSpec]:
    specs = default_repo_specs()
    if not repo_keys:
        return specs
    key_set = set(repo_keys)
    return [spec for spec in specs if spec.key in key_set]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        selected_specs(args.repos),
        fetch=not args.no_fetch,
        allow_dirty=args.allow_dirty,
        update_submodules=not args.skip_submodules,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"json: {display_path(args.json_out)}")
    print(f"md: {display_path(args.md_out)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
