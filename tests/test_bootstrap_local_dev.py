from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bootstrap_local_dev


def test_load_dev_requirements_uses_pyproject_dev_extra() -> None:
    requirements = bootstrap_local_dev.load_dev_requirements()

    assert "pytest>=8" in requirements


def test_build_dev_check_command_defaults_to_quick_check() -> None:
    command = bootstrap_local_dev.build_dev_check_command([])

    assert command[:3] == [sys.executable, "-m", "pytest"]
    assert command[-2:] == ["tests/test_cesium_tools.py", "tests/test_bootstrap_local_dev.py"]


def test_build_env_sets_bootstrap_paths(monkeypatch, tmp_path: Path) -> None:
    prefix = tmp_path / "deps"
    work_root = tmp_path / "work"
    prefix_site = bootstrap_local_dev.prefix_site_packages(prefix)
    prefix_site.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYTHONPATH", "existing-path")

    env = bootstrap_local_dev.build_env(prefix, work_root)

    parts = env["PYTHONPATH"].split(";")
    assert parts[0] == str(prefix_site)
    assert parts[1] == str(bootstrap_local_dev.ROOT)
    assert parts[2] == "existing-path"
    assert env["CESIUM_DEV_TMP_ROOT"] == str(work_root / "tmp")
    assert env["CESIUM_DEV_ARTIFACT_ROOT"] == str(work_root / "artifacts")
    assert env["TEMP"] == str(work_root / "tmp")
    assert env["TMP"] == str(work_root / "tmp")


def test_default_work_root_prefers_short_windows_tmp_root(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap_local_dev.platform, "system", lambda: "Windows")
    monkeypatch.setattr(bootstrap_local_dev, "_windows_short_root_available", lambda *_args: True)

    assert bootstrap_local_dev._default_work_root() == Path("C:/tmp/cesium_dev")


def test_default_work_root_falls_back_when_windows_tmp_is_not_writable(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap_local_dev.platform, "system", lambda: "Windows")
    monkeypatch.setattr(bootstrap_local_dev, "_windows_short_root_available", lambda *_args: False)

    assert bootstrap_local_dev._default_work_root() == bootstrap_local_dev.ROOT / "build" / "work" / "cesium_dev"


def test_classify_bootstrap_state_covers_host_variants() -> None:
    assert bootstrap_local_dev.classify_bootstrap_state(deps_ready=False, work_roots_ready=False, state_present=False) == "fresh-host"
    assert bootstrap_local_dev.classify_bootstrap_state(deps_ready=True, work_roots_ready=False, state_present=True) == "semi-configured"
    assert bootstrap_local_dev.classify_bootstrap_state(deps_ready=True, work_roots_ready=True, state_present=True) == "fully-configured"


def test_main_reports_bootstrap_state(monkeypatch, capsys) -> None:
    args = argparse.Namespace(
        deps_prefix=Path("deps"),
        work_root=Path("work"),
        skip_install=True,
        prepare_only=True,
        dev_check_args=[],
    )
    readiness = bootstrap_local_dev.BootstrapReadiness(
        host_state="semi-configured",
        deps_ready=True,
        work_roots_ready=False,
        state_present=True,
    )

    monkeypatch.setattr(bootstrap_local_dev, "parse_args", lambda: args)
    monkeypatch.setattr(bootstrap_local_dev, "load_dev_requirements", lambda: ("pytest>=8",))
    monkeypatch.setattr(bootstrap_local_dev, "detect_bootstrap_readiness", lambda *_args: readiness)
    monkeypatch.setattr(bootstrap_local_dev, "build_env", lambda *_args: {})

    assert bootstrap_local_dev.main() == 0

    out = capsys.readouterr().out
    assert "bootstrap state: semi-configured" in out
    assert "bootstrap plan: repair any missing dev deps or work roots" in out
