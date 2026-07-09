# Cesium Planned Routes

This note points to the dedicated dry-run packet for the remaining cross-platform bootstrap routes.

Use this command to regenerate the packet:

```bash
cesium-planned-routes
```

## What It Covers

- Unreal Linux parity follow-up routes
- Unity Linux/Docker planned proof routes
- Unity macOS planned proof routes
- Godot macOS planned proof routes
- the shared host-root discovery used for bootstrap on a fresh machine

- status: `dry-run`
- generated_at: `2026-07-08T22:06:42.466988+00:00`

## Claim Boundaries

- This packet records the remaining planned routes as a commandable dry-run bundle, not as build-green proof.
- Unreal Linux parity, Unity Linux/Docker, Unity macOS, and Godot macOS stay explicit and separate.
- The broader engine goal still spans Unreal, Unity, and Godot across Windows, Linux native or Docker proxy, and macOS on both Intel `x86_64` and Apple Silicon `arm64`.
- The bundle keeps the fresh-host bootstrap story tied to the same runner shape used by the rest of the compatibility packet.
- A dry-run packet can prove commandability and inventory without pretending the underlying lane has passed.

## Host Roots

- unreal_public_roots: `C:\Users\Public\Unreal, C:\Program Files\Epic Games`
- unity_public_roots: `C:\Users\Public\Unity, C:\Program Files\Unity\Hub\Editor`
- godot_public_roots: `C:\Users\Public\Godot`

## Packet Graph

- `cesium-engine-matrix`
- `cesium-execution-audit`
- `cesium-compatibility-packet`

## Packet Status

- `engine_matrix`: `partial` -> `artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json`
- `execution_audit`: `partial` -> `artifacts/reports/cesium_execution_audit/cesium_execution_audit.json`
- `compatibility_packet`: `present` -> `artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json`

## Evidence

- `planned-routes`: `dry_run_bundle` -> `artifacts/reports/cesium_lane_runner/cesium_plugin_lanes.json`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version 5.7`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build --engine-version 5.7`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version 5.8`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build --engine-version 5.8`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_5_2f1`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_3_19f1`
- `cross-platform-planned`: `planned_command` -> `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_6_0b2`
- `cross-platform-planned`: `planned_command` -> `cesium-capture-unity-host-report --unity-version 6000.5.2f1 --native-target mac --out-dir artifacts/reports/unity_host_6000_5_2f1`
- `cross-platform-planned`: `planned_command` -> `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_5_2f1 --host-label local-host-6000_5_2f1 --overwrite`
- `cross-platform-planned`: `planned_command` -> `cesium-capture-unity-host-report --unity-version 6000.3.19f1 --native-target mac --out-dir artifacts/reports/unity_host_6000_3_19f1`
- `cross-platform-planned`: `planned_command` -> `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_3_19f1 --host-label local-host-6000_3_19f1 --overwrite`
- `cross-platform-planned`: `planned_command` -> `cesium-capture-unity-host-report --unity-version 6000.6.0b2 --native-target mac --out-dir artifacts/reports/unity_host_6000_6_0b2`
- `cross-platform-planned`: `planned_command` -> `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_6_0b2 --host-label local-host-6000_6_0b2 --overwrite`
- `cross-platform-planned`: `planned_command` -> `cesium-export-unity-host-handoff`
- `cross-platform-planned`: `planned_command` -> `cesium-example report --engine godot --native-target mac`

## Bundle

- overall_status: `dry-run`
- selected_lanes: `cross-platform-planned`
- log_dir: `C:\Users\peanu\GIT\sheepfling\cesium-engine-compatibility\artifacts\reports\cesium_lane_runner\logs`

| Lane | Status | Kind |
| --- | --- | --- |
| `cross-platform-planned` | `dry-run` | `bundle` |

### Commands

