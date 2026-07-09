# Unity Version Matrix

This note captures the Unity evidence we can currently leverage from the repo
and keeps it in the same matrix style we use for Unreal and Godot.

## Current Unity Set

| Version | Lane Role | Project Version File | Package Count | Notes |
| ------- | --------- | -------------------- | ------------- | ----- |
| 6000.3.19f1 | compatibility evidence | `extensions/cesium/examples/unity/CesiumVanillaExample/ProjectSettings/ProjectVersion.txt` | 0 | Currently blocked by Unity licensing/profile failures on this host, including LocalAppData access denial, mutex collisions, and BIOS lookup denial, so it stays as compatibility evidence rather than a default green build lane. |
| 6000.5.2f1 | current baseline | `extensions/cesium/examples/unity/CesiumVanillaExample/ProjectSettings/ProjectVersion.txt` | 3 | Baseline editor used for the original host proof. |
| 6000.6.0b2 | forward verification | `extensions/cesium/examples/unity/CesiumVanillaExample/ProjectSettings/ProjectVersion.txt` | 1 | Verified in batchmode with the self-contained example build harness. |

## Current Package Set

The repo-owned Unity example currently declares no explicit package
dependencies in the source manifest. The editor still materializes built-in
modules during a real build, but the source route itself stays minimal so we can
track version drift more clearly.

## How To Use It

- keep `6000.5.2f1` as the currently pinned baseline lane on this host
- use `6000.3.19f1` as compatibility evidence only, because it still hits a
  Unity licensing/profile blocker on this host
- use `6000.6.0b2` as forward verification
- use the package list to watch for manifest drift
- record exact package revisions and failure modes in
  `docs/CESIUM_UNITY_6000_5_FINDINGS.md`

## Related Notes

- [Unity 6000.5 findings](./CESIUM_UNITY_6000_5_FINDINGS.md)
- [Cesium example standard](../extensions/cesium/docs/CESIUM_EXAMPLE_STANDARD.md)

## Report Shape

The Cesium example workflow now carries a `version_matrix` payload for the
Unity lane so the pin and package set remain attached to the workflow output.
The local batchmode build harness has also been exercised across the installed
editor spread on this host. The green example-build lane currently covers
`6000.5.2f1` and `6000.6.0b2`; `6000.3.19f1` remains tracked as compatibility
evidence because package resolution on that editor still fails on this host.
