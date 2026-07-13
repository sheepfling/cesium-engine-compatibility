# Cesium Example Standard

This document defines the repo-owned pure-Cesium example-project quality bar for Cesium
across Unreal, Unity, and Godot.

It is intentionally separate from the vendor-plugin lane.

## Why Split It

Two different questions matter:

1. does the upstream Cesium plugin install and open on the engine versions we support
2. do we ship a clean pure-Cesium example project that proves the vendor route well

The first question belongs to the vendor lane.
The second question belongs to the example lane.

For Cesium specifically, every supported engine path should have both lanes:

1. `Vendor lane`
   Plugin/package/addon compatibility on the supported engine version.
2. `Example lane`
   A repo-owned pure-Cesium small project that uses that vendor lane as a prerequisite.

We should not let a good upstream plugin hide a weak example project, and we
should not let a weak sample repo imply the plugin-core route is broken.

## Required Bar

Every Cesium example lane should prove:

1. `Open`
   The project opens cleanly on the supported engine version.
2. `Install`
   The Cesium plugin/package/addon is installed and enabled through a short,
   rerunnable setup path.
3. `Scene`
   A known geospatial scene loads with a predictable camera start.
4. `Purity`
   The project stays pure Cesium for this proof stage and does not require
   FastDIS or other repo-specific runtime plugins.
5. `Demo`
   A junior operator can run the example with a short documented flow.
6. `Proof`
   The lane emits a report showing setup state, plugin state, and scene/demo
   status.

## Current Engine Targets

- Unreal: first-class example lane target
- Unity: first-class example lane target
- Godot: first-class example lane target, but on a narrower current Cesium-style
  plugin surface

## Current Readiness Policy

- `Cesium Unreal Example` should be built after the Unreal version matrix is
  green for both the Windows proof lane and the Linux Docker proof lane.
  Linux stays a separate host/toolchain proof lane and is tracked in
  `docs/CESIUM_UNREAL_LINUX_NOTES.md`.
- `Cesium Unity Example` should be built after the pinned editor lane is
  verified. For now that lane is `6000.5.0f1`, while the repo-owned example
  project file itself has moved to `6000.6.0b2`. Forward/backward editor drift
  stays tracked separately in `docs/CESIUM_UNITY_6000_5_FINDINGS.md`, and the
  current Unity version and package story are tracked in
  `docs/CESIUM_UNITY_VERSION_MATRIX.md`.
- `Cesium Godot Example` should be built after the Godot vendor doctor grows
  into a scratch-project import/open smoke. For now, the Windows-native lane
  is pinned to `4.7` and tracked in
  `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`. The four Windows evidence
  builds are tracked in `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`. Linux
  evidence is tracked in `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`. Linux
  and macOS proof routes share the same source route but are tracked
  separately in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`.

## Operator Flow

Start with:

```bash
cesium-prepare-source-route
cesium-example doctor --engine unreal
cesium-example doctor --engine unity
cesium-example doctor --engine godot
cesium-godot-doctor
```

These doctor lanes are planning/quality gates over real repo-owned pure-Cesium example
project scaffolds. They still need live runtime automation to become full proof
lanes.

## Segregation Rule

If a lane needs a version-specific project variant, do not patch the base
example scaffold in place.

Create a separate project root, keep the generated state ignored there too, and
record the split in [`docs/CESIUM_PROJECT_SEGREGATION.md`](../../../docs/CESIUM_PROJECT_SEGREGATION.md).

When you mark a project as version-specific, keep the descriptor and proof
harness files tracked in that versioned root and keep the machine output ignored
there:

- Unreal: `.uproject`, `Config/*.ini`, and `Source/*Target.cs`
- Unity: `ProjectSettings/ProjectVersion.txt`, `ProjectSettings/*.asset`, and
  `Assets/Editor/*.cs`
- Godot: `project.godot`, `export_presets.cfg`, and `scenes/` and `scripts/`
