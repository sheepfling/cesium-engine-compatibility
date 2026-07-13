from __future__ import annotations

import json
import os
import tomllib
import subprocess
from pathlib import Path
import zipfile
from types import SimpleNamespace

import pytest
import cesium
import cesium.cli as cesium_cli
from extensions.cesium.tools import (
    cesium_example_workflow as example_workflow,
    engine_root_discovery,
    godot_linux_docker,
    linux_docker_runner,
    prepare_cesium_source_route as prepare_route,
    unity_linux_docker,
    unreal_linux_docker,
    unreal_linux_lane,
)
from tools import (
    bootstrap_local_dev,
    build_cesium_engine_matrix,
    build_cesium_compatibility_packet,
    build_cesium_cross_platform_fix_notes,
    build_cesium_execution_audit,
    build_cesium_host_inventory,
    build_cesium_visual_proof,
    build_cesium_planned_routes,
    build_godot_visual_proof,
    build_unreal_visual_proof,
    build_windows_visual_proof,
    build_godot_example,
    compare_cesium_visual_proof,
    build_unity_example,
    build_unity_native_matrix,
    build_unity_visual_proof,
    capture_unity_host_report,
    export_unity_host_handoff,
    import_unity_host_report,
    godot_aggressive_launcher,
    godot_bootstrap,
    normalize_cesium_visual_proof,
    godot_versioning,
    run_cesium_plugin_lanes,
    run_windows_visual_proof,
    godot_doctor,
    validate_visual_proof_roots,
    validate_visual_proof_contracts,
    stage_unity_host_report,
    unity_env,
)


ROOT = Path(__file__).resolve().parents[1]


def _portable_path(value: str | Path) -> str:
    return str(value).replace("\\", "/")


def _write_visual_proof_png(
    path: Path,
    *,
    background: tuple[int, int, int],
    accent: tuple[int, int, int],
    patterned: bool = True,
) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (192, 128), background)
    draw = ImageDraw.Draw(image)
    if patterned:
        for row in range(8):
            for column in range(12):
                left = column * 16
                top = row * 16
                right = left + 16
                bottom = top + 16
                tile = (
                    (background[0] + row * 17 + column * 11) % 256,
                    (background[1] + row * 13 + column * 19) % 256,
                    (background[2] + row * 23 + column * 7) % 256,
                )
                draw.rectangle((left, top, right, bottom), fill=tile)
        draw.rectangle((12, 12, 180, 116), outline=accent, width=4)
        draw.ellipse((56, 24, 136, 104), outline=(255, 255, 255), width=4)
        draw.line((24, 104, 168, 32), fill=accent, width=3)
        draw.line((24, 32, 168, 104), fill=(255, 255, 255), width=2)
    image.save(path)


def _seed_visual_proof_source(source_root: Path) -> None:
    palette = {
        "proxy": ((32, 68, 144), (250, 198, 92)),
        "cesium": ((14, 88, 72), (86, 208, 248)),
    }
    for variant, (background, accent) in palette.items():
        for shot in build_cesium_visual_proof.CAMERA_SHOTS:
            _write_visual_proof_png(source_root / f"{variant}_{shot.name}.png", background=background, accent=accent)


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


