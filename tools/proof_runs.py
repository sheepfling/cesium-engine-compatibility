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
    ]
