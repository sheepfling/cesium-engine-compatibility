# Godot Windows 4.7 Build Notes

This note tracks the repo-owned Godot native lane on Windows.

The current goal is to keep the 3D Tiles/Godot route honest about what works
on a Windows host and what still needs compatibility work as the 4.x series
changes. The four public Windows builds on this host are tracked in
`docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`. Linux evidence is tracked in
`docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`. Linux and macOS host differences
are tracked separately in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`.

## Current Lane

- pinned editor family: `4.7`
- native target: `windows`
- repo-owned example project: `extensions/cesium/examples/godot/CesiumVanillaExample/`
- vendor route: `Battle-Road-Labs/3D-Tiles-For-Godot`
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

## Next Step

The Windows-native smoke now runs against the prepared vendor route with the
installed 4.7-stable editor, so the next meaningful step is to keep the macOS
lane moving and add an export proof if the addon or scene layout needs
adjustment.
