from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prepare_route = load_module("prepare_cesium_source_route", "extensions/cesium/tools/prepare_cesium_source_route.py")
example_workflow = load_module("cesium_example_workflow", "extensions/cesium/tools/cesium_example_workflow.py")
bootstrap_local_dev = load_module("bootstrap_local_dev", "tools/bootstrap_local_dev.py")
cesium_cli = load_module("cesium_cli", "cesium.py")


def test_prepare_source_route_report_shape() -> None:
    report = prepare_route.build_report(
        prepare_route.default_repo_specs(),
        fetch=False,
        allow_dirty=True,
        update_submodules=False,
    )

    assert report["schema"] == "cesium.source_route_prepare.v1"
    assert report["checkout_root"].endswith(r"external\cesium")
    assert len(report["repos"]) == 4
    assert {repo["key"] for repo in report["repos"]} == {
        "unreal_plugin",
        "unity_plugin",
        "unreal_samples",
        "godot_plugin",
    }
    unreal = next(repo for repo in report["repos"] if repo["key"] == "unreal_plugin")
    assert unreal["before"]["target_branch"] == "main"
    assert unreal["detail"].startswith("Cesium Unreal plugin")


@pytest.fixture()
def example_repo_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "repo"
    source_root = root / "external" / "cesium"
    report_dir = root / "artifacts" / "reports" / "cesium_examples"
    monkeypatch.setattr(example_workflow, "ROOT", root)
    monkeypatch.setattr(example_workflow, "SOURCE_ROUTE_ROOT", source_root)
    monkeypatch.setattr(example_workflow, "DEFAULT_REPORT_DIR", report_dir)

    engine_specs: dict[str, dict[str, object]] = {}
    for engine, spec in example_workflow.ENGINE_SPECS.items():
        example_root = root / "extensions" / "cesium" / "examples" / engine / "CesiumVanillaExample"
        if engine == "unreal":
            project_marker = example_root / "CesiumVanillaExample.uproject"
            sample_checkout = source_root / "cesium-unreal-samples"
        elif engine == "unity":
            project_marker = example_root / "ProjectSettings" / "ProjectVersion.txt"
            sample_checkout = None
        else:
            project_marker = example_root / "project.godot"
            sample_checkout = None
        engine_specs[engine] = {
            **spec,
            "source_checkout": source_root / str(Path(spec["source_checkout"]).name),
            "sample_checkout": sample_checkout,
            "example_root": example_root,
            "project_marker": project_marker,
        }
        example_root.mkdir(parents=True, exist_ok=True)
        project_marker.parent.mkdir(parents=True, exist_ok=True)
        project_marker.write_text("marker\n", encoding="utf-8")
        source_checkout = Path(engine_specs[engine]["source_checkout"])
        source_checkout.mkdir(parents=True, exist_ok=True)
        if isinstance(sample_checkout, Path):
            sample_checkout.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(example_workflow, "ENGINE_SPECS", engine_specs)
    return root


def test_example_workflow_reports_are_self_consistent(example_repo_layout: Path) -> None:
    for engine in ("unreal", "unity", "godot"):
        discover = example_workflow.discover_payload(engine)
        doctor = example_workflow.doctor_payload(engine)
        report = example_workflow.report_payload(engine)
        full = example_workflow.full_payload(engine)

        assert discover["schema"] == "cesium.example_lane_discovery.v1"
        assert doctor["schema"] == "cesium.example_lane_doctor.v1"
        assert report["schema"] == "cesium.example_lane_report.v1"
        assert full["schema"] == "cesium.example_lane_full.v1"
        assert report["summary"]["prepare_source_route"].endswith("prepare_cesium_source_route.py")
        assert report["readiness"]["source_route_ready"] is True
        assert report["readiness"]["example_scaffold_ready"] is True
        assert doctor["status"] == "ok"


def test_root_cli_dispatches_to_expected_scripts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, list[str]]] = []

    def fake_run_script(script: Path, argv: list[str]) -> int:
        calls.append((script, argv))
        return 7

    monkeypatch.setattr(cesium_cli, "_run_script", fake_run_script)

    exit_code = cesium_cli.main(["prepare-source-route", "--no-fetch"])
    assert exit_code == 7
    assert calls[-1][0].name == "prepare_cesium_source_route.py"
    assert calls[-1][1] == ["--no-fetch"]

    exit_code = cesium_cli.main(["bootstrap", "--prepare-only"])
    assert exit_code == 7
    assert calls[-1][0].name == "bootstrap_local_dev.py"
    assert calls[-1][1] == ["--prepare-only"]

    exit_code = cesium_cli.main(["example", "doctor", "--engine", "unreal"])
    assert exit_code == 7
    assert calls[-1][0].name == "cesium_example_workflow.py"
    assert calls[-1][1] == ["doctor", "--engine", "unreal"]


def test_pyproject_exposes_console_script() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "cesium-engine-compatibility"
    assert pyproject["project"]["scripts"]["cesium"] == "cesium:main"
    assert pyproject["tool"]["setuptools"]["py-modules"] == ["cesium"]