def test_prepare_source_route_honors_repo_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTDIS_CESIUM_UNREAL_REMOTE", "https://example.invalid/cesium-unreal.git")
    monkeypatch.setenv("FASTDIS_CESIUM_UNREAL_BRANCH", "macos-dev")
    monkeypatch.setenv("FASTDIS_CESIUM_GODOT_REMOTE", "https://example.invalid/3D-Tiles-For-Godot.git")
    monkeypatch.setenv("FASTDIS_CESIUM_GODOT_BRANCH", "macos")

    specs = prepare_route.default_repo_specs()
    unreal = next(spec for spec in specs if spec.key == "unreal_plugin")
    godot = next(spec for spec in specs if spec.key == "godot_plugin")

    assert unreal.remote_url == "https://example.invalid/cesium-unreal.git"
    assert unreal.target_branch == "macos-dev"
    assert godot.remote_url == "https://example.invalid/3D-Tiles-For-Godot.git"
    assert godot.target_branch == "macos"


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
            sample_plugin_bridge = sample_checkout / "Plugins" / "cesium-unreal"
        elif engine == "unity":
            project_marker = example_root / "ProjectSettings" / "ProjectVersion.txt"
            sample_checkout = None
            sample_plugin_bridge = None
            packages_dir = example_root / "Packages"
            packages_dir.mkdir(parents=True, exist_ok=True)
            (packages_dir / "manifest.json").write_text(
                """
{
  "dependencies": {
    "com.unity.collab-proxy": "2.6.1",
    "com.unity.feature.development": "1.0.1",
    "com.unity.ide.rider": "3.0.31",
    "com.unity.ide.visualstudio": "2.0.23",
    "com.unity.inputsystem": "1.14.2",
    "com.unity.test-framework": "1.4.5",
    "com.unity.textmeshpro": "3.2.0",
    "com.unity.timeline": "1.8.10",
    "com.unity.ugui": "2.0.1",
    "com.unity.visualscripting": "1.9.6"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
        else:
            project_marker = example_root / "project.godot"
            sample_checkout = None
            sample_plugin_bridge = None
            (example_root / "scenes").mkdir(parents=True, exist_ok=True)
            (example_root / "scenes" / "Main.tscn").write_text("[gd_scene format=3]\n\n[node name=\"Main\" type=\"Node3D\"]\n", encoding="utf-8")
            (example_root / "export_presets.cfg").write_text(
                """
[preset.0]
name="Windows Desktop"
platform="Windows Desktop"
runnable=true
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/godot/CesiumVanillaExample/windows/CesiumVanillaExample.exe"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=1

[preset.0.options]
binary_format/architecture="x86_64"
""".strip()
                + "\n",
                encoding="utf-8",
            )
        engine_specs[engine] = {
            **spec,
            "source_checkout": source_root / str(Path(spec["source_checkout"]).name),
            "sample_checkout": sample_checkout,
            "sample_plugin_bridge": sample_plugin_bridge,
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
        if isinstance(sample_plugin_bridge, Path):
            sample_plugin_bridge.mkdir(parents=True, exist_ok=True)
        if engine == "unity":
            project_marker.write_text(
                "m_EditorVersion: 6000.5.0f1\nm_EditorVersionWithRevision: 6000.5.0f1\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(example_workflow, "ENGINE_SPECS", engine_specs)
    monkeypatch.setattr(
        example_workflow,
        "discover_godot_windows_versions",
        lambda: [
            {
                "version": "4.6.3-stable",
                "platform": "windows",
                "root": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe" / "Godot_v4.6.3-stable_win64.exe",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe" / "Godot_v4.6.3-stable_win64_console.exe",
            },
            {
                "version": "4.7-stable",
                "platform": "windows",
                "root": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7-stable_win64.exe",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7-stable_win64.exe" / "Godot_v4.7-stable_win64.exe",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7-stable_win64.exe" / "Godot_v4.7-stable_win64_console.exe",
            },
            {
                "version": "4.7.1-rc1",
                "platform": "windows",
                "root": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7.1-rc1_win64.exe",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7.1-rc1_win64.exe" / "Godot_v4.7.1-rc1_win64.exe",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.7.1-rc1_win64.exe" / "Godot_v4.7.1-rc1_win64_console.exe",
            },
            {
                "version": "4.8-dev1",
                "platform": "windows",
                "root": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe" / "Godot_v4.8-dev1_win64.exe",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe" / "Godot_v4.8-dev1_win64_console.exe",
            },
        ],
    )
    monkeypatch.setattr(
        example_workflow,
        "discover_godot_linux_versions",
        lambda: [
            {
                "version": "4.6.3-stable",
                "platform": "linux",
                "root": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.6.3-stable_linux.x86_64",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.6.3-stable_linux.x86_64" / "Godot_v4.6.3-stable_linux.x86_64",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.6.3-stable_linux.x86_64" / "Godot_v4.6.3-stable_linux_console.exe",
            },
            {
                "version": "4.7-stable",
                "platform": "linux",
                "root": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7-stable_linux.x86_64",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7-stable_linux.x86_64" / "Godot_v4.7-stable_linux.x86_64",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7-stable_linux.x86_64" / "Godot_v4.7-stable_linux_console.exe",
            },
            {
                "version": "4.7.1-rc1",
                "platform": "linux",
                "root": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7.1-rc1_linux.x86_64",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7.1-rc1_linux.x86_64" / "Godot_v4.7.1-rc1_linux.x86_64",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.7.1-rc1_linux.x86_64" / "Godot_v4.7.1-rc1_linux_console.exe",
            },
            {
                "version": "4.8-dev1",
                "platform": "linux",
                "root": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.8-dev1_linux.x86_64",
                "executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.8-dev1_linux.x86_64" / "Godot_v4.8-dev1_linux.x86_64",
                "console_executable": engine_root_discovery.godot_public_root() / "engines" / "linux" / "Godot_v4.8-dev1_linux.x86_64" / "Godot_v4.8-dev1_linux_console.exe",
            },
        ],
    )
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
        assert report["summary"]["prepare_source_route"] == "cesium-prepare-source-route"
        assert report["readiness"]["source_route_ready"] is True
        assert report["readiness"]["example_scaffold_ready"] is True
        assert doctor["status"] == "ok"
        if engine == "unreal":
            assert discover["compatibility_tracking"]["supported_native_targets"] == ["windows", "linux", "mac"]
            assert doctor["compatibility_tracking"]["supported_native_targets"] == ["windows", "linux", "mac"]
            assert any(Path(path).name == "Unreal" for path in discover["compatibility_tracking"]["public_search_roots"])
        if engine == "unity":
            assert discover["compatibility_tracking"]["pinned_editor"] == "6000.5.0f1"
            assert doctor["compatibility_tracking"]["pinned_editor"] == "6000.5.0f1"
            assert discover["compatibility_tracking"]["native_target"] == "windows"
            assert discover["compatibility_tracking"]["supported_native_targets"] == ["windows", "linux", "mac"]
            assert set(discover["compatibility_tracking"]["native_lane_commands"]) == {"windows", "linux", "mac"}
            assert discover["compatibility_tracking"]["version_matrix"][0]["version"] == "6000.5.0f1"
            assert doctor["compatibility_tracking"]["version_matrix"][0]["package_count"] == 10
            assert doctor["compatibility_tracking"]["version_matrix"][0]["package_dependencies"]["com.unity.inputsystem"] == "1.14.2"
            assert any(Path(path).name == "Unity" for path in discover["compatibility_tracking"]["public_search_roots"])
        if engine == "godot":
            assert discover["compatibility_tracking"]["pinned_editor"] == "4.7"
            assert doctor["compatibility_tracking"]["native_target"] == "windows"
            assert doctor["compatibility_tracking"]["supported_native_targets"] == ["windows", "linux", "mac"]
            assert set(doctor["compatibility_tracking"]["native_lane_commands"]) == {"windows", "linux", "mac"}
            assert doctor["compatibility_tracking"]["native_lane_commands"]["linux"]["host_note"].startswith("Linux should")
            assert [row["version"] for row in doctor["compatibility_tracking"]["windows_version_matrix"]] == [
                "4.6.3-stable",
                "4.7-stable",
                "4.7.1-rc1",
                "4.8-dev1",
            ]
            assert [row["version"] for row in doctor["compatibility_tracking"]["linux_version_matrix"]] == [
                "4.6.3-stable",
                "4.7-stable",
                "4.7.1-rc1",
                "4.8-dev1",
            ]
            assert any(Path(path).name == "Godot" for path in discover["compatibility_tracking"]["public_search_roots"])
            assert doctor["native_target"] is None
        if engine == "unreal":
            bridge_check = next(check for check in doctor["checks"] if check["name"] == "sample_plugin_bridge")
            assert bridge_check["status"] == "ok"


def test_unity_native_matrix_report_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        build_unity_native_matrix.cesium_example_workflow,
        "report_payload",
        lambda engine, *, native_target=None: {
            "status": "ok",
            "compatibility_tracking": {
                "pinned_editor": "6000.5.0f1",
                "example_project_version": "6000.6.0b2",
                "supported_native_targets": ["windows", "linux", "mac"],
                "version_matrix": [{"version": "6000.5.0f1", "package_count": 10}],
            },
        },
    )
    monkeypatch.setattr(
        build_unity_native_matrix,
        "_latest_example_build_failure_signals",
        lambda: [
            "Package Manager tried to write under the installed editor tree and hit EPERM.",
            "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
        ],
    )
    monkeypatch.setattr(
        build_unity_native_matrix.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.3.19f1",
                install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.3.19f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Unity" / "6000.3.19f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="scan",
                quirks=(),
            ),
            unity_env.UnityInstall(
                version="6000.5.2f1",
                install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.2f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="scan",
                quirks=(),
            ),
            unity_env.UnityInstall(
                version="6000.6.0b2",
                install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.6.0b2"),
                editor_path=str(Path.cwd() / "tmp-public" / "Unity" / "6000.6.0b2" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="scan",
                quirks=(),
            ),
        ],
    )
    monkeypatch.setattr(
        build_unity_native_matrix.unity_env,
        "describe_host",
        lambda: {"platform": "Windows", "installs": [], "default_install": None, "public_roots": []},
    )

    payload = build_unity_native_matrix.build_payload()

    assert payload["schema"] == "cesium.unity_native_matrix.v1"
    assert payload["status"] == "partial"
    assert [target["target"] for target in payload["targets"]] == ["windows", "linux", "mac"]
    assert payload["targets"][0]["status"] == "verified"
    assert payload["targets"][0]["installed_versions"] == ["6000.3.19f1", "6000.5.2f1", "6000.6.0b2"]
    assert "Unity Linux/Docker remains planned." in payload["gaps"]
    assert payload["summary"]["installed_versions"] == ["6000.3.19f1", "6000.5.2f1", "6000.6.0b2"]
    assert payload["summary"]["latest_example_build_failure_signals"] == [
        "Package Manager tried to write under the installed editor tree and hit EPERM.",
        "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
    ]


def test_unity_native_matrix_cli_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_main(argv: list[str] | None = None) -> int:
        calls.append(list(argv or []))
        return 0

    monkeypatch.setattr(build_unity_native_matrix, "main", fake_main)

    exit_code = cesium_cli.main(["unity-native-matrix", "--json-out", "out.json"])

    assert exit_code == 0
    assert calls == [["--json-out", "out.json"]]


def test_unity_native_matrix_latest_failure_signals_falls_back_to_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report_dir = tmp_path / "unity_example_build"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "unity_example_build_6000_3_19f1_windows.json"
    log_path = report_dir / "unity_example_build_6000_3_19f1_windows.log"
    json_path.write_text(
        json.dumps(
            {
                "failure_signals": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    log_path.write_text(
        "Failed to resolve packages: EPERM: operation not permitted\n"
        "Unable to retrieve BIOS serial number. Exception: Access denied\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_unity_native_matrix, "UNITY_EXAMPLE_BUILD_DIR", report_dir)

    assert build_unity_native_matrix._latest_example_build_failure_signals() == [
        "Package Manager tried to write under the installed editor tree and hit EPERM.",
        "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
    ]


def test_unity_env_discovers_configured_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "Unity" / "Hub" / "Editor"
    install_root = base / "6000.5.0f1"
    editor = install_root / "Editor"
    editor.mkdir(parents=True, exist_ok=True)
    (editor / "Unity.exe").write_text("stub\n", encoding="utf-8")
    monkeypatch.setenv("FASTDIS_UNITY_ROOTS", str(base))
    monkeypatch.setattr(unity_env, "env_install", lambda version=None: None)
    monkeypatch.setattr(unity_env.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(unity_env, "scan_roots", lambda: [base])

    installs = unity_env.discover_installs()

    assert [install.version for install in installs] == ["6000.5.0f1"]
    assert installs[0].editor_path is not None
    assert unity_env.describe_host()["public_roots"][0] == str(base)
    assert unity_env.recommended_editor_overrides(installs[0])["FASTDIS_UNITY_EDITOR"].endswith(r"Unity.exe")


def test_unity_env_discovers_direct_install_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_root = tmp_path / "Unity" / "Hub" / "Editor" / "6000.5.0f1"
    editor = install_root / "Editor"
    editor.mkdir(parents=True, exist_ok=True)
    (editor / "Unity.exe").write_text("stub\n", encoding="utf-8")
    monkeypatch.setenv("FASTDIS_UNITY_ROOTS", str(install_root))
    monkeypatch.setattr(unity_env, "env_install", lambda version=None: None)
    monkeypatch.setattr(unity_env.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(unity_env, "scan_roots", lambda: [install_root])

    installs = unity_env.discover_installs()

    assert [install.version for install in installs] == ["6000.5.0f1"]
    assert installs[0].install_root == str(install_root)


def test_unity_default_scan_roots_include_public_root_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unity_env.platform, "system", lambda: "Windows")

    roots = unity_env.default_scan_roots()

    assert Path(roots[0]).name == "Unity"
    assert any(_portable_path(root).endswith("Program Files/Unity/Hub/Editor") for root in roots)


def test_unity_host_report_stage_export_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    reports = root / "artifacts" / "reports"
    host_root = root / "artifacts" / "verification_reports" / "unity_hosts"
    out_dir = root / "dist" / "unity_host_handoff"
    source_install_root = tmp_path / "Unity" / "Hub" / "Editor" / "6000.5.0f1"
    (source_install_root / "Editor").mkdir(parents=True, exist_ok=True)
    (source_install_root / "Editor" / "Unity.exe").write_text("stub\n", encoding="utf-8")
    monkeypatch.setenv("FASTDIS_UNITY_ROOTS", str(source_install_root.parent))
    monkeypatch.setattr(stage_unity_host_report, "ROOT", root)
    monkeypatch.setattr(unity_env, "env_install", lambda version=None: None)
    monkeypatch.setattr(unity_env.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(unity_env, "scan_roots", lambda: [source_install_root.parent])

    report = capture_unity_host_report.build_report()
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "unity_host_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (reports / "unity_host_report.md").write_text(capture_unity_host_report.render_markdown(report), encoding="utf-8")

    stage_unity_host_report.stage_report_set(reports, host_root / "local-host", stage_unity_host_report.REQUIRED_FILES, overwrite=True)
    archive = export_unity_host_handoff.export_archive(out_dir / "cesium-unity-host-handoff.zip", host_root)
    imported_root = import_unity_host_report.import_archive(archive, tmp_path / "imported")

    assert (host_root / "local-host" / "unity_host_report.json").is_file()
    assert (host_root / "local-host" / "unity_host_report_manifest.json").is_file()
    assert archive.is_file()
    assert (imported_root / "cesium-unity-host-handoff" / "tools" / "unity_env.py").is_file()
    assert (imported_root / "cesium-unity-host-handoff" / "docs" / "CESIUM_UNITY_VERSION_MATRIX.md").is_file()


def test_unity_example_build_dry_run_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        unity_env,
        "resolve_install",
        lambda version=None: unity_env.UnityInstall(
            version=version or "6000.5.2f1",
            install_root=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
            editor_path=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
            editor_app_path=None,
            source="test",
            quirks=(),
        ),
    )

    payload = build_unity_example.run_build(
        build_unity_example.parse_args(
            [
                "--dry-run",
                "--unity-version",
                "6000.5.2f1",
                "--build-target",
                "windows",
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
    )

    assert payload["schema"] == "cesium.unity_example_build.v1"
    assert payload["status"] == "dry-run"
    assert "-executeMethod" in payload["command"]
    assert "CesiumExample.CesiumExampleBuild.BuildFromCommandLine" in payload["command"]
    assert payload["command"].count("-cesiumBuildTarget") == 1
    target_index = payload["command"].index("-cesiumBuildTarget")
    assert payload["command"][target_index + 1] == "windows"
    log_index = payload["command"].index("-logFile")
    assert Path(payload["command"][log_index + 1]).name.endswith(".log")


def test_unity_example_build_adds_system_ca_to_node_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NODE_OPTIONS", "--trace-warnings")
    monkeypatch.setattr(
        unity_env,
        "resolve_install",
        lambda version=None: unity_env.UnityInstall(
            version=version or "6000.5.2f1",
            install_root=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
            editor_path=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
            editor_app_path=None,
            source="test",
            quirks=(),
        ),
    )
    (tmp_path / "project").mkdir(parents=True, exist_ok=True)

    captured: dict[str, object] = {}

    def fake_run(command, *, cwd=None, text=None, capture_output=None, env=None):  # type: ignore[no-untyped-def]
        captured["env"] = env
        captured["command"] = command
        if "-logFile" not in command:
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        log_index = command.index("-logFile")
        log_path = Path(command[log_index + 1])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("log line\n", encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    class FakeProcess:
        pid = 12345
        returncode = 0

        def poll(self):  # type: ignore[no-untyped-def]
            return self.returncode

        def wait(self, timeout=None):  # type: ignore[no-untyped-def]
            return self.returncode

    def fake_popen(command, *, cwd=None, text=None, stdout=None, stderr=None, env=None):  # type: ignore[no-untyped-def]
        captured["env"] = env
        captured["command"] = command
        log_index = command.index("-logFile")
        log_path = Path(command[log_index + 1])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("log line\n", encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(build_unity_example.subprocess, "run", fake_run)
    monkeypatch.setattr(build_unity_example.subprocess, "Popen", fake_popen)

    payload = build_unity_example.run_build(
        build_unity_example.parse_args(
            [
                "--unity-version",
                "6000.5.2f1",
                "--build-target",
                "windows",
                "--project-dir",
                str(tmp_path / "project"),
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
    )

    assert payload["status"] == "fail"
    assert isinstance(captured["env"], dict)
    assert captured["env"]["NODE_OPTIONS"] == "--trace-warnings --use-system-ca"


def test_unity_example_build_rewrites_project_version_for_selected_editor(tmp_path: Path) -> None:
    staged = tmp_path / "stage" / "CesiumVanillaExample"
    version_file = staged / "ProjectSettings" / "ProjectVersion.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(
        "m_EditorVersion: 6000.5.2f1\nm_EditorVersionWithRevision: 6000.5.2f1 (eb73d3b415a1)\n",
        encoding="utf-8",
    )

    build_unity_example._rewrite_project_version(staged, "6000.3.19f1")

    content = version_file.read_text(encoding="utf-8")
    assert "m_EditorVersion: 6000.3.19f1" in content
    assert "m_EditorVersionWithRevision: 6000.3.19f1 (aligned)" in content


def test_unity_example_build_failure_signals_surface_package_and_licensing_blocks() -> None:
    signals = build_unity_example._failure_signals(
        [
            "Failed to resolve packages: EPERM: operation not permitted, mkdir 'C:\\Program Files\\Unity\\Hub\\Editor\\6000.3.19f1\\Editor\\Data\\artifacts'. No packages loaded.",
            "Unable to retrieve BIOS serial number. Exception: System.Management.ManagementException: Access denied",
        ]
    )

    assert signals == [
        "Package Manager tried to write under the installed editor tree and hit EPERM.",
        "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
    ]


def test_unity_example_build_lane_uses_new_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_cesium_plugin_lanes.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.3.19f1",
                install_root=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.3.19f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.3.19f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="test",
                quirks=(),
            ),
            unity_env.UnityInstall(
                version="6000.5.2f1",
                install_root=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="test",
                quirks=(),
            ),
        ],
    )

    lane = run_cesium_plugin_lanes.resolve_lanes(["unity-example-build"])[0]

    assert lane.id == "unity-example-build"
    assert any("6000_3_19f1" in task.id for task in lane.tasks)
    assert any("tools.build_unity_example" in command for task in lane.tasks for command in task.commands)


def test_cesium_engine_matrix_report_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_example_report(engine: str, *, native_target: str | None = None) -> dict[str, object]:
        version_matrix_key = {
            "unreal": "version_matrix",
            "unity": "version_matrix",
            "godot": "windows_version_matrix" if native_target == "windows" else "linux_version_matrix",
        }[engine]
        tracking: dict[str, object] = {
            "public_search_roots": [f"{engine}-root"],
            "build_commands": [f"build-{engine}"],
            "native_lane_commands": {"windows": {"command": f"doctor {engine} windows"}},
        }
        if engine == "unreal":
            tracking["version_matrix"] = [{"version": "5.7"}, {"version": "5.8"}]
        elif engine == "unity":
            tracking["version_matrix"] = [{"version": "6000.5.0f1"}]
            tracking["pinned_editor"] = "6000.5.0f1"
            tracking["example_project_version"] = "6000.6.0b2"
        else:
            tracking[version_matrix_key] = [{"version": "4.7"}]
        return {
            "status": "ok",
            "preferred_version": "x",
            "compatibility_tracking": tracking,
            "next_steps": [f"next-{engine}"],
            "source_route_root": f"{engine}-source",
        }

    def fake_unreal_linux_report(*, engine_version: str | None = None) -> dict[str, object]:
        return {
            "schema": "cesium.unreal_linux_lane.v1",
            "status": "ok",
            "version_matrix": [{"engine_version": "5.7"}, {"engine_version": "5.8"}],
            "public_search_roots": [_portable_path(Path.cwd() / "tmp-public" / "Unreal")],
            "build_commands": ["docker build"],
            "next_steps": ["next-unreal-linux"],
        }

    monkeypatch.setattr(build_cesium_engine_matrix.cesium_example_workflow, "report_payload", fake_example_report)
    monkeypatch.setattr(build_cesium_engine_matrix.unreal_linux_lane, "report_payload", fake_unreal_linux_report)
    monkeypatch.setattr(
        build_cesium_engine_matrix.build_unity_native_matrix,
        "build_payload",
        lambda: {
            "status": "partial",
            "gaps": ["unity gap"],
            "evidence": [
                {
                    "surface": "unity-native",
                    "kind": "native_matrix",
                    "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json",
                }
            ],
            "targets": [
                {"target": "windows", "status": "verified", "commands": ["cesium-unity-example-build --unity-version 6000.5.2f1 --build-target windows"]},
                {"target": "linux", "status": "planned", "commands": ["cesium-unity-linux-docker --native-target linux"]},
                {"target": "mac", "status": "planned", "commands": ["cesium-plugin-lanes --dry-run --lanes unity-host-mac"]},
            ],
        },
    )
    monkeypatch.setattr(
        build_cesium_engine_matrix.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(version="6000.3.19f1", install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.3.19f1"), editor_path=None, editor_app_path=None, source="test", quirks=()),
            unity_env.UnityInstall(version="6000.5.2f1", install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.2f1"), editor_path=None, editor_app_path=None, source="test", quirks=()),
            unity_env.UnityInstall(version="6000.6.0b2", install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.6.0b2"), editor_path=None, editor_app_path=None, source="test", quirks=()),
        ],
    )

    payload = build_cesium_engine_matrix.build_payload()

    assert payload["schema"] == "cesium.engine_matrix.v1"
    assert payload["status"] == "partial"
    assert payload["lane_count"] == 7
    assert payload["summary"]["verified_lane_count"] == 5
    assert payload["summary"]["planned_lane_count"] == 2
    assert payload["summary"]["evidence_count"] >= 1
    assert payload["gaps"]
    assert any("Windows-native" in note or "Windows-native" in note for note in payload["claim_boundaries"])
    assert payload["summary"]["version_coverage"]["unreal"] == ["5.7", "5.8"]
    assert payload["summary"]["version_coverage"]["unity"] == ["6000.5.0f1"]
    assert payload["summary"]["version_coverage"]["unity_proof_lane"] == ["6000.5.0f1"]
    assert payload["summary"]["version_coverage"]["unity_example_project_version"] == ["6000.6.0b2"]
    assert payload["summary"]["version_coverage"]["unity_installed"] == ["6000.3.19f1", "6000.5.2f1", "6000.6.0b2"]
    assert "cesium-unity-linux-docker --native-target linux" in payload["summary"]["version_coverage"]["unity_linux_docker_planned"]
    assert payload["summary"]["version_coverage"]["unity_mac_planned"] == ["cesium-plugin-lanes --dry-run --lanes unity-host-mac"]
    assert payload["summary"]["version_coverage"]["unreal_linux"] == ["5.7", "5.8"]
    assert payload["summary"]["version_coverage"]["godot_mac_planned"] == ["cesium-plugin-lanes --dry-run --lanes godot-host-mac"]
    assert payload["related_packets"]["execution_audit"]["status"] == "present"
    assert payload["related_packets"]["planned_routes"]["status"] == "present"
    assert any(row["surface"] == "unity-native" for row in payload["evidence"])
    assert any(lane["lane"] == "godot-linux" for lane in payload["lanes"])
    assert any(lane["lane"] == "unity-linux-docker" for lane in payload["lanes"])
    assert payload["lanes"][0]["evidence_tier"] == "verified"
    assert payload["lanes"][2]["versions"] == ["6000.3.19f1", "6000.5.2f1", "6000.6.0b2"]
    assert next(lane for lane in payload["lanes"] if lane["lane"] == "unity-linux-docker")["evidence_tier"] == "planned"
    assert next(lane for lane in payload["lanes"] if lane["lane"] == "unity-linux-docker")["status"] == "planned"
    assert payload["lanes"][-1]["evidence_tier"] == "planned"
    assert payload["lanes"][-1]["status"] == "planned"
    assert any("BuildPlugin" in command or "build-plan" in command for lane in payload["lanes"] for command in lane["build_plan"])
    assert "Unity macOS remains planned." in payload["gaps"]
    assert payload["gaps"].count("Unity macOS remains planned.") == 1


def test_cesium_plugin_lanes_dry_run_expands_known_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_cesium_plugin_lanes.unreal_linux_lane,
        "report_payload",
        lambda: {
            "version_matrix": [{"engine_version": "5.7"}, {"engine_version": "5.8"}],
        },
    )
    monkeypatch.setattr(
        run_cesium_plugin_lanes.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.5.0f1",
                install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.0f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.0f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="test",
                quirks=(),
            )
        ],
    )
    monkeypatch.setattr(
        run_cesium_plugin_lanes.cesium_example_workflow,
        "report_payload",
        lambda engine, native_target=None: {
            "compatibility_tracking": {
                "windows_version_matrix": [{"version": "4.6.3-stable"}, {"version": "4.7-stable"}],
                "linux_version_matrix": [{"version": "4.6.3-stable"}, {"version": "4.7-stable"}],
            }
            if engine == "godot"
            else {
                "version_matrix": [{"version": "6000.5.0f1"}],
            },
        },
    )

    args = run_cesium_plugin_lanes.parse_args(["--dry-run", "--lanes", "unreal-linux-docker", "unity-host"])

    payload = run_cesium_plugin_lanes.build_payload(args)

    assert payload["schema"] == "cesium.plugin_lane_runner.v1"
    assert payload["overall_status"] == "dry-run"
    assert payload["selected_lanes"] == ["unreal-linux-docker", "unity-host"]
    unreal = payload["lanes"][0]
    unity = payload["lanes"][1]
    assert any("build-plan --engine-version 5.7" in command["command"] for command in unreal["tasks"][0]["commands"])
    assert any("build --engine-version 5.8" in command["command"] for command in unreal["tasks"][-1]["commands"])
    assert any("cesium-capture-unity-host-report" in command["command"] for command in unity["tasks"][0]["commands"])
    assert any("cesium-export-unity-host-handoff" in command["command"] for command in unity["tasks"][-1]["commands"])
    all_lanes = run_cesium_plugin_lanes.resolve_lanes(["all"])
    assert all_lanes[0].id == "execution-audit"
    assert any(lane.id == "godot-host-windows" for lane in all_lanes)
    assert any(lane.id == "unity-host-linux-docker" for lane in all_lanes)
    assert any(lane.id == "unity-host-mac" for lane in all_lanes)
    unity_linux = next(lane for lane in all_lanes if lane.id == "unity-host-linux-docker")
    assert any("-m extensions.cesium.tools.unity_linux_docker" in command for task in unity_linux.tasks for command in task.commands)
    unity_mac = next(lane for lane in all_lanes if lane.id == "unity-host-mac")
    assert any("--native-target mac" in command for task in unity_mac.tasks for command in task.commands)
    planned_bundle = next(lane for lane in all_lanes if lane.id == "cross-platform-planned")
    assert planned_bundle.lane_kind == "bundle"
    assert any(task.id.startswith("unreal-linux-build-plan-") for task in planned_bundle.tasks)
    assert any(task.id.startswith("unity-linux-docker-") for task in planned_bundle.tasks)
    assert any(task.id.startswith("unity-capture-") for task in planned_bundle.tasks)
    assert any(task.id.startswith("godot-report-mac-") for task in planned_bundle.tasks)
    assert any(task.id.startswith("godot-build-mac-") for task in planned_bundle.tasks)
    bundle_payload = run_cesium_plugin_lanes.build_payload(
        run_cesium_plugin_lanes.parse_args(["--dry-run", "--lanes", "cross-platform-planned"])
    )
    rendered = run_cesium_plugin_lanes.render_markdown(bundle_payload)
    assert "## Planned Route Bundles" in rendered
    assert "cross-platform-planned" in rendered
    assert "-m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version 5.7" in rendered
    assert "cesium-example report --engine godot --native-target mac" in rendered


def test_cesium_plugin_lanes_cli_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_command(command: str, argv: list[str]) -> int:
        calls.append((command, argv))
        return 7

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["plugin-lanes", "--dry-run", "--lanes", "matrix-refresh"])

    assert exit_code == 7
    assert calls[-1][0] == "plugin-lanes"
    assert calls[-1][1] == ["--lanes", "matrix-refresh", "--dry-run"]


def test_cesium_execution_audit_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_cesium_execution_audit, "_available_docker", lambda: True)
    unity_linux_docker_report = tmp_path / "cesium-unity_linux_docker.json"
    unity_linux_docker_report.write_text(
        json.dumps(
            {
                "blocker_signals": [
                    "The Linux container did not discover a Unity editor install, so this lane is still proof-of-commandability only.",
                    "Unity Linux/Docker still has no installed editor versions inside the container.",
                    "Unity Linux/Docker remains planned.",
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {
            "unreal": [build_cesium_execution_audit.engine_root_discovery.unreal_public_root()],
            "godot": [build_cesium_execution_audit.engine_root_discovery.godot_public_root()],
            "unity": [build_cesium_execution_audit.engine_root_discovery.unity_public_root()],
        },
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.unreal_linux_lane,
        "report_payload",
        lambda: {
            "version_matrix": [{"engine_version": "5.7"}, {"engine_version": "5.8"}],
            "build_status": "verified",
            "build_result": "succeeded",
            "build_log": "artifacts/reports/unreal_linux_docker/cesium_unreal_linux_build_5.8.log",
            "build_output_binary": "/ue/Engine/Binaries/Linux/UnrealGame-Linux-Shipping",
            "linux_platform_support_search_roots": [build_cesium_execution_audit.engine_root_discovery.unreal_public_root() / "Engine" / "Platforms" / "Linux"],
            "linux_platform_support_roots": [build_cesium_execution_audit.engine_root_discovery.unreal_public_root() / "Engine" / "Platforms" / "Linux"],
            "linux_platform_support_ready": True,
            "public_unreal_archives": [build_cesium_execution_audit.engine_root_discovery.unreal_public_root() / "engines" / "linux" / "Linux_Unreal_Engine_5.8.0.zip"],
        },
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.5.0f1",
                install_root=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.0f1"),
                editor_path=str(Path.cwd() / "tmp-public" / "Unity" / "6000.5.0f1" / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="test",
                quirks=(),
            )
        ],
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.cesium_example_workflow,
        "report_payload",
        lambda engine, native_target=None: {
            "compatibility_tracking": {
                "windows_version_matrix": [{"version": "4.6.3-stable"}],
                "linux_version_matrix": [{"version": "4.6.3-stable"}],
            }
            if engine == "godot"
            else {
                "pinned_editor": "6000.5.0f1",
                "example_project_version": "6000.6.0b2",
                "version_matrix": [{"version": "6000.6.0b2"}],
            },
        },
    )
    monkeypatch.setattr(
        build_cesium_execution_audit,
        "_latest_unity_example_failure_signals",
        lambda: [
            "Package Manager tried to write under the installed editor tree and hit EPERM.",
            "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
        ],
    )
    monkeypatch.setattr(build_cesium_execution_audit, "UNITY_LINUX_DOCKER_REPORT", unity_linux_docker_report)

    payload = build_cesium_execution_audit.build_payload()

    assert payload["schema"] == "cesium.execution_audit.v1"
    assert payload["overall_status"] == "partial"
    assert payload["evidence"]
    assert payload["gaps"]
    assert payload["readiness"]["unreal_linux_docker"] is True
    assert payload["readiness"]["unity_host"] is True
    assert payload["readiness"]["godot_windows"] is True
    assert payload["readiness"]["godot_linux"] is True
    assert any(Path(path).name == "Unreal" for path in payload["host"]["unreal_public_roots"])
    assert any(Path(path).name == "Godot" for path in payload["host"]["godot_public_roots"])
    assert any(Path(path).name == "Unity" for path in payload["host"]["unity_public_roots"])
    assert payload["unreal"]["versions"] == ["5.7", "5.8"]
    assert payload["unity"]["versions"] == ["6000.5.0f1"]
    assert payload["unity"]["proof_lane_version"] == "6000.5.0f1"
    assert payload["unity"]["example_project_version"] == "6000.6.0b2"
    assert payload["unreal"]["linux_platform_support_ready"] is True
    assert any(_portable_path(path).endswith("Public/Unreal/Engine/Platforms/Linux") for path in payload["unreal"]["linux_platform_support_search_roots"])
    assert any(_portable_path(path).endswith("Public/Unreal/Engine/Platforms/Linux") for path in payload["unreal"]["linux_platform_support_roots"])
    assert any(_portable_path(path).endswith("Public/Unreal/engines/linux/Linux_Unreal_Engine_5.8.0.zip") for path in payload["unreal"]["public_unreal_archives"])
    assert payload["unreal"]["selected_source"] == "unknown"
    assert payload["unity"]["latest_example_build_failure_signals"] == [
        "Package Manager tried to write under the installed editor tree and hit EPERM.",
        "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
    ]
    assert payload["unity"]["linux_docker_blocker_signals"] == [
        "The Linux container did not discover a Unity editor install, so this lane is still proof-of-commandability only.",
        "Unity Linux/Docker still has no installed editor versions inside the container.",
        "Unity Linux/Docker remains planned.",
    ]
    assert payload["related_packets"]["engine_matrix"]["status"] == "partial"
    assert payload["related_packets"]["unity_native_matrix"]["status"] == "partial"
    assert payload["related_packets"]["planned_routes"]["status"] == "present"


def test_cesium_execution_audit_uses_configured_unreal_and_godot_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    unreal_root = tmp_path / "MountedUnreal"
    godot_root = tmp_path / "MountedGodot"
    monkeypatch.setenv("FASTDIS_UNREAL_ROOTS", str(unreal_root))
    monkeypatch.setenv("FASTDIS_GODOT_ROOTS", str(godot_root))
    monkeypatch.setattr(build_cesium_execution_audit, "_available_docker", lambda: False)
    monkeypatch.setattr(
        build_cesium_execution_audit.engine_root_discovery,
        "public_engine_search_roots",
        build_cesium_execution_audit.engine_root_discovery.public_engine_search_roots,
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.unreal_linux_lane,
        "report_payload",
        lambda: {
            "version_matrix": [{"engine_version": "5.7"}],
            "build_status": "verified",
            "build_result": "succeeded",
            "build_log": "artifacts/reports/unreal_linux_docker/cesium_unreal_linux_build_5.7.log",
            "build_output_binary": "/ue/Engine/Binaries/Linux/UnrealGame-Linux-Shipping",
        },
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.unity_env,
        "discover_installs",
        lambda: [],
    )
    monkeypatch.setattr(
        build_cesium_execution_audit.cesium_example_workflow,
        "report_payload",
        lambda engine, native_target=None: {
            "compatibility_tracking": {
                "windows_version_matrix": [{"version": "4.7-stable"}],
                "linux_version_matrix": [{"version": "4.7-stable"}],
            }
            if engine == "godot"
            else {
                "pinned_editor": "6000.5.0f1",
                "example_project_version": "6000.6.0b2",
                "version_matrix": [{"version": "6000.6.0b2"}],
            },
        },
    )
    monkeypatch.setattr(build_cesium_execution_audit, "_latest_unity_example_failure_signals", lambda: [])
    monkeypatch.setattr(build_cesium_execution_audit, "_unity_linux_docker_blocker_signals", lambda: [])

    payload = build_cesium_execution_audit.build_payload()

    assert payload["host"]["unreal_public_roots"][1] == str(unreal_root)
    assert payload["host"]["godot_public_roots"][1] == str(godot_root)


def test_cesium_planned_routes_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        build_cesium_planned_routes,
        "_planned_bundle_payload",
        lambda: {
            "overall_status": "dry-run",
            "selected_lanes": ["cross-platform-planned"],
            "log_dir": _portable_path(Path.cwd() / "tmp" / "logs"),
            "lanes": [
                {
                    "id": "cross-platform-planned",
                    "status": "dry-run",
                    "lane_kind": "bundle",
                    "tasks": [
                        {
                            "id": "planned-unreal",
                            "status": "dry-run",
                            "commands": [
                                {"command": "cesium-unreal-linux-docker build-plan --engine-version 5.8"}
                            ],
                        }
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(
        build_cesium_planned_routes.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {
            "unreal": [Path.cwd() / "tmp-public" / "Unreal"],
            "unity": [Path.cwd() / "tmp-public" / "Unity"],
            "godot": [Path.cwd() / "tmp-public" / "Godot"],
        },
    )
    monkeypatch.setattr(build_cesium_planned_routes.build_cesium_engine_matrix, "build_payload", lambda: {"status": "partial"})
    monkeypatch.setattr(build_cesium_planned_routes.build_cesium_execution_audit, "build_payload", lambda: {"overall_status": "partial"})

    payload = build_cesium_planned_routes.build_payload()

    assert payload["schema"] == "cesium.planned_routes.v1"
    assert payload["status"] == "dry-run"
    assert payload["summary"]["bundle_lane_count"] == 1
    assert payload["summary"]["bundle_command_count"] == 1
    assert payload["summary"]["bundle_lane_ids"] == ["cross-platform-planned"]
    assert payload["evidence"][0]["surface"] == "planned-routes"
    assert payload["evidence"][0]["kind"] == "dry_run_bundle"
    assert payload["evidence"][1]["kind"] == "planned_command"
    assert "build-plan --engine-version 5.8" in payload["evidence"][1]["path"]
    assert payload["related_packets"]["engine_matrix"]["status"] == "partial"
    assert payload["related_packets"]["execution_audit"]["status"] == "partial"
    assert payload["related_packets"]["compatibility_packet"]["path"] == "artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json"
    assert any(Path(path).name == "Unreal" for path in payload["host"]["unreal_public_roots"])
    assert any(Path(path).name == "Unity" for path in payload["host"]["unity_public_roots"])
    assert any(Path(path).name == "Godot" for path in payload["host"]["godot_public_roots"])


def test_cesium_execution_audit_latest_unity_failure_signals_falls_back_to_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report_dir = tmp_path / "unity_example_build"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "unity_example_build_6000_3_19f1_windows.json"
    log_path = report_dir / "unity_example_build_6000_3_19f1_windows.log"
    json_path.write_text(
        json.dumps(
            {
                "failure_signals": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    log_path.write_text(
        "Failed to resolve packages: EPERM: operation not permitted\n"
        "Unable to retrieve BIOS serial number. Exception: Access denied\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_cesium_execution_audit, "UNITY_EXAMPLE_BUILD_DIR", report_dir)

    assert build_cesium_execution_audit._latest_unity_example_failure_signals() == [
        "Package Manager tried to write under the installed editor tree and hit EPERM.",
        "Unity licensing still hits BIOS lookup denial and mutex contention on this host.",
    ]


def test_cesium_compatibility_packet_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_cesium_compatibility_packet.build_cesium_engine_matrix, "build_payload", lambda: {
        "status": "partial",
        "gaps": ["unity gap"],
        "evidence": [{"surface": "matrix", "kind": "doc", "path": "docs/a.md"}],
        "lane_count": 1,
        "summary": {"verified_lane_count": 1, "planned_lane_count": 0},
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_unity_native_matrix, "build_payload", lambda: {
        "status": "partial",
        "gaps": ["unity native gap"],
        "evidence": [{"surface": "unity-native", "kind": "native_matrix", "path": "artifacts/reports/unity_native_matrix/unity_native_matrix.json"}],
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_cesium_execution_audit, "build_payload", lambda: {
        "overall_status": "partial",
        "gaps": ["audit gap"],
        "evidence": [{"surface": "audit", "kind": "doc", "path": "docs/b.md"}],
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_cesium_planned_routes, "build_payload", lambda: {
        "status": "dry-run",
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_cesium_fork_workpack, "build_payload", lambda: {
        "status": "partial",
        "evidence": [{"surface": "fork", "kind": "doc", "path": "docs/c.md"}],
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_cesium_visual_proof, "build_payload", lambda: {
        "status": "commandable",
        "targets": [{"engine": "unreal", "native_target": "windows", "architecture": "x86_64", "capture_root": "artifacts/reports/cesium_visual_proof/unreal/windows/x86_64", "proof_runner": {"normalized_capture_root": "artifacts/reports/cesium_visual_proof/unreal/windows/x86_64"}}],
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_windows_visual_proof, "build_payload", lambda: {
        "status": "commandable",
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.compare_cesium_visual_proof, "build_payload", lambda scan_roots=None, strict_missing=True: {
        "status": "pass",
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.validate_visual_proof_roots, "build_payload", lambda scan_roots=None: {
        "status": "pass",
        "summary": {"missing_engines": [], "present_engines": ["unreal", "unity", "godot"], "root_count": 1},
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.validate_visual_proof_audit, "build_payload", lambda scan_roots=None: {
        "status": "pass",
        "summary": {"root_engine_coverage_status": "pass"},
    })
    monkeypatch.setattr(build_cesium_compatibility_packet.build_unreal_visual_proof, "build_payload", lambda: {
        "status": "commandable",
    })

    payload = build_cesium_compatibility_packet.build_payload()

    assert payload["schema"] == "cesium.compatibility_packet.v1"
    assert payload["status"] == "partial"
    assert payload["summary"]["evidence_count"] == 10
    assert payload["summary"]["planned_routes_status"] == "dry-run"
    assert payload["gaps"] == ["unity gap", "unity native gap", "audit gap"]
    assert payload["reports"]["engine_matrix"]["status"] == "partial"
    assert payload["reports"]["unity_native_matrix"]["status"] == "partial"
    assert payload["reports"]["execution_audit"]["status"] == "partial"
    assert payload["related_packets"]["planned_routes"]["status"] == "dry-run"
    assert payload["related_packets"]["windows_visual_proof"]["status"] == "commandable"
    assert payload["related_packets"]["windows_visual_proof_run"]["path"].endswith("windows_visual_proof_run/windows_visual_proof_run.json")
    assert payload["related_packets"]["unreal_visual_proof"]["status"] == "commandable"
    assert payload["related_packets"]["visual_proof"]["status"] == "commandable"


def test_cesium_execution_audit_cli_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_command(command: str, argv: list[str]) -> int:
        calls.append((command, argv))
        return 7

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["execution-audit"])

    assert exit_code == 7
    assert calls[-1][0] == "execution-audit"
    assert calls[-1][1] == []

    exit_code = cesium_cli.main(["compatibility-packet"])
    assert exit_code == 7
    assert calls[-1][0] == "compatibility-packet"
    assert calls[-1][1] == []

    exit_code = cesium_cli.main(["planned-routes"])
    assert exit_code == 7
    assert calls[-1][0] == "planned-routes"
    assert calls[-1][1] == []

    exit_code = cesium_cli.main(["cross-platform-fix-notes"])
    assert exit_code == 7
    assert calls[-1][0] == "cross-platform-fix-notes"
    assert calls[-1][1] == []


def test_cesium_cross_platform_fix_notes_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_cesium_cross_platform_fix_notes.build_cesium_engine_matrix, "build_payload", lambda: {
        "status": "partial",
        "summary": {"version_coverage": {"unreal": ["5.8"]}, "verified_lane_count": 5, "planned_lane_count": 3},
        "related_packets": {"unity_native_matrix": {"status": "partial"}},
    })
    monkeypatch.setattr(build_cesium_cross_platform_fix_notes.build_cesium_execution_audit, "build_payload", lambda: {
        "overall_status": "partial",
    })
    monkeypatch.setattr(build_cesium_cross_platform_fix_notes.build_cesium_planned_routes, "build_payload", lambda: {
        "status": "dry-run",
    })
    monkeypatch.setattr(
        build_cesium_cross_platform_fix_notes.proof_runs,
        "next_proof_runs",
        lambda: [{"surface": "godot-mac", "command": "cesium-plugin-lanes --dry-run --lanes godot-host-mac", "capture_focus": ["macOS remains planned."]}],
    )

    payload = build_cesium_cross_platform_fix_notes.build_payload()

    assert payload["schema"] == "cesium.cross_platform_fix_notes.v1"
    assert payload["status"] == "partial"
    assert payload["summary"]["matrix_status"] == "partial"
    assert payload["summary"]["unity_native_status"] == "partial"
    assert payload["summary"]["audit_status"] == "partial"
    assert payload["summary"]["planned_routes_status"] == "dry-run"
    assert payload["version_coverage"][0]["engine"] == "Unreal"
    assert payload["evidence_map"][0]["engine"] == "Unreal"
    assert payload["commandable_followups"][-1] == "cesium-planned-routes"
    assert payload["summary"]["next_proof_runs"][0]["surface"] == "godot-mac"
    assert payload["related_packets"]["engine_matrix"]["status"] == "partial"
    assert payload["related_packets"]["execution_audit"]["status"] == "partial"
    assert payload["related_packets"]["planned_routes"]["status"] == "dry-run"


def test_godot_public_root_discovery_matches_win64_and_linux_layouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "Godot"
    windows_root = root / "engines" / "windows"
    linux_root = root / "engines" / "linux"
    win_install = windows_root / "Godot_v4.7-stable_win64.exe"
    linux_install = linux_root / "Godot_v4.7-stable_linux.x86_64"
    (win_install).mkdir(parents=True, exist_ok=True)
    (linux_install).mkdir(parents=True, exist_ok=True)
    (win_install / "Godot_v4.7-stable_win64.exe").write_text("stub\n", encoding="utf-8")
    (win_install / "Godot_v4.7-stable_win64_console.exe").write_text("stub\n", encoding="utf-8")
    (linux_install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(engine_root_discovery, "PUBLIC_GODOT_ROOT", root)

    windows_versions = engine_root_discovery.discover_godot_windows_versions()
    linux_versions = engine_root_discovery.discover_godot_linux_versions()

    assert [row["version"] for row in windows_versions] == ["4.7-stable"]
    assert windows_versions[0]["console_executable"].name == "Godot_v4.7-stable_win64_console.exe"
    assert [row["version"] for row in linux_versions] == ["4.7-stable"]
    assert linux_versions[0]["console_executable"] == linux_versions[0]["executable"]


def test_godot_public_root_discovery_includes_configured_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "MountedGodot"
    linux_root = root / "engines" / "linux"
    install = linux_root / "Godot_v4.7-stable_linux.x86_64"
    install.mkdir(parents=True, exist_ok=True)
    (install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(engine_root_discovery, "PUBLIC_GODOT_ROOT", tmp_path / "NoGodot")
    monkeypatch.setenv("FASTDIS_GODOT_ROOTS", str(root))

    versions = engine_root_discovery.discover_godot_linux_versions()

    assert [row["version"] for row in versions] == ["4.7-stable"]


def test_godot_public_root_discovery_includes_direct_configured_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "MountedGodot"
    install = root / "Godot_v4.7-stable_linux.x86_64"
    install.mkdir(parents=True, exist_ok=True)
    (install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(engine_root_discovery, "PUBLIC_GODOT_ROOT", tmp_path / "NoGodot")
    monkeypatch.setenv("FASTDIS_GODOT_ROOTS", str(root))

    versions = engine_root_discovery.discover_godot_linux_versions()

    assert [row["version"] for row in versions] == ["4.7-stable"]
    assert versions[0]["root"] == install


def test_godot_linux_docker_prefers_discovered_install_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "MountedGodot"
    windows_root = root / "engines" / "windows"
    linux_root = root / "engines" / "linux"
    windows_install = windows_root / "Godot_v4.7-stable_win64.exe"
    linux_install = linux_root / "Godot_v4.7-stable_linux.x86_64"
    windows_install.mkdir(parents=True, exist_ok=True)
    linux_install.mkdir(parents=True, exist_ok=True)
    (windows_install / "Godot_v4.7-stable_win64.exe").write_text("stub\n", encoding="utf-8")
    (windows_install / "Godot_v4.7-stable_win64_console.exe").write_text("stub\n", encoding="utf-8")
    (linux_install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [root], "unreal": [], "unity": []},
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_windows_versions",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "windows",
                "root": windows_install,
                "executable": windows_install / "Godot_v4.7-stable_win64.exe",
                "console_executable": windows_install / "Godot_v4.7-stable_win64_console.exe",
            }
        ],
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_linux_versions",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "linux",
                "root": linux_install,
                "executable": linux_install / "Godot_v4.7-stable_linux.x86_64",
                "console_executable": linux_install / "Godot_v4.7-stable_linux.x86_64",
            }
        ],
    )

    roots = godot_linux_docker._host_godot_roots()

    assert roots == [windows_install, linux_install]


def test_public_engine_search_roots_include_configured_unreal_and_godot_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    unreal_root = tmp_path / "MountedUnreal"
    godot_root = tmp_path / "MountedGodot"
    monkeypatch.setenv("FASTDIS_UNREAL_ROOTS", str(unreal_root))
    monkeypatch.setenv("FASTDIS_GODOT_ROOTS", str(godot_root))

    roots = engine_root_discovery.public_engine_search_roots()

    assert roots["unreal"][0] == engine_root_discovery.PUBLIC_UNREAL_ROOT
    assert unreal_root in roots["unreal"]
    assert roots["godot"][0] == engine_root_discovery.PUBLIC_GODOT_ROOT
    assert godot_root in roots["godot"]


def test_discover_godot_macos_versions_scans_app_bundles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mac_root = tmp_path / "Applications"
    bundle = mac_root / "Godot_v4.7-stable_macos.app"
    executable_dir = bundle / "Contents" / "MacOS"
    executable_dir.mkdir(parents=True, exist_ok=True)
    (executable_dir / "Godot").write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(engine_root_discovery, "_macos_godot_roots", lambda: [mac_root])
    versions = engine_root_discovery.discover_godot_macos_versions()

    assert [row["version"] for row in versions] == ["4.7-stable"]
    assert versions[0]["platform"] == "mac"
    assert versions[0]["root"] == bundle
    assert versions[0]["executable"] == executable_dir / "Godot"


def test_unreal_linux_lane_report_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    public_unreal_root = tmp_path / "Public" / "Unreal"
    public_unreal_root.mkdir(parents=True, exist_ok=True)
    platform_support_root = public_unreal_root / "Engine" / "Platforms" / "Linux"
    platform_support_root.mkdir(parents=True, exist_ok=True)
    archive = public_unreal_root / "engines" / "linux" / "Linux_Unreal_Engine_5.8.0.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(
        unreal_linux_lane,
        "public_engine_search_roots",
        lambda: {"unreal": [public_unreal_root], "godot": [], "unity": []},
    )
    monkeypatch.setattr(unreal_linux_lane, "discover_unreal_linux_archives", lambda: [archive])

    report = unreal_linux_lane.report_payload()

    assert report["schema"] == "cesium.unreal_linux_lane.v1"
    assert report["status"] == "ok"
    assert report["checks"]
    assert any(check["name"] == "linux_platform_declared" and check["status"] == "ok" for check in report["checks"])
    assert any(check["name"] == "runtime_linux_branch" and check["status"] == "ok" for check in report["checks"])
    assert any(check["name"] == "editor_linux_branch" and check["status"] == "ok" for check in report["checks"])
    assert report["build_commands"]
    assert report["next_steps"]
    assert _portable_path(report["public_search_roots"][0]) == _portable_path(public_unreal_root)
    assert [_portable_path(path) for path in report["linux_platform_support_search_roots"]] == [
        _portable_path(platform_support_root),
    ]
    assert "linux_platform_support_roots" in report
    assert "linux_platform_support_ready" in report


def test_unity_license_probe_classifies_blocked_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install = unity_env.UnityInstall(
        version="6000.5.2f1",
        install_root=str(tmp_path / "Unity"),
        editor_path=str(tmp_path / "Unity" / "Unity.exe"),
        editor_app_path=None,
        source="test",
        quirks=(),
    )
    monkeypatch.setattr(unity_env.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        unity_env.subprocess,
        "run",
        lambda *args, **kwargs: type("Completed", (), {"stdout": "No valid Unity Editor license found", "stderr": "", "returncode": 1})(),
    )
    result = unity_env.probe_unity_license(install, log_path=tmp_path / "license.log")
    assert result["status"] == "blocked"
    assert result["signals"] == ["no valid unity editor license"]


def test_unity_hub_bootstrap_leaves_successful_process_running(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hub = tmp_path / "Unity Hub.exe"
    hub.write_text("stub\n", encoding="utf-8")
    monkeypatch.setattr(unity_env.platform, "system", lambda: "Windows")
    monkeypatch.setattr(unity_env, "unity_hub_candidates", lambda: [hub])

    class RunningProcess:
        pid = 42

        def poll(self) -> None:
            return None

    monkeypatch.setattr(unity_env.subprocess, "Popen", lambda *args, **kwargs: RunningProcess())
    monkeypatch.setattr(unity_env.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(unity_env.time, "monotonic", iter([0.0, 0.0, 1.0]).__next__)
    result = unity_env.ensure_unity_hub_open(settle_seconds=0.5)
    assert result["status"] == "opened"
    assert result["left_running"] is True
    assert result["pid"] == 42


def test_unreal_linux_lane_supports_selected_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report_dir = tmp_path / "unreal_linux_docker"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "cesium_unreal_linux_build_5.7.log").write_text("Result: Succeeded\nExitCode=0\n", encoding="utf-8")
    (report_dir / "cesium_unreal_linux_build_5.8.log").write_text("Result: Succeeded\nExitCode=0\n", encoding="utf-8")
    monkeypatch.setattr(unreal_linux_lane, "REPORT_DIR", report_dir)

    report = unreal_linux_lane.report_payload(engine_version="5.8")

    assert report["selected_version"] == "5.8"
    assert report["selected_version_details"]["engine_version"] == "5.8"
    assert report["selected_version_details"]["lane_role"] == "forward verification"
    assert report["build_log"].endswith("cesium_unreal_linux_build_5.8.log")


def test_unreal_linux_docker_build_plan_shapes() -> None:
    plan = unreal_linux_docker._container_lane_command("5.8")

    assert plan == ["python3", "-m", "extensions.cesium.tools.unreal_linux_lane", "report", "--engine-version", "5.8"]


def test_unreal_linux_docker_profile_files_and_defaults() -> None:
    profile_57 = ROOT / "tools" / "unreal_linux_profiles" / "ubuntu_24_04_ue57.env"
    profile_58 = ROOT / "tools" / "unreal_linux_profiles" / "ubuntu_24_04_ue58.env"

    values_57 = unreal_linux_docker.parse_env_file(profile_57)
    values_58 = unreal_linux_docker.parse_env_file(profile_58)

    assert values_57["UE_VERSION_LABEL"] == "ue5.7.4-linux"
    assert values_58["UE_VERSION_LABEL"] == "ue5.8.0-linux"
    assert values_57["UE_LINUX_IMAGE"] == "cesium-linux-proof:ubuntu24.04"
    assert values_58["DOCKER_PLATFORM"] == "linux/amd64"


def test_unreal_linux_docker_log_path_and_container_name() -> None:
    assert unreal_linux_docker.resolved_container_name("5.8") == f"{unreal_linux_docker.DEFAULT_CONTAINER_NAME_PREFIX}-5.8-{os.getpid()}"
    assert unreal_linux_docker._docker_log_path("build", "5.8").name == "cesium_unreal_linux_build_5.8.log"


def test_unreal_linux_docker_detects_missing_linux_prereqs(tmp_path: Path) -> None:
    ue_root = tmp_path / "UE_5.8"
    (ue_root / "Engine" / "Build" / "BatchFiles").mkdir(parents=True, exist_ok=True)

    assert unreal_linux_docker._has_linux_build_prereqs(ue_root) is False


def test_unreal_linux_docker_detects_missing_linux_platform_support(tmp_path: Path) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Build/BatchFiles/Linux/SetupEnvironment.sh", "#!/bin/bash\n")
        zf.writestr("Engine/Build/Build.version", "{}\n")

    assert unreal_linux_docker._archive_has_linux_platform_support(archive) is False


def test_unreal_linux_docker_accepts_platform_support_in_engine_platforms_layout(tmp_path: Path) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Platforms/Linux/Config/DataDrivenPlatformInfo.ini", "[/Script]")
        zf.writestr("Engine/Platforms/Linux/Config/SDK.json", "{}")

    assert unreal_linux_docker._archive_has_linux_platform_support(archive) is True


def test_unreal_linux_docker_resolves_explicit_linux_platform_support_root(tmp_path: Path) -> None:
    support_root = tmp_path / "LinuxPlatform"
    support_root.mkdir(parents=True, exist_ok=True)

    assert unreal_linux_docker._resolve_linux_platform_support_root(support_root) == support_root


def test_unreal_linux_docker_build_passes_linux_platform_support_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Build/BatchFiles/Linux/SetupEnvironment.sh", "#!/bin/bash\n")
        zf.writestr("Engine/Build/Build.version", "{}\n")

    support_root = tmp_path / "LinuxPlatform"
    support_root.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_roots", lambda: [])
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_archives", lambda: [archive])
    monkeypatch.setattr(unreal_linux_docker, "_resolve_plugin_root", lambda explicit_root=None: unreal_linux_docker.DEFAULT_PLUGIN_ROOT)

    def fake_run_docker_with_archive(
        image,
        archive_arg,
        command,
        *,
        linux_platform_support_root=None,
        plugin_root=None,
        **kwargs,
    ):
        captured["image"] = image
        captured["archive"] = archive_arg
        captured["command"] = command
        captured["linux_platform_support_root"] = linux_platform_support_root
        captured["plugin_root"] = plugin_root
        captured["kwargs"] = kwargs
        return 13

    monkeypatch.setattr(unreal_linux_docker, "_run_docker_with_archive", fake_run_docker_with_archive)

    exit_code = unreal_linux_docker.main([
        "build",
        "--engine-version",
        "5.8",
        "--linux-platform-support-root",
        str(support_root),
    ])

    assert exit_code == 13
    assert captured["archive"] == archive
    assert captured["linux_platform_support_root"] == support_root
    assert captured["plugin_root"] == unreal_linux_docker.DEFAULT_PLUGIN_ROOT


def test_unreal_linux_docker_report_does_not_forward_ue_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Build/BatchFiles/Linux/SetupEnvironment.sh", "#!/bin/bash\n")
        zf.writestr("Engine/Build/Build.version", "{}\n")

    captured: dict[str, object] = {}

    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_roots", lambda: [])
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_archives", lambda: [archive])
    monkeypatch.setattr(unreal_linux_docker, "_resolve_plugin_root", lambda explicit_root=None: unreal_linux_docker.DEFAULT_PLUGIN_ROOT)
    monkeypatch.setattr(
        unreal_linux_docker,
        "_resolve_ue_root_with_source",
        lambda explicit_root, engine_version=None: (None, "staged zip from public Unreal search roots", archive),
    )
    monkeypatch.setattr(unreal_linux_docker, "_archive_has_linux_platform_support", lambda _archive: True)

    def fake_run_docker_with_archive(
        image,
        archive_arg,
        command,
        *,
        linux_platform_support_root=None,
        plugin_root=None,
        **kwargs,
    ):
        captured["image"] = image
        captured["archive"] = archive_arg
        captured["command"] = command
        captured["linux_platform_support_root"] = linux_platform_support_root
        captured["plugin_root"] = plugin_root
        captured["kwargs"] = kwargs
        return 17

    monkeypatch.setattr(unreal_linux_docker, "_run_docker_with_archive", fake_run_docker_with_archive)

    exit_code = unreal_linux_docker.main(["report", "--engine-version", "5.8"])

    assert exit_code == 17
    assert captured["archive"] == archive
    assert "--ue-root" not in captured["command"]
    assert captured["linux_platform_support_root"] is None
    assert captured["plugin_root"] == unreal_linux_docker.DEFAULT_PLUGIN_ROOT


def test_unreal_linux_docker_report_surfaces_discovered_support_roots_and_archives(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    support_root = tmp_path / "LinuxPlatform"
    support_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Build/BatchFiles/Linux/SetupEnvironment.sh", "#!/bin/bash\n")
        zf.writestr("Engine/Build/Build.version", "{}\n")

    captured: dict[str, object] = {}
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_roots", lambda: [])
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_archives", lambda: [archive])
    monkeypatch.setattr(unreal_linux_docker, "_resolve_plugin_root", lambda explicit_root=None: unreal_linux_docker.DEFAULT_PLUGIN_ROOT)
    monkeypatch.setattr(unreal_linux_docker, "_discover_linux_platform_support_roots", lambda: [support_root])
    monkeypatch.setattr(
        unreal_linux_docker,
        "_resolve_ue_root_with_source",
        lambda explicit_root, engine_version=None: (None, "staged zip from public Unreal search roots", archive),
    )
    monkeypatch.setattr(unreal_linux_docker, "_archive_has_linux_platform_support", lambda _archive: True)

    def fake_run_docker_with_archive(
        image,
        archive_arg,
        command,
        *,
        linux_platform_support_root=None,
        plugin_root=None,
        **kwargs,
    ):
        captured["image"] = image
        captured["archive"] = archive_arg
        captured["command"] = command
        captured["linux_platform_support_root"] = linux_platform_support_root
        captured["plugin_root"] = plugin_root
        captured["kwargs"] = kwargs
        return 17

    monkeypatch.setattr(unreal_linux_docker, "_run_docker_with_archive", fake_run_docker_with_archive)

    exit_code = unreal_linux_docker.main(["report", "--engine-version", "5.8"])

    assert exit_code == 17
    out = capsys.readouterr().out
    assert "selected source: staged zip from public Unreal search roots" in out
    assert "discovered linux platform support roots:" in out
    assert str(support_root) in out
    assert "public Unreal archives:" in out
    assert str(archive) in out
    assert captured["archive"] == archive
    assert captured["linux_platform_support_root"] is None


def test_unreal_linux_docker_prefers_repo_plugin_root_with_include_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "cesium-unreal"
    (source_root / "Source").mkdir(parents=True, exist_ok=True)
    (source_root / "Source" / "ThirdParty" / "include").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(unreal_linux_docker, "DEFAULT_PLUGIN_ROOT", source_root)

    resolved = unreal_linux_docker._resolve_plugin_root()

    assert resolved == source_root.resolve()


def test_unreal_linux_docker_does_not_search_outside_repo_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "cesium-unreal"
    source_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(unreal_linux_docker, "DEFAULT_PLUGIN_ROOT", source_root)

    assert unreal_linux_docker._resolve_plugin_root() == source_root.resolve()


def test_unreal_linux_docker_build_plan_shows_linux_platform_support_root(capsys, tmp_path: Path) -> None:
    support_root = tmp_path / "LinuxPlatform"
    support_root.mkdir(parents=True, exist_ok=True)

    exit_code = unreal_linux_docker.main([
        "build-plan",
        "--linux-platform-support-root",
        str(support_root),
    ])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert f"linux platform support root: {support_root}" in out


def test_unreal_linux_docker_resolves_latest_discovered_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    low = tmp_path / "UE_5.7"
    high = tmp_path / "UE_5.8"
    monkeypatch.setattr(
        unreal_linux_docker,
        "discover_unreal_linux_roots",
        lambda: [low, high],
    )

    assert unreal_linux_docker._resolve_ue_root(None) == high


def test_unreal_linux_docker_stages_archive_when_no_root_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engine/Build/BatchFiles/Linux/SetupEnvironment.sh", "#!/bin/bash\n")
        zf.writestr("Engine/Binaries/Linux/UnrealEditor", "binary\n")
        zf.writestr("Engine/Build/Build.version", "{}\n")

    stage_root = tmp_path / "stage"
    monkeypatch.setattr(unreal_linux_docker, "DEFAULT_STAGE_ROOT", stage_root)
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_roots", lambda: [])
    monkeypatch.setattr(unreal_linux_docker, "discover_unreal_linux_archives", lambda: [archive])

    resolved = unreal_linux_docker._resolve_or_stage_ue_root(None, engine_version="5.8")

    assert resolved == stage_root / "ue5.8-linux"
    assert (resolved / "Engine" / "Build" / "BatchFiles" / "Linux" / "SetupEnvironment.sh").is_file()
    assert (resolved / "Engine" / "Binaries" / "Linux" / "UnrealEditor").is_file()
    assert (resolved / "Engine" / "Build" / "Build.version").is_file()


def test_unreal_linux_docker_stages_archive_on_host_before_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = tmp_path / "Linux_Unreal_Engine_5.8.0.zip"
    support_root = tmp_path / "LinuxPlatform"
    support_root.mkdir(parents=True, exist_ok=True)
    (support_root / "DataDrivenPlatformInfo.ini").write_text("[Linux]\n", encoding="utf-8")
    (support_root / "Linux_SDK.json").write_text("{}\n", encoding="utf-8")
    staged_root = tmp_path / "stage" / "ue5.8-linux"
    (staged_root / "Engine" / "Build" / "BatchFiles" / "Linux").mkdir(parents=True, exist_ok=True)
    (staged_root / "Engine" / "Build" / "BatchFiles" / "Linux" / "SetupEnvironment.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_stage_unreal_linux_archive(archive_arg, *, engine_version=None):
        captured["archive"] = archive_arg
        captured["engine_version"] = engine_version
        return staged_root

    monkeypatch.setattr(unreal_linux_docker, "_stage_unreal_linux_archive", fake_stage_unreal_linux_archive)
    def fake_run_logging(command, **kwargs):
        captured["command"] = command
        captured["logging_kwargs"] = kwargs
        return 0, ["line"], [], "line\n"

    monkeypatch.setattr(unreal_linux_docker, "_run_command_with_logging", fake_run_logging)

    exit_code = unreal_linux_docker._run_docker_with_archive(
        "cesium-linux-proof:ubuntu24.04",
        archive,
        [
            "/tmp/ue/Engine/Build/BatchFiles/RunUAT.sh",
            "BuildPlugin",
            "-Plugin=/workspace/external/cesium/cesium-unreal/CesiumForUnreal.uplugin",
        ],
        linux_platform_support_root=support_root,
        plugin_root=unreal_linux_docker.DEFAULT_PLUGIN_ROOT,
        engine_version="5.8",
    )

    assert exit_code == 0
    assert captured["archive"] == archive
    assert captured["engine_version"] == "5.8.0"
    assert (staged_root / "Engine" / "Config" / "Linux" / "DataDrivenPlatformInfo.ini").is_file()
    assert (staged_root / "Engine" / "Config" / "Linux" / "Linux_SDK.json").is_file()
    command = captured["command"]
    assert any(str(staged_root) in str(arg) and ":/ue" in str(arg) for arg in command)
    assert "/ue/Engine/Build/BatchFiles/RunUAT.sh" in str(command)
    assert "/tmp/ue/Engine/Build/BatchFiles/RunUAT.sh" not in str(command)


def test_unreal_linux_docker_labels_manual_root_as_manual(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ue_root = tmp_path / "UE_5.8"
    (ue_root / "Engine" / "Build" / "BatchFiles" / "Linux").mkdir(parents=True, exist_ok=True)
    (ue_root / "Engine" / "Build" / "BatchFiles" / "Linux" / "SetupEnvironment.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (ue_root / "Engine" / "Binaries" / "Linux").mkdir(parents=True, exist_ok=True)
    (ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor").write_text("binary\n", encoding="utf-8")
    (ue_root / "Engine" / "Build").mkdir(parents=True, exist_ok=True)
    (ue_root / "Engine" / "Build" / "Build.version").write_text("{}\n", encoding="utf-8")

    resolved, source, archive = unreal_linux_docker._resolve_ue_root_with_source(ue_root, engine_version="5.8")

    assert resolved == ue_root
    assert source == "manual --ue-root"
    assert archive is None


def test_godot_linux_docker_builds_expected_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_godot_root = tmp_path / "Godot"
    host_godot_linux_root = host_godot_root / "engines" / "linux"
    install = host_godot_linux_root / "Godot_v4.7-stable_linux.x86_64"
    install.mkdir(parents=True, exist_ok=True)
    (install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    (install / "Godot_v4.7-stable_linux_console.exe").write_text("stub\n", encoding="utf-8")
    args = godot_linux_docker.parse_args(
        [
            "--native-target",
            "linux",
            "--json-out",
            str(tmp_path / "godot.json"),
            "--md-out",
            str(tmp_path / "godot.md"),
        ]
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [host_godot_root], "unreal": [], "unity": []},
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_windows_versions",
        lambda: [],
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_linux_versions",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "linux",
                "root": install,
                "executable": install / "Godot_v4.7-stable_linux.x86_64",
                "console_executable": install / "Godot_v4.7-stable_linux.x86_64",
            }
        ],
    )

    command = godot_linux_docker.build_docker_command(args)

    assert command[0:4] == ["docker", "run", "--rm", "--name"]
    assert "--platform" in command
    assert "cesium-godot-linux-proof-linux" in command[4]
    joined = " ".join(command)
    assert "extensions.cesium.tools.cesium_example_workflow" in joined
    assert "--native-target" in joined
    assert "linux" in joined
    assert str(install) in joined
    assert "FASTDIS_GODOT_ROOTS" in joined


def test_godot_linux_docker_dry_run_writes_reports(tmp_path: Path) -> None:
    json_out = tmp_path / "godot.json"
    md_out = tmp_path / "godot.md"
    args = godot_linux_docker.parse_args(
        [
            "--dry-run",
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    exit_code = godot_linux_docker.main(
        [
            "--dry-run",
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    assert exit_code == 0
    assert json_out.is_file()
    assert md_out.is_file()
    content = json_out.read_text(encoding="utf-8")
    assert "\"status\": \"dry-run\"" in content
    assert "\"scratch_home\": \"/tmp/cesium_godot/home\"" in content


def test_godot_example_build_dry_run_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "CesiumVanillaExample"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    (project_dir / "export_presets.cfg").write_text("[preset.0]\nname=\"Windows Desktop\"\n", encoding="utf-8")

    monkeypatch.setattr(
        build_godot_example,
        "_discover_installs",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "windows",
                "root": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.7-stable_win64.exe",
                "executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.7-stable_win64.exe" / "Godot_v4.7-stable_win64.exe",
                "console_executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.7-stable_win64.exe" / "Godot_v4.7-stable_win64_console.exe",
            }
        ],
    )
    monkeypatch.setattr(
        build_godot_example.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [tmp_path / "Public" / "Godot", tmp_path / "DriveD" / "Godot"], "unreal": [], "unity": []},
    )
    template_root = tmp_path / "GodotTemplates" / "4.7-stable"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "windows_debug_x86_64.exe").write_text("template\n", encoding="utf-8")
    (template_root / "windows_release_x86_64.exe").write_text("template\n", encoding="utf-8")
    monkeypatch.setattr(build_godot_example, "_template_root", lambda godot_version, runtime_root: template_root)

    payload = build_godot_example.run_build(
        build_godot_example.parse_args(
            [
                "--dry-run",
                "--build-target",
                "windows",
                "--godot-version",
                "4.7",
                "--project-dir",
                str(project_dir),
                "--out-dir",
                str(tmp_path / "report"),
            ]
        )
    )

    assert payload["schema"] == "cesium.godot_example_build.v1"
    assert payload["status"] == "dry-run"
    assert payload["build_target"] == "windows"
    assert "--export-release" in " ".join(payload["command"])
    assert "Windows Desktop" in " ".join(payload["command"])
    assert payload["output_path"].endswith(r"build\godot\CesiumVanillaExample\windows\CesiumVanillaExample.exe")
    assert payload["public_search_roots"] == [_portable_path(tmp_path / "Public" / "Godot"), _portable_path(tmp_path / "DriveD" / "Godot")]
    assert payload["missing_template_paths"] == []


def test_godot_example_build_dry_run_mac_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "CesiumVanillaExample"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    (project_dir / "export_presets.cfg").write_text("[preset.0]\nname=\"Mac Desktop\"\n", encoding="utf-8")

    monkeypatch.setattr(
        build_godot_example,
        "_discover_installs",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "mac",
                "root": tmp_path / "Godot" / "engines" / "mac" / "Godot_v4.7-stable_macos.app",
                "executable": tmp_path / "Godot" / "engines" / "mac" / "Godot_v4.7-stable_macos.app" / "Contents" / "MacOS" / "Godot",
                "console_executable": tmp_path / "Godot" / "engines" / "mac" / "Godot_v4.7-stable_macos.app" / "Contents" / "MacOS" / "Godot",
            }
        ],
    )
    monkeypatch.setattr(
        build_godot_example.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [Path("/Applications"), Path.home() / "Applications"], "unreal": [], "unity": []},
    )
    template_root = tmp_path / "GodotTemplates" / "4.7-stable"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "macos_debug.zip").write_text("template\n", encoding="utf-8")
    (template_root / "macos_release.zip").write_text("template\n", encoding="utf-8")
    monkeypatch.setattr(build_godot_example, "_template_root", lambda godot_version, runtime_root: template_root)

    payload = build_godot_example.run_build(
        build_godot_example.parse_args(
            [
                "--dry-run",
                "--build-target",
                "mac",
                "--godot-version",
                "4.7",
                "--project-dir",
                str(project_dir),
                "--out-dir",
                str(tmp_path / "report"),
            ]
        )
    )

    assert payload["schema"] == "cesium.godot_example_build.v1"
    assert payload["status"] == "dry-run"
    assert payload["build_target"] == "mac"
    assert "Mac Desktop" in " ".join(payload["command"])
    assert payload["output_path"].endswith(r"build\godot\CesiumVanillaExample\mac\CesiumVanillaExample.app")
    assert payload["missing_template_paths"] == []


def test_godot_example_build_dry_run_uses_selector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "CesiumVanillaExample"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    (project_dir / "export_presets.cfg").write_text("[preset.0]\nname=\"Windows Desktop\"\n", encoding="utf-8")

    monkeypatch.setattr(
        build_godot_example,
        "_discover_installs",
        lambda: [
            {
                "version": "4.6.3-stable",
                "platform": "windows",
                "root": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe",
                "executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe" / "Godot_v4.6.3-stable_win64.exe",
                "console_executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.6.3-stable_win64.exe" / "Godot_v4.6.3-stable_win64_console.exe",
            },
            {
                "version": "4.8-dev1",
                "platform": "windows",
                "root": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe",
                "executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe" / "Godot_v4.8-dev1_win64.exe",
                "console_executable": tmp_path / "Godot" / "engines" / "windows" / "Godot_v4.8-dev1_win64.exe" / "Godot_v4.8-dev1_win64_console.exe",
            },
        ],
    )
    monkeypatch.setattr(
        build_godot_example.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [Path.cwd() / "tmp-public" / "Godot"], "unreal": [], "unity": []},
    )
    template_root = tmp_path / "GodotTemplates" / "4.8-dev1"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "windows_debug_x86_64.exe").write_text("template\n", encoding="utf-8")
    (template_root / "windows_release_x86_64.exe").write_text("template\n", encoding="utf-8")
    monkeypatch.setattr(build_godot_example, "_template_root", lambda godot_version, runtime_root: template_root)

    payload = build_godot_example.run_build(
        build_godot_example.parse_args(
            [
                "--dry-run",
                "--build-target",
                "windows",
                "--godot-selector",
                "4.7-stable..4.8-dev1",
                "--project-dir",
                str(project_dir),
                "--out-dir",
                str(tmp_path / "report"),
            ]
        )
    )

    assert payload["godot_version"] == "4.8-dev1"
    assert payload["requested_version_source"] == "selector"


def test_godot_bootstrap_builds_expected_urls() -> None:
    editor_url = godot_bootstrap.build_editor_download_url("4.7-stable", "mac")
    template_url = godot_bootstrap.build_template_download_url("4.8-dev1")

    assert editor_url == (
        "https://downloads.godotengine.org/?version=4.7&flavor=stable&slug=macos.universal.zip&platform=macos.universal"
    )
    assert template_url == (
        "https://downloads.godotengine.org/?version=4.8&flavor=dev1&slug=export_templates.tpz&platform=templates"
    )


def test_godot_bootstrap_editor_dry_run_uses_public_root(tmp_path: Path) -> None:
    payload = godot_bootstrap.bootstrap_editor(
        godot_version="4.7-stable",
        native_target="windows",
        install_root=tmp_path / "PublicGodot",
        dry_run=True,
    )

    assert payload["status"] == "dry-run"
    assert payload["download_url"].endswith("platform=windows.64")
    assert payload["target_path"].endswith(r"PublicGodot\Godot_v4.7-stable_win64.exe")
    assert payload["archive_page_url"] == "https://godotengine.org/download/archive/4.7-stable/"


def test_godot_bootstrap_editor_extracts_flat_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "godot.zip"
    target_root = tmp_path / "PublicGodot"
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Godot_v4.7-stable_win64.exe", "stub\n")

    monkeypatch.setattr(godot_bootstrap, "_download_file", lambda url, destination: {"requested_url": url, "final_url": url, "download_path": str(archive)})

    payload = godot_bootstrap.bootstrap_editor(
        godot_version="4.7-stable",
        native_target="windows",
        install_root=target_root,
        archive_path=archive,
    )

    install = target_root / "Godot_v4.7-stable_win64.exe"
    assert payload["status"] == "ok"
    assert install.is_dir()
    assert (install / "Godot_v4.7-stable_win64.exe").is_file()


def test_godot_bootstrap_templates_dry_run_builds_expected_url(tmp_path: Path) -> None:
    payload = godot_bootstrap.bootstrap_templates(
        godot_version="4.7-stable",
        template_root=tmp_path / "templates",
        dry_run=True,
    )

    assert payload["status"] == "dry-run"
    assert payload["template_download_url"].endswith("slug=export_templates.tpz&platform=templates")
    assert payload["template_target_path"].endswith("templates")


def test_godot_bootstrap_template_selector_uses_any_installed_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(godot_bootstrap, "_installed_version_tags", lambda native_target: {
        "windows": ["4.7-stable"],
        "linux": ["4.8-dev1"],
        "mac": ["4.6.3-stable"],
    }[native_target])

    payload = godot_bootstrap.bootstrap_templates(
        godot_selector="4.7-stable..4.8-dev1",
        template_root=tmp_path / "templates",
        dry_run=True,
    )

    assert payload["godot_version"] == "4.8-dev1"
    assert payload["requested_version_source"] == "installed"


def test_host_inventory_uses_engine_and_tool_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_cesium_host_inventory.platform, "system", lambda: "Windows")
    monkeypatch.setattr(build_cesium_host_inventory.platform, "machine", lambda: "AMD64")
    public_root = Path.cwd() / "tmp-public"
    unreal_root = public_root / "Unreal"
    unity_root = public_root / "Unity"
    godot_root = public_root / "Godot"
    linux_support_root = unreal_root / "Engine" / "Platforms" / "Linux"
    monkeypatch.setattr(
        build_cesium_host_inventory.shutil,
        "which",
        lambda command: {
            "python": r"C:\Python\python.exe",
            "python3": None,
            "git": r"C:\Program Files\Git\cmd\git.exe",
            "docker": r"C:\Program Files\Docker\docker.exe",
            "dotnet": None,
        }.get(command),
    )
    monkeypatch.setattr(
        build_cesium_host_inventory.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {
            "unreal": [unreal_root],
            "unity": [unity_root],
            "godot": [godot_root],
        },
    )
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_unreal_linux_roots", lambda: [Path("/opt/unreal")])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_unreal_linux_archives", lambda: [unreal_root / "engines" / "linux" / "Linux_Unreal_Engine_5.8.0.zip"])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_windows_versions", lambda: [{"version": "4.7-stable"}])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_linux_versions", lambda: [{"version": "4.7-stable"}])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_macos_versions", lambda: [{"version": "4.7-stable"}])
    monkeypatch.setattr(
        build_cesium_host_inventory.unity_env,
        "describe_host",
        lambda: {
            "platform": "Windows",
            "arch": "AMD64",
            "public_roots": [_portable_path(unity_root)],
            "installs": [
                {
                    "version": "6000.5.2f1",
                    "install_root": _portable_path(public_root / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
                    "editor_path": _portable_path(public_root / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                    "editor_app_path": None,
                    "source": "scan",
                    "quirks": (),
                }
            ],
            "default_install": {
                "version": "6000.5.2f1",
                "install_root": _portable_path(public_root / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
                "editor_path": _portable_path(public_root / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                "editor_app_path": None,
                "source": "scan",
                "quirks": (),
            },
            "recommended_editor_overrides": {"FASTDIS_UNITY_EDITOR": _portable_path(public_root / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe")},
        },
    )

    payload = build_cesium_host_inventory.build_payload()

    assert payload["schema"] == "cesium.host_inventory.v1"
    assert payload["host"]["platform"] == "Windows"
    assert payload["engines"]["unity"]["installed_versions"] == ["6000.5.2f1"]
    assert payload["engines"]["godot"]["mac_versions"] == ["4.7-stable"]
    assert payload["runway"]["unity"] is True
    assert payload["runway"]["godot"] is True
    assert payload["runway"]["unreal"] is True


def test_host_inventory_limits_godot_runway_when_selector_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_windows_versions", lambda: [{"version": "4.6.3-stable"}, {"version": "4.7-stable"}])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_linux_versions", lambda: [{"version": "4.7.1-rc1"}, {"version": "4.8-dev1"}])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "discover_godot_macos_versions", lambda: [{"version": "4.8-dev2"}, {"version": "4.8-dev1"}])
    monkeypatch.setattr(build_cesium_host_inventory.engine_root_discovery, "public_engine_search_roots", lambda: {"unreal": [], "unity": [], "godot": [Path.cwd() / "tmp-public" / "Godot"]})
    monkeypatch.setattr(build_cesium_host_inventory.unity_env, "describe_host", lambda: {"platform": "Windows", "arch": "AMD64", "public_roots": [], "installs": [], "default_install": None, "recommended_editor_overrides": {}})

    payload = build_cesium_host_inventory.build_payload(
        build_cesium_host_inventory.parse_args(["--godot-selector", "4.7-stable..4.8-dev1", "--max-godot-matches", "2"])
    )

    assert payload["engines"]["godot"]["requested_selector"] == "4.7-stable..4.8-dev1"
    assert payload["engines"]["godot"]["selected_versions"] == ["4.8-dev1", "4.7.1-rc1"]
    assert payload["runway"]["godot"] is True


def test_host_inventory_module_wrapper_imports_main() -> None:
    import cesium.host_inventory as host_inventory

    assert host_inventory.main is build_cesium_host_inventory.main


def test_cesium_cli_dispatches_host_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_command(command: str, argv: list[str]) -> int:
        calls.append((command, argv))
        return 7

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["host-inventory", "--godot-selector", "4.7-stable..4.8-dev1", "--max-godot-matches", "2"])

    assert exit_code == 7
    assert calls[-1][0] == "host-inventory"
    assert calls[-1][1] == ["--godot-selector", "4.7-stable..4.8-dev1", "--max-godot-matches", "2"]


def test_godot_version_selector_orders_and_limits_ranges() -> None:
    tags = ["4.6.3-stable", "4.8-dev1", "4.7-stable", "4.7.1-rc1", "4.8-dev1"]

    selected = godot_versioning.select_versions(tags, "4.7-stable..4.8-dev1", limit=2)

    assert selected == ["4.8-dev1", "4.7.1-rc1"]


def test_godot_linux_docker_build_mode_builds_expected_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_godot_root = tmp_path / "Godot"
    host_godot_linux_root = host_godot_root / "engines" / "linux"
    install = host_godot_linux_root / "Godot_v4.7-stable_linux.x86_64"
    install.mkdir(parents=True, exist_ok=True)
    (install / "Godot_v4.7-stable_linux.x86_64").write_text("stub\n", encoding="utf-8")
    (install / "Godot_v4.7-stable_linux_console.exe").write_text("stub\n", encoding="utf-8")
    args = godot_linux_docker.parse_args(
        [
            "--mode",
            "build",
            "--build-target",
            "linux",
            "--godot-version",
            "4.7",
            "--json-out",
            str(tmp_path / "godot.json"),
            "--md-out",
            str(tmp_path / "godot.md"),
        ]
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "public_engine_search_roots",
        lambda: {"godot": [host_godot_root], "unreal": [], "unity": []},
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_windows_versions",
        lambda: [],
    )
    monkeypatch.setattr(
        godot_linux_docker.engine_root_discovery,
        "discover_godot_linux_versions",
        lambda: [
            {
                "version": "4.7-stable",
                "platform": "linux",
                "root": install,
                "executable": install / "Godot_v4.7-stable_linux.x86_64",
                "console_executable": install / "Godot_v4.7-stable_linux.x86_64",
            }
        ],
    )

    command = godot_linux_docker.build_docker_command(args)

    assert command[0:4] == ["docker", "run", "--rm", "--name"]
    assert "--platform" in command
    assert "cesium-godot-linux-proof-linux" in command[4]
    joined = " ".join(command)
    assert "tools.build_godot_example" in joined
    assert "--mode build" not in joined
    assert "CESIUM_GODOT_WORK_ROOT=/tmp/cesium_godot" in joined
    assert "HOME=/tmp/cesium_godot/home" in joined
    assert "XDG_CACHE_HOME=/tmp/cesium_godot/home/.cache" in joined
    assert "XDG_CONFIG_HOME=/tmp/cesium_godot/home/.config" in joined
    assert "XDG_DATA_HOME=/tmp/cesium_godot/home/.local/share" in joined
    assert "--build-target" in joined
    assert "linux" in joined
    assert "--godot-version" in joined
    assert "4.7" in joined
    assert str(install) in joined
    assert "FASTDIS_GODOT_ROOTS" in joined


def test_unity_linux_docker_builds_expected_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_unity_root = tmp_path / "Unity" / "Hub" / "Editor"
    install_root = host_unity_root / "6000.5.2f1"
    (install_root / "Editor").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(unity_linux_docker.unity_env, "default_scan_roots", lambda: [host_unity_root])
    monkeypatch.setattr(
        unity_linux_docker.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.5.2f1",
                install_root=str(install_root),
                editor_path=str(install_root / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="scan",
                quirks=(),
            )
        ],
    )
    args = unity_linux_docker.parse_args(
        [
            "--native-target",
            "linux",
            "--json-out",
            str(tmp_path / "unity.json"),
            "--md-out",
            str(tmp_path / "unity.md"),
        ]
    )

    command = unity_linux_docker.build_docker_command(args)

    assert command[0:4] == ["docker", "run", "--rm", "--name"]
    assert "--platform" in command
    assert "cesium-unity-linux-proof-linux" in command[4]
    joined = " ".join(command)
    assert "tools.build_unity_native_matrix" in joined
    assert "--json-out" in joined
    assert "--md-out" in joined
    assert str(install_root) in joined
    assert "FASTDIS_UNITY_ROOTS" in joined


def test_unity_linux_docker_dry_run_writes_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    json_out = tmp_path / "unity.json"
    md_out = tmp_path / "unity.md"
    monkeypatch.setattr(
        unity_linux_docker.unity_env,
        "describe_host",
        lambda: {
            "platform": "Windows",
            "arch": "AMD64",
            "public_roots": [_portable_path(Path.cwd() / "tmp-public" / "Unity")],
            "installs": [
                {
                    "version": "6000.5.2f1",
                    "install_root": _portable_path(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
                    "editor_path": _portable_path(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                    "editor_app_path": None,
                    "source": "scan",
                    "quirks": (),
                }
            ],
            "default_install": {
                "version": "6000.5.2f1",
                "install_root": _portable_path(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1"),
                "editor_path": _portable_path(Path.cwd() / "tmp-public" / "Program Files" / "Unity" / "Hub" / "Editor" / "6000.5.2f1" / "Editor" / "Unity.exe"),
                "editor_app_path": None,
                "source": "scan",
                "quirks": (),
            },
        },
    )

    exit_code = unity_linux_docker.main(
        [
            "--dry-run",
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    assert exit_code == 0
    assert json_out.is_file()
    assert md_out.is_file()
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status"] == "dry-run"
    assert payload["host_snapshot"]["installed_versions"] == ["6000.5.2f1"]
    assert any(Path(path).name == "Unity" for path in payload["host_snapshot"]["public_roots"])
    assert "Host Snapshot" in md_out.read_text(encoding="utf-8")


def test_unity_linux_docker_blocker_signals_surface_missing_container_editor() -> None:
    signals = unity_linux_docker._blocker_signals(
        {
            "host": {"installs": []},
            "summary": {"installed_versions": []},
            "gaps": ["Unity Linux/Docker remains planned.", "Unity macOS remains planned."],
        }
    )

    assert signals == [
        "The Linux container did not discover a Unity editor install, so this lane is still proof-of-commandability only.",
        "Unity Linux/Docker still has no installed editor versions inside the container.",
        "Unity Linux/Docker remains planned.",
    ]


def test_linux_docker_runner_helpers() -> None:
    name = linux_docker_runner.resolved_container_name("runner", identifier="5.8")
    log_path = linux_docker_runner.docker_log_path(Path("C:/tmp/logs"), command_name="build", identifier="5.8")

    assert name.startswith("runner-5.8-")
    assert log_path.name == "build_5.8.log"


def test_root_cli_dispatches_to_expected_scripts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_command(command: str, argv: list[str]) -> int:
        calls.append((command, argv))
        return 7

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["prepare-source-route", "--no-fetch"])
    assert exit_code == 7
    assert calls[-1][0] == "prepare-source-route"
    assert calls[-1][1] == ["--no-fetch"]

    exit_code = cesium_cli.main(["bootstrap", "--prepare-only"])
    assert exit_code == 7
    assert calls[-1][0] == "bootstrap"
    assert calls[-1][1] == ["--prepare-only"]

    exit_code = cesium_cli.main(["example", "doctor", "--engine", "unreal"])
    assert exit_code == 7
    assert calls[-1][0] == "example"
    assert calls[-1][1] == ["doctor", "--engine", "unreal"]

    exit_code = cesium_cli.main(["unreal-linux", "report", "--engine-version", "5.7"])
    assert exit_code == 7
    assert calls[-1][0] == "unreal-linux"
    assert calls[-1][1] == ["report", "--engine-version", "5.7"]

    exit_code = cesium_cli.main(["unreal-linux-docker", "build-plan", "--engine-version", "5.8"])
    assert exit_code == 7
    assert calls[-1][0] == "unreal-linux-docker"
    assert calls[-1][1] == ["build-plan", "--engine-version", "5.8"]

    exit_code = cesium_cli.main(["godot-linux-docker", "report", "--native-target", "linux"])
    assert exit_code == 7
    assert calls[-1][0] == "godot-linux-docker"
    assert calls[-1][1] == ["report", "--native-target", "linux"]

    exit_code = cesium_cli.main(["unity-linux-docker", "--dry-run"])
    assert exit_code == 7
    assert calls[-1][0] == "unity-linux-docker"
    assert calls[-1][1] == ["--dry-run"]

    exit_code = cesium_cli.main(["engine-matrix"])
    assert exit_code == 7
    assert calls[-1][0] == "engine-matrix"
    assert calls[-1][1] == []

    exit_code = cesium_cli.main(
        [
            "unreal-linux-docker",
            "build",
            "--engine-version",
            "5.8",
            "--ue-root",
            str(Path.cwd() / "tmp-public" / "Epic Games" / "UE_5.8"),
        ]
    )
    assert exit_code == 7
    assert calls[-1][0] == "unreal-linux-docker"
    assert calls[-1][1] == [
        "build",
        "--engine-version",
        "5.8",
        "--ue-root",
        str(Path.cwd() / "tmp-public" / "Epic Games" / "UE_5.8"),
    ]

    exit_code = cesium_cli.main([
        "unreal-linux-docker",
        "build",
        "--engine-version",
        "5.8",
        "--linux-platform-support-root",
        str(Path.cwd() / "tmp-public" / "Unreal" / "Engine" / "Platforms" / "Linux"),
    ])
    assert exit_code == 7
    assert calls[-1][0] == "unreal-linux-docker"
    assert calls[-1][1] == [
        "build",
        "--engine-version",
        "5.8",
        "--linux-platform-support-root",
        str(Path.cwd() / "tmp-public" / "Unreal" / "Engine" / "Platforms" / "Linux"),
    ]


def test_pyproject_exposes_console_script() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "cesium-engine-compatibility"
    assert pyproject["project"]["scripts"]["cesium"] == "cesium:main"
    assert pyproject["project"]["scripts"]["cesium-bootstrap"] == "tools.bootstrap_local_dev:main"
    assert pyproject["project"]["scripts"]["cesium-prepare-source-route"] == "extensions.cesium.tools.prepare_cesium_source_route:main"
    assert pyproject["project"]["scripts"]["cesium-example"] == "extensions.cesium.tools.cesium_example_workflow:main"
    assert pyproject["project"]["scripts"]["cesium-godot-doctor"] == "tools.godot_doctor:main"
    assert pyproject["project"]["scripts"]["cesium-unreal-linux"] == "extensions.cesium.tools.unreal_linux_lane:main"
    assert pyproject["project"]["scripts"]["cesium-unreal-linux-docker"] == "extensions.cesium.tools.unreal_linux_docker:main"
    assert pyproject["project"]["scripts"]["cesium-godot-linux-docker"] == "extensions.cesium.tools.godot_linux_docker:main"
    assert pyproject["project"]["scripts"]["cesium-godot-example-build"] == "tools.build_godot_example:main"
    assert pyproject["project"]["scripts"]["cesium-unity-linux-docker"] == "extensions.cesium.tools.unity_linux_docker:main"
    assert pyproject["project"]["scripts"]["cesium-unity-example-build"] == "tools.build_unity_example:main"
    assert pyproject["project"]["scripts"]["cesium-compatibility-packet"] == "tools.build_cesium_compatibility_packet:main"
    assert pyproject["project"]["scripts"]["cesium-unreal-visual-proof"] == "tools.build_unreal_visual_proof:main"
    assert pyproject["project"]["scripts"]["cesium-cross-platform-fix-notes"] == "tools.build_cesium_cross_platform_fix_notes:main"
    assert pyproject["project"]["scripts"]["cesium-planned-routes"] == "tools.build_cesium_planned_routes:main"
    assert pyproject["project"]["scripts"]["cesium-engine-matrix"] == "tools.build_cesium_engine_matrix:main"
    assert pyproject["project"]["scripts"]["cesium-unity-native-matrix"] == "tools.build_unity_native_matrix:main"
    assert pyproject["project"]["scripts"]["cesium-plugin-lanes"] == "tools.run_cesium_plugin_lanes:main"
    assert pyproject["project"]["scripts"]["cesium-execution-audit"] == "tools.build_cesium_execution_audit:main"
    assert pyproject["project"]["scripts"]["cesium-capture-unity-host-report"] == "tools.capture_unity_host_report:main"
    assert pyproject["project"]["scripts"]["cesium-stage-unity-host-report"] == "tools.stage_unity_host_report:main"
    assert pyproject["project"]["scripts"]["cesium-export-unity-host-handoff"] == "tools.export_unity_host_handoff:main"
    assert pyproject["project"]["scripts"]["cesium-import-unity-host-report"] == "tools.import_unity_host_report:main"
    assert "cesium" in pyproject["tool"]["setuptools"]["packages"]["find"]["include"]


def test_cesium_package_wrapper_exports_the_cli_entry_points() -> None:
    assert cesium.main is cesium_cli.main
    assert cesium.parse_args is cesium_cli.parse_args


def test_godot_doctor_wrapper_forwards_default_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(godot_doctor.cesium_example_workflow, "main", fake_main)

    exit_code = godot_doctor.main([])

    assert exit_code == 0
    assert captured["argv"] == [
        "doctor",
        "--engine",
        "godot",
        "--native-target",
        "windows",
        "--format",
        "text",
    ]


def test_cesium_godot_doctor_command_forwards_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["godot-doctor"])

    assert exit_code == 0
    assert captured["command"] == "godot-doctor"
    assert captured["argv"] == ["--native-target", "windows", "--format", "text"]


def test_cesium_unreal_visual_proof_command_forwards_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["unreal-visual-proof"])

    assert exit_code == 0
    assert captured["command"] == "unreal-visual-proof"
    assert captured["argv"] == []


def test_cesium_windows_visual_proof_command_forwards_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["windows-visual-proof"])

    assert exit_code == 0
    assert captured["command"] == "windows-visual-proof"
    assert captured["argv"] == []


def test_cesium_unity_visual_proof_command_forwards_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["unity-visual-proof"])

    assert exit_code == 0
    assert captured["command"] == "unity-visual-proof"
    assert captured["argv"] == []


def test_cesium_godot_visual_proof_command_forwards_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    exit_code = cesium_cli.main(["godot-visual-proof"])

    assert exit_code == 0
    assert captured["command"] == "godot-visual-proof"
    assert captured["argv"] == []


def test_cesium_bootstrap_command_forwards_package_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command: str, argv: list[str]) -> int:
        captured["command"] = command
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cesium_cli, "_run_command", fake_run_command)

    assert cesium_cli.main(
        [
            "bootstrap",
            "--deps-prefix",
            str(tmp_path / "deps"),
            "--work-root",
            str(tmp_path / "work"),
            "--skip-install",
            "--prepare-only",
            "--",
            "tests/test_cesium_tools.py",
        ]
    ) == 0

    assert captured["command"] == "bootstrap"
    assert captured["argv"] == [
        "--deps-prefix",
        str(tmp_path / "deps"),
        "--work-root",
        str(tmp_path / "work"),
        "--skip-install",
        "--prepare-only",
        "--",
        "tests/test_cesium_tools.py",
    ]


def test_visual_proof_normalize_validate_and_compare_are_commensurate(tmp_path: Path) -> None:
    scan_roots: list[Path] = []
    for engine in ("unreal", "unity", "godot"):
        source_root = tmp_path / "source" / engine
        capture_root = tmp_path / "capture" / engine / "windows" / "x86_64"
        _seed_visual_proof_source(source_root)
        payload = build_cesium_visual_proof.normalize_visual_proof_capture(
            engine,
            source_root,
            capture_root,
            host="windows",
            native_target="windows",
            architecture="x86_64",
        )
        assert payload["status"] == "pass"
        assert payload["missing"] == []
        assert payload["capture_variants"] == ["proxy", "cesium"]
        assert payload["shot_names"] == ["overview", "oblique", "close"]
        scan_roots.append(capture_root)

        validation = validate_visual_proof_roots.validate_root(capture_root)
        assert validation["status"] == "pass"
        assert validation["manifest_exists"] is True
        assert validation["png_count"] == 6
        assert validation["engine"] == engine

    comparison = compare_cesium_visual_proof.build_payload(scan_roots=scan_roots, strict_missing=True)

    assert comparison["status"] == "pass"
    assert comparison["summary"]["expected_engine_count"] == 3
    assert comparison["summary"]["present_engine_count"] == 3
    assert comparison["summary"]["missing_engine_count"] == 0
    assert comparison["summary"]["quality_issue_count"] == 0
    assert comparison["summary"]["canonical_comparison_count"] > 0
    assert comparison["summary"]["variant_comparison_count"] > 0
    assert comparison["summary"]["engine_variant_comparison_count"] > 0
    assert comparison["findings"] == []


def test_visual_proof_compare_detects_black_frames(tmp_path: Path) -> None:
    source_root = tmp_path / "black_source"
    capture_root = tmp_path / "black_capture"
    source_root.mkdir(parents=True, exist_ok=True)
    for variant in ("proxy", "cesium"):
        for shot in build_cesium_visual_proof.CAMERA_SHOTS:
            _write_visual_proof_png(
                source_root / f"{variant}_{shot.name}.png",
                background=(0, 0, 0),
                accent=(0, 0, 0),
                patterned=False,
            )

    normalize_payload = normalize_cesium_visual_proof.build_payload(
        normalize_cesium_visual_proof.parse_args(
            [
                "--engine",
                "godot",
                "--source-root",
                str(source_root),
                "--capture-root",
                str(capture_root),
            ]
        )
    )

    assert normalize_payload["status"] == "pass"

    comparison = compare_cesium_visual_proof.build_payload(scan_roots=[capture_root], strict_missing=False)

    assert comparison["status"] == "fail"
    assert comparison["summary"]["quality_issue_count"] > 0
    assert any("near_black" in finding for finding in comparison["findings"])
    assert any("flat_solid" in finding for finding in comparison["findings"])


def test_visual_proof_compare_scopes_cross_engine_and_content_deltas(tmp_path: Path) -> None:
    scan_roots: list[Path] = []
    for engine in ("unity", "godot"):
        source_root = tmp_path / "source" / engine
        capture_root = tmp_path / "capture" / engine / "windows" / "x86_64"
        _seed_visual_proof_source(source_root)
        normalize_cesium_visual_proof.build_payload(
            normalize_cesium_visual_proof.parse_args(
                [
                    "--engine",
                    engine,
                    "--source-root",
                    str(source_root),
                    "--capture-root",
                    str(capture_root),
                ]
            )
        )
        scan_roots.append(capture_root)

    comparison = compare_cesium_visual_proof.build_payload(scan_roots=scan_roots, strict_missing=True)

    assert comparison["status"] == "pass"
    assert comparison["findings"] == []
    assert all(
        item["comparison_scope"] == "cross-engine-structural"
        for item in comparison["canonical_comparisons"]
    )
    assert all(
        item["status"] == "content-delta"
        for item in comparison["engine_variant_comparisons"]
    )
    assert all(
        "structure_centroid_distance" in item["metrics"]
        for item in comparison["canonical_comparisons"]
    )


def test_visual_proof_packet_tracks_all_engine_runner_reports() -> None:
    payload = build_cesium_visual_proof.build_payload()

    related = payload["related_packets"]
    assert related["unreal_visual_proof"]["path"].endswith("unreal_visual_proof/unreal_visual_proof.json")
    assert related["unity_visual_proof"]["path"].endswith("unity_visual_proof/unity_visual_proof.json")
    assert related["godot_visual_proof"]["path"].endswith("godot_visual_proof/godot_visual_proof.json")
    unity_windows = next(
        target for target in payload["targets"] if target["engine"] == "unity" and target["native_target"] == "windows" and target["architecture"] == "x86_64"
    )
    godot_windows = next(
        target for target in payload["targets"] if target["engine"] == "godot" and target["native_target"] == "windows" and target["architecture"] == "x86_64"
    )
    assert unity_windows["startup_health_command"] == "cesium-unity-visual-proof"
    assert godot_windows["startup_health_command"] == "cesium-godot-aggressive-launcher --native-target windows --max-versions 1"


def test_windows_visual_proof_bundle_payload_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        build_windows_visual_proof.build_cesium_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "camera_shots": [{"name": "overview"}],
        },
    )
    monkeypatch.setattr(
        build_windows_visual_proof.build_unreal_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "UnrealEditor.exe",
            "launcher_command": "UnrealEditor.exe",
            "normalize_command": "cesium-visual-proof-normalize --engine unreal",
            "manifest_path": "artifacts/reports/unreal_visual_proof/unreal_visual_proof.json",
            "expected_pngs": ["proxy_overview.png", "cesium_overview.png"],
            "engine_side_harness_status": "present",
        },
    )
    monkeypatch.setattr(
        build_windows_visual_proof.build_unity_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "cesium-unity-visual-proof",
            "launcher_command": 'Unity.exe -batchmode -nographics -quit -projectPath "UnityProject"',
            "normalize_command": "cesium-visual-proof-normalize --engine unity",
            "manifest_path": "artifacts/reports/unity_visual_proof/unity_visual_proof.json",
            "expected_pngs": ["proxy_overview.png", "cesium_overview.png"],
            "engine_side_harness_status": "present",
        },
    )
    monkeypatch.setattr(
        build_windows_visual_proof.build_godot_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "cesium-godot-aggressive-launcher --native-target windows --max-versions 1",
            "launcher_command": "Godot.exe",
            "normalize_command": "cesium-visual-proof-normalize --engine godot",
            "manifest_path": "artifacts/reports/godot_visual_proof/godot_visual_proof.json",
            "expected_pngs": ["proxy_overview.png", "cesium_overview.png"],
            "engine_side_harness_status": "present",
        },
    )
    monkeypatch.setattr(
        build_windows_visual_proof.compare_cesium_visual_proof,
        "build_payload",
        lambda strict_missing=True: {"status": "pass", "findings": []},
    )

    payload = build_windows_visual_proof.build_payload()

    assert payload["schema"] == "cesium.windows_visual_proof.v1"
    assert payload["status"] == "commandable"
    assert len(payload["runner_reports"]) == 3
    assert payload["visual_proof_packet"]["status"] == "commandable"
    assert payload["comparison_packet"]["status"] == "pass"
    assert any(row["engine"] == "godot" for row in payload["runner_commands"])
    unity_row = next(row for row in payload["runner_commands"] if row["engine"] == "unity")
    assert "-batchmode" in unity_row["launch_command"]


def test_unreal_visual_proof_runner_payload_shapes() -> None:
    payload = build_unreal_visual_proof.build_payload()

    assert payload["schema"] == "cesium.unreal_visual_proof.v1"
    assert payload["status"] in {"planned", "commandable"}
    assert payload["engine"] == "unreal"
    assert payload["native_target"] == "windows"
    assert payload["architecture"] == "x86_64"
    assert _portable_path(payload["command"]).startswith("UnrealEditor.exe ")
    assert _portable_path(payload["command"]).endswith(
        '-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache -ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"'
    )
    assert "CesiumVanillaExample.uproject" in _portable_path(payload["command"])
    assert _portable_path(payload["raw_capture_root"]).endswith("Saved/Screenshots/WindowsEditor")
    assert _portable_path(payload["normalized_capture_root"]).endswith("artifacts/reports/cesium_visual_proof/unreal/windows/x86_64")
    assert _portable_path(payload["manifest_path"]).endswith("visual_proof_manifest.json")
    assert _portable_path(payload["normalize_command"]).startswith("cesium-visual-proof-normalize --engine unreal")
    assert payload["windows_tests"] == [
        "Cesium.VisualProof.Windows.ProxyEarth",
        "Cesium.VisualProof.Windows.CesiumEarth",
    ]
    selected_root = Path(payload["editor_discovery"]["selected_root"])
    fake_launcher = (
        f'"{_portable_path(selected_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe")}" '
        f'"{_portable_path(ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject")}" '
    )
    assert [_portable_path(command) for command in payload["launcher_commands"]] == [
        f'{fake_launcher}-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache -ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"',
        f'{fake_launcher}-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache -ExecCmds="Automation RunTests Cesium.VisualProof.Windows.CesiumEarth; Quit"',
    ]
    assert payload["engine_side_harness_status"] == "present"
    assert _portable_path(payload["engine_side_harness_path"]).endswith(
        "external/cesium/cesium-unreal/Source/CesiumRuntime/Private/Tests/CesiumVisualProof.spec.cpp"
    )


def test_unity_visual_proof_runner_payload_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = Path("simulated") / "Unity" / "6000.5.0f1"
    monkeypatch.setattr(
        build_unity_visual_proof.unity_env,
        "discover_installs",
        lambda: [
            unity_env.UnityInstall(
                version="6000.5.0f1",
                install_root=str(fake_root),
                editor_path=str(fake_root / "Editor" / "Unity.exe"),
                editor_app_path=None,
                source="test",
                quirks=(),
            )
        ],
    )

    payload = build_unity_visual_proof.build_payload()

    assert payload["schema"] == "cesium.unity_visual_proof.v1"
    assert payload["status"] == "commandable"
    assert payload["engine"] == "unity"
    assert payload["native_target"] == "windows"
    assert payload["architecture"] == "x86_64"
    assert payload["engine_side_harness_status"] == "present"
    assert _portable_path(payload["engine_side_harness_path"]).endswith(
        "extensions/cesium/examples/unity/CesiumVanillaExample/Assets/CesiumVisualProofCapture.cs"
    )
    assert _portable_path(payload["command"]).endswith("cesium-unity-visual-proof")
    assert "Unity.exe" in _portable_path(payload["launcher_command"])
    assert "-batchmode" in _portable_path(payload["launcher_command"])
    assert "-projectPath" in _portable_path(payload["launcher_command"])
    assert _portable_path(payload["manifest_path"]).endswith("visual_proof_manifest.json")
    assert _portable_path(payload["normalize_command"]).startswith("cesium-visual-proof-normalize --engine unity")


def test_godot_visual_proof_runner_payload_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = Path("simulated") / "Godot" / "engines" / "windows" / "Godot_v4.7-stable_win64.exe"
    monkeypatch.setattr(
        build_godot_visual_proof.engine_root_discovery,
        "discover_godot_windows_versions",
        lambda: [
            {
                "version": "4.7-stable",
                "root": fake_root,
                "executable": fake_root / "Godot_v4.7-stable_win64.exe",
                "console_executable": fake_root / "Godot_v4.7-stable_win64_console.exe",
            }
        ],
    )

    payload = build_godot_visual_proof.build_payload()

    assert payload["schema"] == "cesium.godot_visual_proof.v1"
    assert payload["status"] == "commandable"
    assert payload["engine"] == "godot"
    assert payload["native_target"] == "windows"
    assert payload["architecture"] == "x86_64"
    assert payload["engine_side_harness_status"] == "present"
    assert _portable_path(payload["engine_side_harness_path"]).endswith(
        "extensions/cesium/examples/godot/CesiumVanillaExample/scripts/VisualProofRunner.gd"
    )
    assert _portable_path(payload["command"]).endswith("cesium-godot-aggressive-launcher --native-target windows --max-versions 1")
    assert _portable_path(payload["launcher_command"]).endswith("Godot_v4.7-stable_win64_console.exe")
    assert _portable_path(payload["manifest_path"]).endswith("visual_proof_manifest.json")
    assert _portable_path(payload["normalize_command"]).startswith("cesium-visual-proof-normalize --engine godot")


def test_windows_visual_proof_run_orchestrates_engine_lanes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    unreal_raw = tmp_path / "unreal_raw"
    unity_raw = tmp_path / "unity_raw"
    godot_raw = tmp_path / "godot_raw"
    unreal_norm = tmp_path / "unreal_norm"
    unity_norm = tmp_path / "unity_norm"
    godot_norm = tmp_path / "godot_norm"

    monkeypatch.setattr(run_windows_visual_proof, "UNREAL_NORMALIZED_CAPTURE_ROOT", unreal_norm)
    monkeypatch.setattr(run_windows_visual_proof, "UNITY_NORMALIZED_CAPTURE_ROOT", unity_norm)
    monkeypatch.setattr(run_windows_visual_proof, "GODOT_NORMALIZED_CAPTURE_ROOT", godot_norm)
    monkeypatch.setattr(run_windows_visual_proof.build_cesium_visual_proof, "UNREAL_RAW_CAPTURE_ROOT", unreal_raw)

    monkeypatch.setattr(
        run_windows_visual_proof.build_unreal_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "UnrealEditor.exe",
            "launcher_command": "UnrealEditor.exe",
            "raw_capture_root": str(unreal_raw),
            "normalized_capture_root": str(unreal_norm),
            "engine_side_harness_status": "present",
            "editor_discovery": {"status": "present"},
        },
    )
    monkeypatch.setattr(
        run_windows_visual_proof.build_unity_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "CesiumUnityBuild",
            "launcher_command": "Unity.exe -batchmode -nographics -quit -projectPath UnityProject",
            "example_project": str(tmp_path / "unity" / "CesiumVanillaExample.unity"),
            "engine_side_harness_status": "present",
            "editor_discovery": {"status": "present"},
        },
    )
    monkeypatch.setattr(
        run_windows_visual_proof.build_godot_visual_proof,
        "build_payload",
        lambda: {
            "status": "commandable",
            "command": "cesium-godot-aggressive-launcher --native-target windows --max-versions 1",
            "launcher_command": "Godot_v4.7-stable_win64_console.exe",
            "example_project": str(tmp_path / "godot" / "project.godot"),
            "engine_side_harness_status": "present",
            "editor_discovery": {"status": "present"},
        },
    )
    monkeypatch.setattr(
        run_windows_visual_proof.unity_env,
        "resolve_install",
        lambda version=None: unity_env.UnityInstall(
            version="6000.5.0f1",
            install_root=str(tmp_path / "Unity" / "6000.5.0f1"),
            editor_path=str(tmp_path / "Unity" / "6000.5.0f1" / "Editor" / "Unity.exe"),
            editor_app_path=None,
            source="test",
            quirks=(),
        ),
    )

    def fake_unity_build(build_args: object) -> dict[str, object]:
        out_dir = Path(getattr(build_args, "out_dir"))
        player_path = out_dir / "windows" / "CesiumVanillaExample.exe"
        player_path.parent.mkdir(parents=True, exist_ok=True)
        player_path.write_text("fake unity player", encoding="utf-8")
        return {"status": "pass", "output_path": str(player_path), "unity_version": "6000.5.0f1"}

    monkeypatch.setattr(run_windows_visual_proof.build_unity_example, "run_build", fake_unity_build)

    compare_calls: list[list[str]] = []

    def fake_compare(*, scan_roots=None, strict_missing=True, **kwargs):
        compare_calls.append([str(path) for path in scan_roots or []])
        return {"status": "pass", "summary": {"sample_count": 6, "missing_engines": []}, "findings": []}

    monkeypatch.setattr(run_windows_visual_proof.compare_cesium_visual_proof, "build_payload", fake_compare)

    def fake_normalize(engine, source_root, capture_root, **kwargs):
        capture_root = Path(capture_root)
        capture_root.mkdir(parents=True, exist_ok=True)
        _seed_visual_proof_source(capture_root)
        manifest = capture_root / "visual_proof_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": "cesium.visual_proof_manifest.v1",
                    "engine": engine,
                    "host": "windows",
                    "native_target": "windows",
                    "architecture": "x86_64",
                    "capture_variants": ["proxy", "cesium"],
                    "shot_names": [shot.name for shot in build_cesium_visual_proof.CAMERA_SHOTS],
                    "camera_shots": [
                        {
                            "name": shot.name,
                            "camera_position": list(shot.camera_position),
                            "look_at": list(shot.look_at),
                            "up": list(shot.up),
                            "fov_degrees": shot.fov_degrees,
                        }
                        for shot in build_cesium_visual_proof.CAMERA_SHOTS
                    ],
                    "capture_paths": [str(path) for path in sorted(capture_root.glob("*.png"))],
                }
            ),
            encoding="utf-8",
        )
        return {
            "status": "pass",
            "engine": engine,
            "source_root": str(source_root),
            "capture_root": str(capture_root),
            "manifest_path": str(manifest),
        }

    monkeypatch.setattr(run_windows_visual_proof.build_cesium_visual_proof, "normalize_visual_proof_capture", fake_normalize)

    def fake_godot_build(args: object) -> dict[str, object]:
        capture_root = Path(getattr(args, "capture_root"))
        capture_root.mkdir(parents=True, exist_ok=True)
        _seed_visual_proof_source(capture_root)
        return {
            "status": "pass",
            "capture_root": str(capture_root),
            "example_project": str(tmp_path / "godot" / "project.godot"),
        }

    monkeypatch.setattr(run_windows_visual_proof.godot_aggressive_launcher, "build_payload", fake_godot_build)

    def fake_run_process(command, *, cwd, env, timeout_seconds, log_path):
        command_text = " ".join(command) if isinstance(command, list) else str(command)
        if "CesiumVanillaExample.exe" in command_text:
            player_root = Path(command[0]).parent if isinstance(command, list) and command else tmp_path
            _seed_visual_proof_source(player_root / "build" / "unity" / "CesiumVanillaExample" / "visual_proof")
        if "UnrealEditor.exe" in command_text:
            _seed_visual_proof_source(unreal_raw)
        return {
            "command": command if isinstance(command, list) else [command],
            "returncode": 0,
            "timed_out": False,
            "stdout_tail": [],
            "stderr_tail": [],
            "log_path": str(log_path),
            "success": True,
        }

    monkeypatch.setattr(run_windows_visual_proof, "_run_process", fake_run_process)

    namespace = SimpleNamespace(
        json_out=tmp_path / "windows_visual_proof_run.json",
        md_out=tmp_path / "windows_visual_proof_run.md",
        log_dir=tmp_path / "logs",
        timeout_seconds=30.0,
        unity_version=None,
        godot_selector=None,
        godot_max_versions=1,
    )

    payload = run_windows_visual_proof.build_payload(namespace)

    assert payload["schema"] == "cesium.windows_visual_proof_run.v1"
    assert payload["status"] == "pass"
    assert payload["comparison"]["status"] == "pass"
    assert len(payload["engine_results"]) == 3
    assert any(result["engine"] == "unity" and result["status"] == "pass" for result in payload["engine_results"])
    assert any(result["engine"] == "godot" and result["status"] == "pass" for result in payload["engine_results"])
    assert any(result["engine"] == "unreal" and result["status"] == "pass" for result in payload["engine_results"])
    assert compare_calls[-1] == [str(unreal_norm), str(unity_norm), str(godot_norm)]


def test_unreal_visual_proof_reports_launcher_command_when_editor_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = Path("simulated") / "Epic Games" / "UE_5.8"
    monkeypatch.setattr(
        build_unreal_visual_proof.engine_root_discovery,
        "discover_unreal_windows_editors",
        lambda: [
            {
                "root": fake_root,
                "executable": fake_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe",
                "command": str(fake_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"),
            }
        ],
    )

    payload = build_unreal_visual_proof.build_payload()

    assert payload["status"] == "commandable"
    assert payload["editor_discovery"]["status"] == "present"
    assert _portable_path(payload["launcher_command"]) == (
        '"simulated/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe" '
        f'"{_portable_path(ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject")}" '
        '-NoEOS -unattended -nop4 -NoEpicPortal -nosplash -NoSound -log -stdout -FullStdOutLogOutput -DDC-ForceMemoryCache -ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"'
    )
    assert payload["launcher_commands"][0].endswith(
        '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"'
    )
    assert payload["launcher_commands"][1].endswith(
        '-ExecCmds="Automation RunTests Cesium.VisualProof.Windows.CesiumEarth; Quit"'
    )


def test_godot_aggressive_launcher_orphan_cleanup_reports_matches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = '[{"pid": 1234, "name": "Godot_v4.7-stable_win64.exe", "command_line": "Godot --fastdis-launch-tag abc"}]'
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr(godot_aggressive_launcher.subprocess, "run", fake_run)

    log_path = tmp_path / "cleanup.log"
    payload = godot_aggressive_launcher._cleanup_orphan_godot_processes(["abc", ""], log_path=log_path, timeout_s=3.0)

    assert payload["supported"] is True
    assert payload["success"] is True
    assert payload["timed_out"] is False
    assert payload["killed"] == [1234]
    assert payload["matches"][0]["name"] == "Godot_v4.7-stable_win64.exe"
    assert log_path.read_text(encoding="utf-8").strip().startswith("[{\"pid\": 1234")
    assert any("powershell.exe" in str(part).lower() for part in captured["command"])
    assert captured["kwargs"]["timeout"] == 3.0


def test_godot_aggressive_launcher_orphan_cleanup_times_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 1.0), output="slow", stderr="still running")

    monkeypatch.setattr(godot_aggressive_launcher.subprocess, "run", fake_run)

    log_path = tmp_path / "cleanup-timeout.log"
    payload = godot_aggressive_launcher._cleanup_orphan_godot_processes(["abc"], log_path=log_path, timeout_s=0.5)

    assert payload["supported"] is True
    assert payload["success"] is False
    assert payload["timed_out"] is True
    assert payload["timeout_seconds"] == 0.5
    assert "orphan cleanup timed out" in log_path.read_text(encoding="utf-8")


def test_godot_aggressive_launcher_run_command_terminates_timed_out_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events: list[tuple[str, object]] = []

    class _Proc:
        pid = 4321
        returncode = None

        def __init__(self) -> None:
            self._communicate_calls = 0

        def communicate(self, timeout=None):
            self._communicate_calls += 1
            if self._communicate_calls == 1:
                raise subprocess.TimeoutExpired(cmd=["Godot"], timeout=timeout, output="partial stdout", stderr="partial stderr")
            self.returncode = -9
            return ("tail stdout", "tail stderr")

    proc = _Proc()

    def fake_popen(command, **kwargs):
        events.append(("popen", command))
        events.append(("popen_kwargs", kwargs))
        return proc

    def fake_run(command, **kwargs):
        events.append(("run", command))
        events.append(("run_kwargs", kwargs))
        class _Completed:
            returncode = 0
            stdout = ""
            stderr = ""
        return _Completed()

    monkeypatch.setattr(godot_aggressive_launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(godot_aggressive_launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(godot_aggressive_launcher.platform, "system", lambda: "Windows")

    payload = godot_aggressive_launcher._run_command(
        command=["Godot_v4.7-stable_win64.exe", "--path", "project"],
        env={},
        log_path=tmp_path / "launch.log",
        timeout_s=0.25,
    )

    assert payload["timed_out"] is True
    assert payload["success"] is False
    assert payload["exit_code"] == -9
    assert "partial stdout" in (tmp_path / "launch.log").read_text(encoding="utf-8")
    assert any("tail stdout" in row for row in payload["stdout_tail"])
    assert any(name == "run" for name, _ in events)
    assert any("taskkill" in str(command).lower() for name, command in events if name == "run")


def test_godot_aggressive_launcher_runs_visual_compare_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_build_payload(*, scan_roots, strict_missing):
        captured["scan_roots"] = scan_roots
        captured["strict_missing"] = strict_missing
        return {"status": "pass", "findings": []}

    monkeypatch.setattr(godot_aggressive_launcher.compare_cesium_visual_proof, "build_payload", fake_build_payload)

    payload = godot_aggressive_launcher._run_visual_proof_compare(tmp_path / "visual_proof")

    assert payload["status"] == "pass"
    assert captured["scan_roots"] == [tmp_path / "visual_proof"]
    assert captured["strict_missing"] is True


def test_validate_visual_proof_contracts_includes_unreal_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    contract_path = ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "VisualProofContract.md"
    readme_path = ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "README.md"
    harness_path = ROOT / "external" / "cesium" / "cesium-unreal" / "Source" / "CesiumRuntime" / "Private" / "Tests" / "CesiumVisualProof.spec.cpp"
    support_path = ROOT / "external" / "cesium" / "cesium-unreal" / "Source" / "CesiumRuntime" / "Private" / "Tests" / "CesiumLoadTestCore.cpp"
    monkeypatch.setattr(
        validate_visual_proof_contracts,
        "CONTRACTS",
        (
            {
                "engine": "unreal",
                "contract_path": contract_path,
                "readme_path": readme_path,
                "harness_path": harness_path,
                "support_path": support_path,
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
        ),
    )

    payload = validate_visual_proof_contracts.build_payload()

    assert payload["status"] == "pass"
    assert payload["contracts"][0]["harness_exists"] is True
    assert payload["contracts"][0]["support_exists"] is True
    assert payload["contracts"][0]["missing_harness_phrases"] == []
    assert payload["contracts"][0]["missing_support_phrases"] == []
    assert _portable_path(payload["contracts"][0]["harness_path"]).endswith(
        "external/cesium/cesium-unreal/Source/CesiumRuntime/Private/Tests/CesiumVisualProof.spec.cpp"
    )
