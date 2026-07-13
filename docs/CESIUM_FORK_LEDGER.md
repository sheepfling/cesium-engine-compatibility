# Cesium Fork Ledger

This note collects the Cesium-specific code changes and documentation trail that
matter for upstream-facing forks and PRs.

Use it as the branch-level index for the lane notes already captured elsewhere
in the repo. The canonical version-and-host structure now lives in
[Cesium Compatibility Notebook](./CESIUM_COMPATIBILITY_NOTEBOOK.md).

## What Is Already Documented

- [Cesium compatibility notebook](./CESIUM_COMPATIBILITY_NOTEBOOK.md)
- [Cesium proof strategy](./CESIUM_PROOF_STRATEGY.md)
- [Cesium source route](../extensions/cesium/docs/CESIUM_SOURCE_ROUTE.md)
- [Cesium fork push plan](./research/CESIUM_FORK_PUSH_PLAN.md)
- [Cesium fork workpack](./CESIUM_FORK_WORKPACK.md)
- [Cesium example standard](../extensions/cesium/docs/CESIUM_EXAMPLE_STANDARD.md)
- [Unreal version matrix](./UNREAL_VERSION_MATRIX.md)
- [Unreal Linux notes](./CESIUM_UNREAL_LINUX_NOTES.md)
- [Unity 6000.5 findings](./CESIUM_UNITY_6000_5_FINDINGS.md)
- [Unity version matrix](./CESIUM_UNITY_VERSION_MATRIX.md)
- [Godot 4.7 Windows build notes](./CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md)
- [Godot Windows version matrix](./CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md)
- [Godot Linux version matrix](./CESIUM_GODOT_LINUX_VERSION_MATRIX.md)
- [Godot cross-platform notes](./CESIUM_GODOT_CROSS_PLATFORM_NOTES.md)
- [Cesium engine matrix](./CESIUM_ENGINE_MATRIX.md)
- [Cesium plugin lane runner](../tools/run_cesium_plugin_lanes.py)
- [Cesium fork workpack command](../tools/build_cesium_fork_workpack.py)

## Code Changes By Lane

### Shared Repo Boundary Work

Goal:

- keep generic orchestration out of the Cesium subtree
- keep product-specific Cesium work inside the Cesium tree
- keep Cesium-only policy and lane glue isolated from unrelated repo logic

The practical outputs of that boundary work are:

- the Cesium extension subtree for Cesium-specific workflow and example policy
- workspace-manifest route separation for vendor lanes versus example lanes
- report and artifact plumbing that records the exact lane, host, and proof shape

These changes stay in this repo. They are not vendor-fork patches.

### Unreal

Documented Unreal work is split between host/toolchain handling and Cesium
plugin compatibility.

Known code changes and report updates:

- Unreal 5.7 and 5.8 lane detection and proof reporting
- Windows toolchain selection/reporting for the 5.8 lane
- Linux Docker proof wrapper and cache/report hygiene
- exact selected compiler/version recording for reproducible doctor output
- install-smoke and matrix reporting for Cesium Unreal

Lane split:

- Windows 5.7/5.8 is the main Unreal plugin proof lane.
- Unreal Windows 5.8 is visually complete for the current proof packet: the
  source build, automation test, tileset population, and six normalized images
  all pass.
- Linux Docker is the repeatable host proof lane for Unreal 5.8.
- The Unreal source fixes belong in `CesiumGS/cesium-unreal`.
- The repo workflow/reporting changes stay here.

Where to look:

- `extensions/cesium/tools/prepare_cesium_source_route.py`
- `extensions/cesium/tools/cesium_example_workflow.py`
- `extensions/cesium/tools/unreal_linux_lane.py`
- `docs/CESIUM_PROOF_STRATEGY.md`
- `docs/UNREAL_VERSION_MATRIX.md`

Upstream fork target:

- `CesiumGS/cesium-unreal`

### Unity

Unity work currently has the clearest documented fix packet.

Known code changes and report updates:

- Reinterop staging no longer relies on the stub publish artifact
- source-route prep now stages the real compiled Reinterop assembly
- Unity 6000.5 editor API drift is captured as a distinct blocker
- import/compile smoke and failure reporting are normalized
- Unity version/package drift is tracked in a repo-owned version matrix
- Unity install discovery now includes the public Unity roots used for host bootstrap
- Unity native target lanes are carried explicitly as windows, linux, and mac

