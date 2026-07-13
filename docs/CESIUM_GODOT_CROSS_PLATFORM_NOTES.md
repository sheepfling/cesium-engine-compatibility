# Cesium Godot Cross-Platform Notes

This note is the cross-platform Godot companion to the fork workpack.

Use it when you need one place to answer:

1. what source route the Godot work comes from
2. what host and architecture are being proven
3. which versions are compatibility evidence versus current baseline
4. what still needs to go green before the Godot PR is defendable

## Source Route

- source route: `Battle-Road-Labs/3D-Tiles-For-Godot`
- versioning model: commit-tracked checkout, not a semver package
- current branch policy: `master`
- public engine discovery prefers `C:\Users\Public\Godot`

The exact checkout commit belongs in the fork workpack, not in a vague version
label. That keeps the community-route story honest.

## Source Version Anchors

| Surface | Version Anchor | Notes |
| --- | --- | --- |
| Windows | `4.7-stable` | Current pinned baseline for the repo-owned Godot lane. |
| Linux | `4.7-stable` | Current pinned Linux baseline for the repo-owned Godot lane. |
| Backward evidence | `4.6.3-stable` | Useful compatibility evidence for both Windows and Linux. |
| Forward evidence | `4.7.1-rc1`, `4.8-dev1` | Useful for detecting release drift before it reaches the baseline. |

## Host Matrix

| Host | Architecture | Status | Notes |
| --- | --- | --- | --- |
| Windows | `x86_64` | verified | Baseline import/open proof and the four-version discovery set are both present. |
| Linux | `x86_64` | verified | Docker-backed proof is available and the same four-version discovery set is visible. |
| macOS | `x86_64` | planned | Keep Intel separate from Apple Silicon when we get a real host proof. |
| macOS | `arm64` | planned | Track Apple Silicon separately so the packet can defend both Mac architectures. |

## Current Contract

The repo-owned Godot example workflow already treats the lane as a first-class
workflow surface. What changes per host is the compatibility framing:

- Windows: baseline import/open and renderer proof
- Linux: separate native import/open proof, with Docker as the repeatable proxy
- macOS: separate native import/open proof, split by Intel and Apple Silicon

The commandable routes now stay visible in the packet set:

- `cesium-example report --engine godot --native-target windows`
- `cesium-example report --engine godot --native-target linux`
- `cesium-example report --engine godot --native-target mac`
- `cesium-plugin-lanes --dry-run --lanes godot-host-mac`

## Evidence

### Windows

- the local Windows editor can headlessly import the repo-owned example project
- the Windows public discovery tree recognizes the four public builds
- build notes live in [Godot Windows 4.7 build notes](./CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md)
- the version matrix lives in [Godot Windows version matrix](./CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md)

### Linux

- the local Linux editor can headlessly import the repo-owned example project in Docker
- the Linux public discovery tree recognizes the same four-version set
- the Docker proof lane is a real proof lane, not just a discovery placeholder
- the version matrix lives in [Godot Linux version matrix](./CESIUM_GODOT_LINUX_VERSION_MATRIX.md)

### macOS

- macOS remains planned
- macOS should be split into Intel `x86_64` and Apple Silicon `arm64`
- the planned route stays commandable through the lane bundle
- the macOS notes should preserve the same evidence shape when the first real host proof lands

## Public Search Roots

Search these first when looking for local Godot editor installs:

- `C:\Users\Public\Godot\engines\windows`
- `C:\Users\Public\Godot\engines\linux`

The discovery helper already understands the public `win64.exe` and
`linux.x86_64` layouts, so the host audit can see the full Windows and Linux
version sets.

## Open Gaps

- macOS native import/open or build proof
- separate Intel and Apple Silicon macOS evidence
- any extra addon or scene drift that only shows up on the Mac route
- Windows GDExtension load crash when the Cesium descriptor is loaded from the
  scene script on the current host

## Minimal Repro

The current Windows crash reduces to a very small repro:

1. create a clean Godot project with a `Node3D` proof scene
2. add the Cesium addon folder under `addons/cesium_godot`
3. call `load("res://addons/cesium_godot/Godot3DTiles.gdextension")` from
   `_ready()`
4. the editor hard-crashes on Windows across `4.6.3-stable`, `4.7-stable`,
   `4.7.1-rc1`, and `4.8-dev1`

That makes the current blocker a GDExtension-load compatibility failure, not
just a bad scene layout or a missing user cache.

## PR Defense Notes

When you write the Godot PR narrative, keep these sentences true:

- the route is community-maintained and commit-tracked
- Windows and Linux are proven as separate host lanes
- macOS is still planned, not implied green
- Intel and Apple Silicon remain separate proof lanes on macOS
- the workpack is the place where the exact checkout commit and branch live
- the Windows blocker is a reproducible GDExtension load crash, so the proof
  notes should name the exact descriptor-load line and the versions tested

## Next Step

The next useful step is still one native smoke per host:

1. Windows import/open smoke
2. Linux import/open smoke
3. macOS import/open smoke

Keep those smokes separated in documentation and reporting so the host-specific
compatibility story stays obvious.
