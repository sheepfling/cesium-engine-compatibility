#!/usr/bin/env python3
"""Prepare a local Cesium dev environment and run the default quick check.

This wrapper exists so a fresh host can bootstrap the editable install and
scratch paths in one step instead of hand-managing temp directories and pytest
arguments.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import tempfile
import venv
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_ROOT = ROOT / "build" / "tool_bootstrap" / "cesium"
DEFAULT_DEPS_PREFIX = BOOTSTRAP_ROOT / "venv"
STATE_PATH = BOOTSTRAP_ROOT / "bootstrap_state.json"
DEFAULT_SMOKE_TARGETS = ("tests/test_cesium_tools.py", "tests/test_bootstrap_local_dev.py")


@dataclass(frozen=True)
class BootstrapState:
    python_version: str
    requirements: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "python_version": self.python_version,
            "requirements": list(self.requirements),
        }


@dataclass(frozen=True)
class BootstrapReadiness:
    host_state: str
    deps_ready: bool
    work_roots_ready: bool
    state_present: bool


def _default_work_root() -> Path:
    if platform.system().lower() == "windows":
        preferred = Path(tempfile.gettempdir()) / "cesium_dev"
        if _windows_short_root_available(preferred.parent):
            return preferred
        return ROOT / "build" / "work" / "cesium_dev"
    return ROOT / "build" / "work" / "dev"


def _windows_short_root_available(parent: Path) -> bool:
    try:
        with tempfile.TemporaryDirectory(dir=parent):
            return True
    except OSError:
        return False


DEFAULT_WORK_ROOT = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_dev_requirements() -> tuple[str, ...]:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - Python 3.11 fallback
        raise RuntimeError("tomllib is required to read pyproject.toml") from exc

    payload = tomllib.loads(pyproject)
    project = payload.get("project", {})
    optional = project.get("optional-dependencies", {})
    requirements = optional.get("dev", [])
    if not isinstance(requirements, list) or not requirements:
        raise RuntimeError("pyproject.toml does not define a non-empty dev extra")
    return tuple(str(item) for item in requirements)


def _prefix_paths(prefix: Path) -> dict[str, Path]:
    paths = sysconfig.get_paths(vars={"base": str(prefix), "platbase": str(prefix)})
    return {name: Path(value) for name, value in paths.items()}


def prefix_site_packages(prefix: Path) -> Path:
    return _prefix_paths(prefix)["purelib"]


def bootstrap_python(prefix: Path) -> Path:
    if platform.system().lower() == "windows":
        return prefix / "Scripts" / "python.exe"
    return prefix / "bin" / "python"


def load_state() -> BootstrapState | None:
    if not STATE_PATH.is_file():
        return None
    payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    python_version = str(payload.get("python_version", ""))
    requirements = payload.get("requirements", [])
    if not python_version or not isinstance(requirements, list):
        return None
    return BootstrapState(python_version=python_version, requirements=tuple(str(item) for item in requirements))


def classify_bootstrap_state(*, deps_ready: bool, work_roots_ready: bool, state_present: bool) -> str:
    if deps_ready and work_roots_ready:
        return "fully-configured"
    if deps_ready or work_roots_ready or state_present:
        return "semi-configured"
    return "fresh-host"


def detect_bootstrap_readiness(prefix: Path, work_root: Path, requirements: tuple[str, ...]) -> BootstrapReadiness:
    expected = BootstrapState(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        requirements=requirements,
    )
    current = load_state()
    deps_ready = current == expected and bootstrap_python(prefix).is_file() and prefix_site_packages(prefix).is_dir()
    work_roots_ready = all((work_root / name).is_dir() for name in ("tmp", "artifacts"))
    state_present = current is not None
    return BootstrapReadiness(
        host_state=classify_bootstrap_state(
            deps_ready=deps_ready,
            work_roots_ready=work_roots_ready,
            state_present=state_present,
        ),
        deps_ready=deps_ready,
        work_roots_ready=work_roots_ready,
        state_present=state_present,
    )


def write_state(state: BootstrapState) -> None:
    BOOTSTRAP_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")


def _ensure_bootstrap_venv(prefix: Path) -> Path:
    python = bootstrap_python(prefix)
    if python.is_file():
        return python
    prefix.parent.mkdir(parents=True, exist_ok=True)
    builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=False, upgrade_deps=False)
    builder.create(prefix)
    if not python.is_file():
        raise SystemExit(f"bootstrap virtualenv did not create expected python at {python}")
    return python


def ensure_dev_dependencies(prefix: Path, requirements: tuple[str, ...]) -> bool:
    current = load_state()
    expected = BootstrapState(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        requirements=requirements,
    )
    python = bootstrap_python(prefix)
    site_packages = prefix_site_packages(prefix)
    if current == expected and python.is_file() and site_packages.is_dir():
        return False

    python = _ensure_bootstrap_venv(prefix)
    cmd = [
        str(python),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--disable-pip-version-check",
        "-e",
        ".[dev]",
    ]
    completed = subprocess.run(cmd, cwd=ROOT, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    write_state(expected)
    return True


def ensure_work_roots(work_root: Path) -> dict[str, Path]:
    roots = {
        "CESIUM_DEV_TMP_ROOT": work_root / "tmp",
        "CESIUM_DEV_ARTIFACT_ROOT": work_root / "artifacts",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    return roots


def build_env(work_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    roots = ensure_work_roots(work_root)
    for key, path in roots.items():
        env.setdefault(key, str(path))
    temp_root = work_root / "tmp"
    upm_cache_root = temp_root / "UPMCache"
    upm_config_root = temp_root / "UPMConfig"
    upm_npm_cache_path = temp_root / "UPMNpmCache"
    for path in (upm_cache_root, upm_config_root, upm_npm_cache_path):
        path.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    env["UPM_CACHE_ROOT"] = str(upm_cache_root)
    env["UPM_CONFIG_ROOT"] = str(upm_config_root)
    env["UPM_NPM_CACHE_PATH"] = str(upm_npm_cache_path)
    return env


def build_dev_check_command(dev_check_args: list[str], *, python_executable: Path | str | None = None) -> list[str]:
    args = list(dev_check_args)
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        args = list(DEFAULT_SMOKE_TARGETS)
    return [str(python_executable or sys.executable), "-m", "pytest", *args]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps-prefix", type=Path, default=DEFAULT_DEPS_PREFIX, help="Virtualenv root for local Python dev dependencies")
    parser.add_argument("--work-root", type=Path, default=None, help="Scratch root for bootstrap temp state and artifacts")
    parser.add_argument("--skip-install", action="store_true", help="Skip installing dev dependencies and only prepare the runtime environment")
    parser.add_argument("--prepare-only", action="store_true", help="Install dev dependencies and scratch roots without running pytest")
    parser.add_argument("dev_check_args", nargs=argparse.REMAINDER, default=[], help="Arguments forwarded to pytest")
    args = parser.parse_args(argv)
    if args.work_root is None:
        args.work_root = _default_work_root()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args() if argv is None else parse_args(argv)
    requirements = load_dev_requirements()
    readiness = detect_bootstrap_readiness(args.deps_prefix, args.work_root, requirements)
    print(f"bootstrap state: {readiness.host_state}")
    if readiness.host_state == "fresh-host":
        print("bootstrap plan: install dev deps, create work roots, then run the quick check")
    elif readiness.host_state == "semi-configured":
        print("bootstrap plan: repair any missing dev deps or work roots, then run the quick check")
    else:
        print("bootstrap plan: reuse the existing dev deps and work roots, then run the quick check")

    if not args.skip_install:
        installed = ensure_dev_dependencies(args.deps_prefix, requirements)
        print(f"dev dependencies: {'installed' if installed else 'already present'}")
    else:
        print("dev dependencies: skipped")

    env = build_env(args.work_root)
    print("bootstrap work root:", args.work_root)
    print("bootstrap deps venv:", args.deps_prefix)
    if args.prepare_only:
        return 0

    bootstrap_python_executable = bootstrap_python(args.deps_prefix)
    command_python = bootstrap_python_executable if bootstrap_python_executable.is_file() else sys.executable
    command = build_dev_check_command(args.dev_check_args, python_executable=command_python)
    print("+", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
