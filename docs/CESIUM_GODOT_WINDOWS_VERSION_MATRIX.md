# Godot Windows Version Matrix

This note captures the four public Godot Windows builds already present on this
host and ties them to the repo-owned Godot evidence story.

## Current Windows Set

| Version | Lane Role | Executable Root | Notes |
| ------- | --------- | --------------- | ----- |
| 4.6.3-stable | compatibility evidence | `C:\Users\Public\Godot\engines\windows\Godot_v4.6.3-stable_win64.exe` | Oldest stable build in the local public set. Useful as backward-compatibility evidence. |
| 4.7-stable | current baseline | `C:\Users\Public\Godot\engines\windows\Godot_v4.7-stable_win64.exe` | Current pinned Windows baseline for the Godot lane. |
| 4.7.1-rc1 | release-candidate evidence | `C:\Users\Public\Godot\engines\windows\Godot_v4.7.1-rc1_win64.exe` | Good for checking whether release-candidate drift changes the Windows baseline behavior. |
| 4.8-dev1 | forward verification | `C:\Users\Public\Godot\engines\windows\Godot_v4.8-dev1_win64.exe` | Forward-looking build for detecting upcoming Windows editor or export drift. |

## How To Use It

- keep `4.7-stable` as the pinned baseline lane
- use `4.6.3-stable` as backward-compatibility evidence
- use `4.7.1-rc1` as release-candidate evidence
- use `4.8-dev1` as forward-verification evidence

## Related Notes

- [Godot Windows 4.7 build notes](./CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md)
- [Godot cross-platform notes](./CESIUM_GODOT_CROSS_PLATFORM_NOTES.md)

## Report Shape

The Godot example workflow now carries a `windows_version_matrix` payload for
the Windows lane. That keeps the evidence set available both as documentation
and as structured workflow output.
