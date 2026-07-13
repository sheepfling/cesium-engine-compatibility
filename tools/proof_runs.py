"""Shared next-proof run metadata for the Cesium compatibility packet."""

from __future__ import annotations


def next_proof_runs() -> list[dict[str, object]]:
    return [
        {
            "surface": "Unreal",
            "command": "cesium-unreal-linux-docker build-plan --engine-version 5.8",
            "capture_focus": [
                "source-built Linux support tree for upstream parity",
                "--linux-platform-support-root",
                "toolchain details",
            ],
        },
        {
            "surface": "Unreal Windows Startup Health",
            "command": "cesium-example doctor --engine unreal",
            "capture_focus": [
                "source route readiness",
                "example scaffold health",
                "project marker discovery",
                "first check before Windows visual proof",
            ],
        },
        {
            "surface": "Cross-Platform Planned",
            "command": "cesium-plugin-lanes --dry-run --lanes cross-platform-planned",
            "capture_focus": [
                "refresh the dedicated planned-routes packet",
                "bundle the planned Unreal Linux, Unity Linux/Docker, Unity macOS, and Godot macOS routes",
                "show the command inventory for a fresh-host bootstrap",
                "keep the remaining planned lanes commandable without guessing",
            ],
        },
        {
            "surface": "Unity",
            "command": "cesium-unity-native-matrix",
            "capture_focus": [
                "installed editor spread",
                "pinned versus forward editor versions",
                "native target coverage",
                "live Cesium package-route proof",
            ],
        },
        {
            "surface": "Unity Windows Startup Health",
            "command": "cesium-example doctor --engine unity",
            "capture_focus": [
                "source route readiness",
                "example scaffold health",
                "project marker discovery",
                "first check before Windows visual proof",
            ],
        },
        {
            "surface": "Unity Docker",
            "command": "cesium-unity-linux-docker --native-target linux",
            "capture_focus": [
                "docker image",
                "container logs",
                "inner matrix payload",
                "Linux target proof route",
            ],
        },
        {
            "surface": "Godot Docker",
            "command": "cesium-godot-linux-docker --native-target linux",
            "capture_focus": [
                "docker image",
                "container logs",
                "inner report payload",
                "Linux target proof route",
            ],
        },
        {
            "surface": "Godot Windows Startup Health",
            "command": "cesium-godot-aggressive-launcher --native-target windows --max-versions 1",
            "capture_focus": [
                "bootstrap section with isolated runtime and staged project dir",
                "import_probe section before the health probe",
                "startup_health section from the launcher packet",
                "shader-cache bootstrap success or failure",
                "extension registration before visual proof",
                "early crash signature capture before screenshot work",
            ],
        },
        {
            "surface": "Godot Windows Import Probe",
            "command": "cesium-godot-aggressive-launcher --native-target windows --max-versions 1 --diagnostic-crash-dumps",
            "capture_focus": [
                "isolated runtime copy",
                "project import and cache warmup",
                "crash-handler-off diagnostics when needed",
                "failure evidence before visual proof",
            ],
        },
        {
            "surface": "Godot Linux Proof",
            "command": "cesium-godot-aggressive-linux-launcher --dry-run",
            "capture_focus": [
                "installed Linux versions in newest-first order",
                "per-attempt screenshot proof paths",
                "container wrapper and inner launcher split",
                "the screenshot proof contract for the Linux lane",
            ],
        },
        {
            "surface": "Godot Build",
            "command": "cesium-godot-example-build --build-target windows --godot-version 4.7",
            "capture_focus": [
                "export presets",
                "staged project path",
                "export output artifact",
                "Windows target build route",
            ],
        },
        {
            "surface": "Godot Build Docker",
            "command": "cesium-godot-linux-docker --mode build --build-target linux --godot-version 4.7",
            "capture_focus": [
                "docker image",
                "container logs",
                "inner build payload",
                "Linux export route",
            ],
        },
        {
            "surface": "Godot",
            "command": "cesium-plugin-lanes --dry-run --lanes godot-host-mac",
            "capture_focus": [
                "editor version",
                "host architecture",
                "addon revision",
                "macOS import/open or build proof",
            ],
        },
        {
            "surface": "Godot macOS Proof",
            "command": "cesium-godot-aggressive-launcher --native-target mac --dry-run",
            "capture_focus": [
                "macOS app bundle discovery",
                "Intel and Apple Silicon proof-ready ordering",
                "per-attempt screenshot contract",
                "the same launcher/report structure as Windows and Linux",
            ],
        },
        {
            "surface": "Visual Proof",
            "command": "cesium-visual-proof",
            "capture_focus": [
                "Windows-first capture order",
                "canonical camera poses",
                "proxy-earth and cesium-earth variants",
                "engine-specific screenshot output roots",
                "macOS arm64 and x86_64 separation",
                "normalized Unreal Saved/Screenshots output into the shared packet root",
                "the final screenshot packet contract before real capture automation lands",
            ],
        },
        {
            "surface": "Windows Visual Proof Bundle",
            "command": "cesium-windows-visual-proof",
            "capture_focus": [
                "one packet for the Unreal, Unity, and Godot Windows proof commands",
                "startup-health, normalization, and compare wiring",
                "the final Windows bundle before real host execution",
            ],
        },
        {
            "surface": "Windows Visual Proof Run",
            "command": "cesium-windows-visual-proof-run",
            "capture_focus": [
                "actual Unreal, Unity, and Godot launcher execution",
                "normalized proxy-earth and Cesium-earth capture roots",
                "the compare gate that proves the Windows lane is green",
            ],
        },
        {
            "surface": "Unreal Visual Proof",
            "command": "UnrealEditor.exe CesiumVanillaExample.uproject -NoEOS -ExecCmds=\"Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit\"",
            "manifest_path": "artifacts/reports/cesium_visual_proof/unreal/windows/x86_64/visual_proof_manifest.json",
            "proof_runner": {
                "type": "automation",
                "windows_tests": [
                    "Cesium.VisualProof.Windows.ProxyEarth",
                    "Cesium.VisualProof.Windows.CesiumEarth",
                ],
                "raw_capture_root": "extensions/cesium/examples/unreal/CesiumVanillaExample/Saved/Screenshots/WindowsEditor",
                "normalized_capture_root": "artifacts/reports/cesium_visual_proof/unreal/windows/x86_64",
                "normalize_command": "cesium-visual-proof-normalize --engine unreal --source-root \"extensions/cesium/examples/unreal/CesiumVanillaExample/Saved/Screenshots/WindowsEditor\" --capture-root \"artifacts/reports/cesium_visual_proof/unreal/windows/x86_64\" --native-target windows --architecture x86_64",
            },
            "capture_focus": [
                "Cesium.VisualProof.Windows.ProxyEarth automation lane",
                "Cesium.VisualProof.Windows.CesiumEarth automation lane",
                "Saved/Screenshots/WindowsEditor capture output",
                "cesium-visual-proof-normalize into artifacts/reports/cesium_visual_proof/unreal/windows/x86_64",
                "manifest-backed proof root beside the normalized PNGs",
                "canonical proxy-earth and cesium-earth camera poses",
                "the Unreal Windows proof runner that now matches the other engines",
            ],
        },
        {
            "surface": "Unreal Visual Proof Report",
            "command": "cesium-unreal-visual-proof",
            "capture_focus": [
                "commandable Unreal Windows visual-proof payload",
                "raw screenshot root and normalized capture root",
                "manifest-backed packet entry for the Unreal runner",
                "upstream CesiumVisualProof.spec.cpp harness in external/cesium/cesium-unreal",
            ],
        },
        {
            "surface": "Visual Proof Compare",
            "command": "cesium-visual-proof-compare",
            "capture_focus": [
                "perceptual image drift detection",
                "black or gray frame failure detection",
                "cross-engine canonical shot comparisons",
                "the screenshot quality gate that defends the packet",
            ],
        },
    ]
