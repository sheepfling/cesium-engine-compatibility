# Cesium Engine Matrix

- status: `partial`
- generated_at: `2026-07-08T22:04:57.530073+00:00`
- lane_count: `7`

The matrix unions Windows-native, Linux native or Docker-proxy, and host-only evidence into a single packet-friendly compatibility picture, with evidence tiers separating verified lanes from planned lanes, the discovered Unity install spread staying visible beside the planned macOS and Linux targets, and the Unity proof lane remaining pinned to 6000.5.0f1.

## Claim Boundaries

- Verified lanes are the ones we can defend today; planned lanes stay explicitly labeled so the matrix never pretends a gap is green.
- Unreal Linux Docker is verified on this host, while the source-built Linux support tree remains an upstream-parity follow-up.
- The target goal spans Unreal, Unity, and Godot across Windows, Linux native or Docker proxy, and macOS on both Intel `x86_64` and Apple Silicon `arm64` where the engine supports both.
- Unity Linux/Docker has live Docker report evidence but still waits on build-green proof, Unity macOS remains planned, and Godot macOS remains a commandable proof route.
- The matrix unions Windows-native, Linux native or Docker-proxy, and host-only evidence into one packet-friendly view of the current compatibility picture.

## Engine-by-Platform Matrix

| Engine | Windows | Linux | macOS Intel `x86_64` | macOS Apple Silicon `arm64` | Notes |
| --- | --- | --- | --- | --- | --- |
| Unreal | verified | verified | planned | planned | Linux uses native or Docker evidence; macOS remains a follow-up proof lane. |
| Unity | verified | planned | planned | planned | Windows is the current proof anchor; Linux/Docker and macOS remain planned. |
| Godot | verified | verified | planned | planned | Windows and Linux are covered; macOS remains the next platform gap. |

## Packet Graph

- `cesium-unity-native-matrix`
- `cesium-execution-audit`
- `cesium-planned-routes`
- `cesium-compatibility-packet`

## Packet Status

- `unity_native_matrix`: `partial` -> `artifacts/reports/unity_native_matrix/unity_native_matrix.json`
- `execution_audit`: `present` -> `artifacts/reports/cesium_execution_audit/cesium_execution_audit.json`
- `planned_routes`: `present` -> `artifacts/reports/cesium_planned_routes/cesium_planned_routes.json`
- `compatibility_packet`: `present` -> `artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json`

## Evidence

- `unreal-windows`: `version_matrix` -> `docs/UNREAL_VERSION_MATRIX.md`
- `unreal-linux`: `linux_notes` -> `docs/CESIUM_UNREAL_LINUX_NOTES.md`
- `unity-windows`: `version_matrix` -> `docs/CESIUM_UNITY_VERSION_MATRIX.md`
- `unity`: `findings` -> `docs/CESIUM_UNITY_6000_5_FINDINGS.md`
- `unity-native`: `native_matrix` -> `artifacts/reports/unity_native_matrix/unity_native_matrix.json`
- `unity-linux-docker`: `docker_report` -> `artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json`
- `godot-linux-docker`: `docker_report` -> `artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.json`
- `godot-windows`: `version_matrix` -> `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`
- `godot-linux`: `version_matrix` -> `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`
- `godot-mac`: `cross_platform_notes` -> `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`
- `packet-summary`: `review_packet` -> `docs/CESIUM_PR_PACKET_SUMMARY.md`

## Gaps

- Unity Linux/Docker remains planned.
- Godot macOS remains planned.
- Unity macOS remains planned.

## Lane Table

| Lane | Engine | Target | Evidence | Status | Versions |
| --- | --- | --- | --- | --- | --- |
| unreal-windows | unreal | default | verified | ok | 5.7, 5.8 |
| unreal-linux | unreal-linux | default | verified | verified | 5.7, 5.8 |
| unity-windows | unity | default | verified | ok | 6000.5.2f1, 6000.3.19f1, 6000.6.0b2 |
| unity-linux-docker | unity | linux | planned | planned | 6000.5.2f1, 6000.3.19f1, 6000.6.0b2 |
| godot-windows | godot | windows | verified | ok | 4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1 |
| godot-linux | godot | linux | verified | ok | 4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1 |
| godot-mac | godot | mac | planned | planned | 4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1 |

## Summary

- verified_lane_count: `5`
- planned_lane_count: `2`
- evidence_count: `11`
- unreal: `5.7, 5.8`
- unity: `6000.6.0b2`
- unity_proof_lane: `6000.5.0f1`
- unity_example_project_version: `6000.6.0b2`
- unity_installed: `6000.5.2f1, 6000.3.19f1, 6000.6.0b2`
- unity_linux_docker_planned: `cesium-unity-linux-docker --native-target linux, cesium-unity-native-matrix, cesium-plugin-lanes --dry-run --lanes unity-host-linux-docker`
- unity_mac_planned: `cesium-plugin-lanes --dry-run --lanes unity-host-mac, cesium-capture-unity-host-report --native-target mac, cesium-stage-unity-host-report --overwrite, cesium-export-unity-host-handoff`
- godot_windows: `4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1`
- godot_linux: `4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1`
- godot_mac_planned: `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
- unreal_linux: `5.7, 5.8`

## Build Plans

### unreal-windows

- `cesium-example report --engine unreal`
- `cesium-example report --engine unreal --format json`

### unreal-linux

- `cesium-unreal-linux-docker build-plan --engine-version 5.7`
- `cesium-unreal-linux-docker build-plan --engine-version 5.8`
- `cesium-unreal-linux-docker build --engine-version 5.8`

### unity-windows

- `cesium-capture-unity-host-report --native-target windows`
- `cesium-stage-unity-host-report`
- `cesium-export-unity-host-handoff`
- `cesium-import-unity-host-report dist/unity_host_handoff/cesium-unity-host-handoff.zip`

### unity-linux-docker

- `cesium-unity-linux-docker --native-target linux`
- `cesium-plugin-lanes --dry-run --lanes unity-host-linux-docker`
- `cesium-unity-native-matrix`

### godot-windows

- `cesium-example report --engine godot --native-target windows`
- `cesium-example doctor --engine godot --native-target windows`

### godot-linux

- `cesium-example report --engine godot --native-target linux`
- `cesium-example doctor --engine godot --native-target linux`

### godot-mac

- `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
- `cesium-example report --engine godot --native-target mac`
- `cesium-example doctor --engine godot --native-target mac`


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
