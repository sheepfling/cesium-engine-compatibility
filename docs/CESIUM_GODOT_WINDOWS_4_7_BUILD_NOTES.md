# Godot Windows 4.7 Build Notes

This note tracks the repo-owned Godot native lane on Windows.

The current goal is to keep the 3D Tiles/Godot route honest about what works
on a Windows host and what still needs compatibility work as the 4.x series
changes. The four public Windows builds on this host are tracked in
`docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`. Linux evidence is tracked in
`docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`. Linux and macOS host differences
are tracked separately in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`.

The cross-platform notebook and fork workpack now hold the source-version and
host-architecture structure that the PR narrative should follow.

## Current Lane

- pinned editor family: `4.7`
- native target: `windows`
- repo-owned example project: `extensions/cesium/examples/godot/CesiumVanillaExample/`
- vendor route: `Battle-Road-Labs/3D-Tiles-For-Godot`
- versioning model: commit-tracked checkout, not a semver package
- default engine discovery prefers `C:\Users\Public\Godot` before falling
  back to the installed Godot binaries under the public engine tree

## Current Shape

The Godot example scaffold already includes:

- `project.godot`
- `scenes/Main.tscn`
- a forward-plus renderer setting for the Windows-native path

The source-route prep now falls back to the vendor repo's real default branch
when `main` is unavailable, which matters for this community route.

Public engine locations we should search first:

- `C:\Users\Public\Godot\engines\windows`
- `C:\Users\Public\Godot\engines\linux`

The discovery helper now matches the real public Windows Godot layout under
`Godot_v*_win64.exe`, which is why the host audit now reports the four local
Windows versions instead of an empty set.

## Compatibility Buckets

- forward compatibility
  - track Godot 4.x changes that affect Windows-native rendering, addon import,
    or export behavior
  - capture the first failing editor revision if a newer 4.x line breaks
- backward compatibility
  - track Godot 4.x changes that affect project parsing, addon loading, or
    serialized scene data
  - capture the first failing editor revision if an older 4.x line breaks

## What To Capture

When we have a live Windows-native smoke, record:

- exact Godot editor version
- vendor checkout commit
- host OS and architecture
- command used
- log tail or failure message
- whether the issue is import-time, editor-open, or scene/runtime related

## Windows Visual-Proof Fork Fix

The Cesium Godot fork used by the Windows proof lane contains a material-loader
compatibility fix that must be carried into the vendor PR:

```cpp
BaseMaterial3D::CullMode cullMode =
    cesiumMaterial.doubleSided
        ? BaseMaterial3D::CULL_DISABLED
        : BaseMaterial3D::CULL_BACK;
```

The prior `CULL_FRONT` path made ordinary one-sided glTF tile surfaces
disappear even though HTTP requests completed and `MeshInstance3D` nodes were
created. This is a source fix in the sibling `3D-Tiles-For-Godot` checkout,
not a project-only scene adjustment.

The current prebuilt Windows DLL predates that source change. Until it is
rebuilt, the proof harness uses a visible-material compatibility path for the
already-loaded mesh and records both `CESIUM_TILE_STATE` and
`CESIUM_PROOF_GEOMETRY_CLONED`. That fallback is not a rebuilt-fork
verification.

The rebuild is currently blocked by the host's missing Cesium Native dependency
cache and headers (`C:\.ezvcpkg`, GLM, RapidJSON, Curl, and async++). The PR
should include the source diff and a rebuilt Windows release DLL, followed by a
fresh six-frame run with the fallback disabled.

The proof camera uses a bounded `far` plane of `1,000,000` units after
normalizing the local control tileset. The earlier `20,000,000` value caused
Godot Forward+ `create_frustum_points` failures on Windows.

## PR Defense Rule

When this lane changes, update the Windows version matrix and the fork workpack
before editing the prose here. That keeps the exact host, version, and evidence
shape consistent across the packet set.

## Next Step

The Windows-native smoke now runs against the prepared vendor route with the
installed 4.7-stable editor, so the next meaningful step is to keep the macOS
lane moving and add an export proof if the addon or scene layout needs
adjustment.
