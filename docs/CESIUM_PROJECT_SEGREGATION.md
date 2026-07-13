# Cesium Project Segregation

This note defines how repo-owned example projects should be split when engine
versions or proof lanes need to diverge.

## Core Rule

Keep the base example scaffold stable.

If a lane needs engine-version-specific, host-specific, or renderer-specific
mutation, create a separate project root instead of mutating the base scaffold
in place.

That is especially important for Unreal, which tends to be picky about project
structure, generated files, and version drift.

## Base Scaffolds

These are the canonical repo-owned example roots:

- `extensions/cesium/examples/unreal/CesiumVanillaExample`
- `extensions/cesium/examples/unity/CesiumVanillaExample`
- `extensions/cesium/examples/godot/CesiumVanillaExample`

## Version-Specific Markers

Keep the files that describe the pinned version or the lane contract tracked in
the project root, and keep machine output ignored.

Typical tracked version markers are:

- Unreal: `.uproject`, `Config/*.ini`, and lane-specific target/build source
  files such as `Source/*Target.cs`
- Unity: `ProjectSettings/ProjectVersion.txt`, the pinned `ProjectSettings/*.asset`
  set, and proof harness code under `Assets/Editor/`
- Godot: `project.godot`, `export_presets.cfg`, and the proof harness under
  `scenes/` and `scripts/`

Typical ignored machine output remains:

- Unreal: `Binaries/`, `Build/`, `DerivedDataCache/`, `Intermediate/`,
  `Saved/`, `.vs/`
- Unity: `Library/`, `Logs/`, `Temp/`, `UserSettings/`, `build/`, generated
  proof helper assets
- Godot: `.godot/`, `build/`, `logs/`, local addon/runtime state

## When To Split

Create a separate project root when any of these change:

- the Unreal engine version or `.uproject` shape
- the Unity editor line when the example project file must stay pinned to a
  different version
- the Godot editor or addon compatibility line when the project layout needs a
  different baseline
- a proof lane needs its own generated assets, scene files, or serialized
  project metadata

## Recommended Pattern

Use a sibling project root or a lane-specific workpack/report tree.

Examples:

- `extensions/cesium/examples/unreal/CesiumVanillaExample_5_8`
- `artifacts/reports/<lane>/<version>/`
- `artifacts/workpacks/<lane>/<version>/`

## Ignore Rule

Every project root, including version-specific siblings, should carry its own
local ignore rules for editor/runtime churn.

## Reporting Rule

If a project is version-specific, mark that in the example README and the lane
notes.

Do not make the base scaffold silently carry version-specific state.
