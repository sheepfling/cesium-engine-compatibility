# Godot Linux Version Matrix

This note captures the four public Godot Linux builds already present on this
host and ties them to the repo-owned Godot evidence story.

## Current Linux Set

| Version | Lane Role | Executable Root | Notes |
| ------- | --------- | --------------- | ----- |
| 4.6.3-stable | compatibility evidence | `C:\Users\Public\Godot\engines\linux\Godot_v4.6.3-stable_linux.x86_64` | Oldest stable build in the local public set. Useful as backward-compatibility evidence. |
| 4.7-stable | current baseline | `C:\Users\Public\Godot\engines\linux\Godot_v4.7-stable_linux.x86_64` | Current pinned Linux baseline for the Godot lane. |
| 4.7.1-rc1 | release-candidate evidence | `C:\Users\Public\Godot\engines\linux\Godot_v4.7.1-rc1_linux.x86_64` | Good for checking whether release-candidate drift changes the Linux baseline behavior. |
| 4.8-dev1 | forward verification | `C:\Users\Public\Godot\engines\linux\Godot_v4.8-dev1_linux.x86_64` | Forward-looking build for detecting upcoming Linux editor or export drift. |

## How To Use It

- keep `4.7-stable` as the pinned baseline lane
- use `4.6.3-stable` as backward-compatibility evidence
- use `4.7.1-rc1` as release-candidate evidence
- use `4.8-dev1` as forward-verification evidence

## Related Notes

- [Godot Windows version matrix](./CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md)
- [Godot cross-platform notes](./CESIUM_GODOT_CROSS_PLATFORM_NOTES.md)

## Report Shape

The Godot example workflow now carries a `linux_version_matrix` payload for the
Linux lane. That keeps the evidence set available both as documentation and as
structured workflow output.

## Live Linux Proof

The Linux editor has now been exercised in Docker against the repo-owned
example project with:

```bash
docker run --rm -v "C:\Users\peanu\GIT\sheepfling\cesium-engine-compatibility:/workspace" -v "C:\Users\Public\Godot\engines\linux\Godot_v4.7-stable_linux.x86_64:/godot:ro" -w /workspace cesium-linux-proof:ubuntu24.04 /godot/Godot_v4.7-stable_linux.x86_64 --headless --path /workspace/extensions/cesium/examples/godot/CesiumVanillaExample --import --quit
```

That succeeded and gives us a real Linux import/open proof for the 4.7-stable
lane, separate from the Windows headless import proof.
