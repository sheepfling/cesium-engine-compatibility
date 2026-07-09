# Cesium Execution Audit

The live audit command is `cesium-execution-audit`.

- overall_status: `partial`
- generated_at: `2026-07-08T22:04:57.808727+00:00`
- docker_available: `True`
- unreal_public_roots: `C:\Users\Public\Unreal, C:\Program Files\Epic Games`
- unity_public_roots: `C:\Users\Public\Unity, C:\Program Files\Unity\Hub\Editor, D:\Unity\Hub\Editor`
- godot_public_roots: `C:\Users\Public\Godot`

## Claim Boundaries

- The audit unions host availability, public search roots, and next-proof commands into one packet-friendly readiness picture.
- Unreal Linux Docker is verified on this host, while the source-built Linux support tree story remains an upstream-parity follow-up.
- Unity Linux/Docker now has a live Docker report, while the Windows host route still carries the current proof lane evidence and Unity macOS remains planned.
- Godot Windows and Linux are verified; Godot macOS remains the next proof gap.
- The planned-routes packet keeps the remaining cross-platform bootstrap bundle commandable without claiming any of those routes are build-green.

## Packet Graph

- `cesium-engine-matrix`
- `cesium-unity-native-matrix`
- `cesium-planned-routes`
- `cesium-compatibility-packet`

## Packet Status

- `engine_matrix`: `partial` -> `artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json`
- `unity_native_matrix`: `partial` -> `artifacts/reports/unity_native_matrix/unity_native_matrix.json`
- `planned_routes`: `present` -> `artifacts/reports/cesium_planned_routes/cesium_planned_routes.json`
- `compatibility_packet`: `present` -> `artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json`

## Evidence

- `unreal`: `version_matrix` -> `docs/UNREAL_VERSION_MATRIX.md`
- `unreal`: `linux_notes` -> `docs/CESIUM_UNREAL_LINUX_NOTES.md`
- `unity`: `version_matrix` -> `docs/CESIUM_UNITY_VERSION_MATRIX.md`
- `unity`: `findings` -> `docs/CESIUM_UNITY_6000_5_FINDINGS.md`
- `unity`: `docker_report` -> `artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json`
- `godot`: `docker_report` -> `artifacts/reports/godot_linux_docker/cesium-godot_linux_docker.json`
- `godot`: `windows_version_matrix` -> `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`
- `godot`: `linux_version_matrix` -> `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`
- `planned-routes`: `dry_run_bundle` -> `artifacts/reports/cesium_planned_routes/cesium_planned_routes.json`
- `packet-summary`: `review_packet` -> `docs/CESIUM_PR_PACKET_SUMMARY.md`

## Gaps

- Unity Linux/Docker remains planned.
- Unity macOS remains planned.
- Godot macOS remains planned.

## Readiness

- `unreal_linux_docker`: `True`
- `unity_host`: `True`
- `godot_windows`: `True`
- `godot_linux`: `True`

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

## Unreal

- versions: `5.7, 5.8`
- docker_preflight: `available`
- linux_docker_report_status: `verified`
- linux_docker_build_status: `verified`
- linux_docker_blocker: `none`
- linux_platform_support_search_roots:
  - C:\Users\Public\Unreal\Engine\Platforms\Linux
  - C:\Program Files\Epic Games\Engine\Platforms\Linux
- linux_platform_support_ready: `False`
- public_unreal_archives:
  - C:\Users\Public\Unreal\engines\linux\Linux_Unreal_Engine_5.7.4.zip
  - C:\Users\Public\Unreal\engines\linux\Linux_Unreal_Engine_5.8.0.zip
- selected_source: `non-linux-host`

## Unity

- versions: `6000.5.2f1, 6000.3.19f1, 6000.6.0b2`
- installed host spread: `6000.5.2f1, 6000.3.19f1, 6000.6.0b2`
- proof lane: `6000.5.0f1`
- proof_lane_version: `6000.5.0f1`
- current example-project version: `6000.6.0b2`
- example_project_version: `6000.6.0b2`
- host_capture_ready: `True`
- host_status: `verified`
- linux_docker_status: `planned`
Unity Linux/Docker still a planned proof lane.
Windows host coverage for Unity is represented by the installed host spread.
Unity Linux/Docker lane now has a live Docker report artifact.
Unity macOS remains planned as the other native gap, and the lane remains planned for the same reason.
- linux_docker_plan: `cesium-unity-linux-docker --native-target linux; cesium-unity-native-matrix`
- latest_example_build_failure_signals:
  - Package Manager tried to write under the installed editor tree and hit EPERM.
  - Unity licensing still hits BIOS lookup denial and mutex contention on this host.
That planned route is now commandable as `cesium-unity-linux-docker --native-target linux`, which keeps the future proof path in the same lane bundle as the rest of the host evidence.

## Godot

- windows_versions: `4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1`
- linux_versions: `4.6.3-stable, 4.7-stable, 4.7.1-rc1, 4.8-dev1`
- windows_status: `verified`
- linux_status: `verified`
- mac_status: `planned`