Lane split:

- the vendor source fix packet belongs in `CesiumGS/cesium-unity`
- the repo workflow/reporting changes stay here
- the current blocker is a real Unity 6000.5 source/API drift issue, not a
  generic packaging failure
- Unity Windows is **not visually complete**: the current Cesium-earth images
  do not show an acceptable populated Cesium globe, even though the bootstrap
  manifest and fallback-player gates pass.

Where to look:

- `extensions/cesium/tools/prepare_cesium_source_route.py`
- `extensions/cesium/tools/cesium_example_workflow.py`
- `docs/CESIUM_UNITY_6000_5_FINDINGS.md`
- `docs/CESIUM_UNITY_VERSION_MATRIX.md`
- `docs/CESIUM_SOURCE_ROUTE.md`

Upstream fork target:

- `CesiumGS/cesium-unity`

### Godot

Godot now has Windows and Linux evidence notes plus cross-platform proof notes.

Known code changes and report updates:

- Windows 4.7 build lane fix in `SCsub`
- proof runner normalization for report tails and command capture
- Linux Docker proof wrapper for repeatable headless verification
- cache and path hygiene for SCons, CMake, and vcpkg retries

Lane split:

- the vendor source fix packet belongs in `Battle-Road-Labs/3D-Tiles-For-Godot`
- the repo workflow/reporting changes stay here
- Windows and Linux are both part of the same Godot compatibility story, but
  they produce separate proof packets
- Godot Windows is **not visually complete**: the current Cesium-earth images
  do not show an acceptable populated Cesium globe, so the proxy/bootstrap
  evidence must not be treated as final Cesium proof.

Where to look:

- `extensions/cesium/tools/prepare_cesium_source_route.py`
- `extensions/cesium/tools/cesium_example_workflow.py`
- `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`
- `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`
- `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`
- `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`
- `docs/CESIUM_PROOF_STRATEGY.md`

Upstream fork target:

- `Battle-Road-Labs/3D-Tiles-For-Godot`

## What This Means For Forks

The repo is now organized enough to branch the upstream fixes separately:

- one fork/PR packet for Cesium Unreal
- one fork/PR packet for Cesium Unity
- one fork/PR packet for Battle Road Godot

Recommended fork targets:

- [sheepfling/cesium-unreal](https://github.com/sheepfling/cesium-unreal) for
  Unreal 5.7, Unreal 5.8, and Unreal Linux source and packaging compatibility
  issues
- [sheepfling/cesium-unity](https://github.com/sheepfling/cesium-unity) for
  Unity 6000.5 Reinterop and editor API drift
- [sheepfling/3D-Tiles-For-Godot](https://github.com/sheepfling/3D-Tiles-For-Godot)
  for the Godot 4.7 SCsub and native build fixes

The fork packets should preserve:

- the Cesium workspace commit that the work was based on
- exact engine version
- host and toolchain
- command used
- failure class or success proof
- log tail and artifact paths

## Short Answer

Yes, we have clear notes for the next agent to pull and fork the right repo:

- Unreal: fork [sheepfling/cesium-unreal](https://github.com/sheepfling/cesium-unreal),
  using the Unreal lane notes and the Windows/Linux split above
- Unity: fork [sheepfling/cesium-unity](https://github.com/sheepfling/cesium-unity),
  using the Unity 6000.5 findings note
- Godot: fork [sheepfling/3D-Tiles-For-Godot](https://github.com/sheepfling/3D-Tiles-For-Godot),
  using the Godot 4.7 build notes, the Windows and Linux matrices, and the cross-platform notes

This repo keeps the orchestration, matrix, and reporting changes.
The vendor repos get the source-fix PRs.

## Version Anchors

The notes are now expected to cite these source anchors explicitly:

- Cesium for Unreal: `2.28.0`
- Cesium for Unity: `1.24.0`
- Godot route: commit-tracked `Battle-Road-Labs/3D-Tiles-For-Godot`

When the vendor version is semver-based, cite the package/version field.
When it is commit-tracked, cite the checkout commit and branch in the workpack.

## Remaining Gap

The documentation is now sufficient to start creating per-repo forks, but the
lane notes are still distributed across multiple files. This ledger is the
branch-level index; the detailed evidence still lives in the per-lane docs.
