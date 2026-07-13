# Cesium Cross-Platform Fix Notes

- status: `partial`
- generated_at: `2026-07-08T22:01:52.282899+00:00`

## Claim Boundaries

- This note turns the current matrix, audit, and planned-routes packets into a reviewer-facing checklist.
- The table is meant to be evidence-driven, not a substitute for live build proof.
- Unreal Windows coverage exists for `5.7` and `5.8`.
- Unreal Windows visual proof now has an explicit runner entry that names the `Cesium.VisualProof.Windows.ProxyEarth` and `Cesium.VisualProof.Windows.CesiumEarth` automation tests and the normalized `Saved/Screenshots/WindowsEditor` root.
- The overall goal spans Unreal, Unity, and Godot across Windows, Linux native or Docker proxy, and macOS on both Intel `x86_64` and Apple Silicon `arm64` where supported.
- Planned macOS and Unity Linux/Docker work remains explicit rather than folded into the verified lanes.
- The note is intentionally aligned to the current packet state so it can be regenerated from the same evidence.

## Packet Graph

- `cesium-engine-matrix`
- `cesium-unity-native-matrix`
- `cesium-execution-audit`
- `cesium-planned-routes`
- `cesium-compatibility-packet`

## Packet Status

- `engine_matrix`: `partial` -> `artifacts/reports/cesium_engine_matrix/cesium_engine_matrix.json`
- `unity_native_matrix`: `partial` -> `artifacts/reports/unity_native_matrix/unity_native_matrix.json`
- `execution_audit`: `partial` -> `artifacts/reports/cesium_execution_audit/cesium_execution_audit.json`
- `planned_routes`: `dry-run` -> `artifacts/reports/cesium_planned_routes/cesium_planned_routes.json`
- `compatibility_packet`: `present` -> `artifacts/reports/cesium_compatibility_packet/cesium_compatibility_packet.json`

## Version Coverage

| Engine | Version | Windows | Linux Docker | macOS | Notes |
| --- | --- | --- | --- | --- | --- |
| Unreal | `5.7` | `verified` | `verified` | `planned` | Baseline or forward verification lane. |
| Unreal | `5.8` | `verified` | `verified` | `planned` | Baseline or forward verification lane. |
| Godot | `4.6.3-stable` | `verified` | `verified` | `planned` | Windows/Linux coverage with macOS still planned. |
| Godot | `4.7-stable` | `verified` | `verified` | `planned` | Windows/Linux coverage with macOS still planned. |
| Godot | `4.7.1-rc1` | `verified` | `verified` | `planned` | Windows/Linux coverage with macOS still planned. |
| Godot | `4.8-dev1` | `verified` | `verified` | `planned` | Windows/Linux coverage with macOS still planned. |
| Unity | `6000.3.19f1` | `verified` | `planned` | `planned` | Installed-editor spread kept visible for backward/forward notes. |
| Unity | `6000.5.2f1` | `verified` | `planned` | `planned` | Installed-editor spread kept visible for backward/forward notes. |
| Unity | `6000.6.0b2` | `verified` | `planned` | `planned` | Installed-editor spread kept visible for backward/forward notes. |

## Evidence Map

| Engine | Version family | Backing evidence | Current commandable path |
| --- | --- | --- | --- |
| Unreal | 5.7 / 5.8 | docs/UNREAL_VERSION_MATRIX.md; docs/CESIUM_UNREAL_LINUX_NOTES.md | `cesium-unreal-linux-docker build-plan --engine-version 5.8` |
| Unity | 6000.3.19f1 / 6000.5.2f1 / 6000.6.0b2 | docs/CESIUM_UNITY_VERSION_MATRIX.md; docs/CESIUM_UNITY_6000_5_FINDINGS.md; artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json | `cesium-unity-linux-docker --native-target linux` |
| Godot | 4.6.3-stable / 4.7-stable / 4.7.1-rc1 / 4.8-dev1 | docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md; docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md; docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md; docs/CESIUM_PLANNED_ROUTES.md; artifacts/reports/cesium_planned_routes/cesium_planned_routes.json | `cesium-plugin-lanes --dry-run --lanes godot-host-mac` |

## Remaining Fix Work

- Keep the Unreal Linux source-built support-tree story explicit.
- Unity Linux/Docker still needs a build-green proof on a host/container combination that discovers an editor.
- Unity macOS remains a planned native proof lane.
- Godot macOS remains the next live proof gap.

## Commandable Follow-Ups

- `cesium-unreal-linux-docker build-plan --engine-version 5.8`
- `cesium-unity-linux-docker --native-target linux`
- `cesium-plugin-lanes --dry-run --lanes unity-host-mac`
- `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
- `cesium-planned-routes`

## Reference Artifacts

- `docs/CESIUM_ENGINE_MATRIX.md`
- `docs/CESIUM_EXECUTION_AUDIT.md`
- `docs/CESIUM_PLANNED_ROUTES.md`
- `docs/CESIUM_PR_PACKET_SUMMARY.md`

## Summary

- matrix_status: `partial`
- unity_native_status: `partial`
- audit_status: `partial`
- planned_routes_status: `dry-run`
- verified_lane_count: `5`
- planned_lane_count: `2`
- evidence_count: `3`

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