- `cross-platform-planned`
  - `unreal-linux-build-plan-5_7`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version 5.7`
  - `unreal-linux-build-5_7`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build --engine-version 5.7`
  - `unreal-linux-build-plan-5_8`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build-plan --engine-version 5.8`
  - `unreal-linux-build-5_8`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unreal_linux_docker build --engine-version 5.8`
  - `unity-linux-docker-6000_5_2f1`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_5_2f1`
  - `unity-linux-docker-6000_3_19f1`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_3_19f1`
  - `unity-linux-docker-6000_6_0b2`: `dry-run`
    - `'C:\Users\peanu\scoop\apps\python313\current\python.exe' -m extensions.cesium.tools.unity_linux_docker --native-target linux --docker-log-mode tee --log-tail-lines 120 --timeout-seconds 900 --preserve --preserve-label unity-linux-6000_6_0b2`
  - `unity-capture-6000_5_2f1`: `dry-run`
    - `cesium-capture-unity-host-report --unity-version 6000.5.2f1 --native-target mac --out-dir artifacts/reports/unity_host_6000_5_2f1`
  - `unity-stage-6000_5_2f1`: `dry-run`
    - `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_5_2f1 --host-label local-host-6000_5_2f1 --overwrite`
  - `unity-capture-6000_3_19f1`: `dry-run`
    - `cesium-capture-unity-host-report --unity-version 6000.3.19f1 --native-target mac --out-dir artifacts/reports/unity_host_6000_3_19f1`
  - `unity-stage-6000_3_19f1`: `dry-run`
    - `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_3_19f1 --host-label local-host-6000_3_19f1 --overwrite`
  - `unity-capture-6000_6_0b2`: `dry-run`
    - `cesium-capture-unity-host-report --unity-version 6000.6.0b2 --native-target mac --out-dir artifacts/reports/unity_host_6000_6_0b2`
  - `unity-stage-6000_6_0b2`: `dry-run`
    - `cesium-stage-unity-host-report --source-dir artifacts/reports/unity_host_6000_6_0b2 --host-label local-host-6000_6_0b2 --overwrite`
  - `unity-export`: `dry-run`
    - `cesium-export-unity-host-handoff`
  - `godot-report-mac-4_6_3_stable`: `dry-run`
    - `cesium-example report --engine godot --native-target mac`
  - `godot-report-mac-4_7_stable`: `dry-run`
    - `cesium-example report --engine godot --native-target mac`
  - `godot-report-mac-4_7_1_rc1`: `dry-run`
    - `cesium-example report --engine godot --native-target mac`
  - `godot-report-mac-4_8_dev1`: `dry-run`
    - `cesium-example report --engine godot --native-target mac`

## Summary

- bundle_lane_count: `1`
- bundle_task_count: `18`
- bundle_command_count: `18`
- bundle_lane_ids: `cross-platform-planned`

## Next Proof Runs

- `Unreal`: `cesium-unreal-linux-docker build-plan --engine-version 5.8`
  - source-built Linux support tree for upstream parity
  - --linux-platform-support-root
  - toolchain details
- `Cross-Platform Planned`: `cesium-plugin-lanes --dry-run --lanes cross-platform-planned`
  - refresh the dedicated planned-routes packet
  - bundle the planned Unreal Linux, Unity Linux/Docker, Unity macOS, and Godot macOS routes
  - show the command inventory for a fresh-host bootstrap
  - keep the remaining planned lanes commandable without guessing
- `Unity`: `cesium-unity-native-matrix`
  - installed editor spread
  - pinned versus forward editor versions
  - native target coverage
  - live Cesium package-route proof
- `Unity Docker`: `cesium-unity-linux-docker --native-target linux`
  - docker image
  - container logs
  - inner matrix payload
  - Linux target proof route
- `Godot Docker`: `cesium-godot-linux-docker --native-target linux`
  - docker image
  - container logs
  - inner report payload
  - Linux target proof route
- `Godot`: `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
  - editor version
  - host architecture
  - addon revision
  - macOS import/open or build proof
