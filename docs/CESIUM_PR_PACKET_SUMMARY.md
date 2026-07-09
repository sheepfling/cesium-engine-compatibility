# Cesium PR Packet Summary

This note is the reviewer-facing snapshot for the current cross-platform
compatibility work. It keeps the current evidence and the remaining live gaps in
one place so the eventual upstream PR can be defended without reconstructing the
whole thread.

The packet now mirrors the same shape used by the generated matrix and audit
reports: a top-level status, explicit claim boundaries, evidence pointers, and
clear gap tracking. That makes the summary behave like a union of the lane
reports instead of a separate narrative.

The compatibility packet also carries a related-packet index now, so the matrix,
Unity native matrix, execution audit, and planned-routes packet stay linked as
one reviewable set.

If you want to regenerate the same packet locally, use:

```bash
cesium-compatibility-packet
```

## Packet Graph

- `cesium-engine-matrix`
- `cesium-unity-native-matrix`
- `cesium-execution-audit`
- `cesium-planned-routes`
- `cesium-compatibility-packet`

Those packets are the main navigation anchors for the PR packet:

- `cesium-engine-matrix` keeps the version coverage and lane framing visible.
- `cesium-unity-native-matrix` keeps the Unity host spread and planned target gap visible.
- `cesium-execution-audit` keeps host readiness and runtime blockers visible.
- `cesium-planned-routes` keeps the remaining bootstrap routes commandable.
- `cesium-compatibility-packet` unions the above into the final reviewer-facing picture.

## Packet Status

- `cesium-engine-matrix`: `partial`
- `cesium-unity-native-matrix`: `partial`
- `cesium-execution-audit`: `partial`
- `cesium-planned-routes`: `dry-run`
- `cesium-compatibility-packet`: `partial`

That status line-up keeps the current verified-versus-planned split obvious
without making the summary look greener than the underlying evidence really is.

## Coverage Snapshot

| Surface | Verified Today | Still Planned |
| --- | --- | --- |
| Unreal | Windows 5.7/5.8, Linux Docker 5.7/5.8 build evidence, Linux 5.7/5.8 matrix coverage | stronger source-built Linux platform-support story for long-lived upstream reference |
| Unity | Windows host coverage across `6000.3.19f1`, `6000.5.2f1`, and `6000.6.0b2`; the example-build lane now attempts all three installed editors; plus the Unity native matrix report and a live Linux Docker report | separate live Cesium install/build proof |
| Godot | Windows and Linux coverage across `4.6.3-stable`, `4.7-stable`, `4.7.1-rc1`, and `4.8-dev1`, plus a live Linux Docker report | macOS native import/open or build proof |

## Verified Today

- Unreal Windows coverage is explicit for `5.7` and `5.8`
- Unreal Linux Docker build evidence is explicit for `5.7` and `5.8`; the
  current build path now completes successfully and emits the Linux shipping
  binary on both lanes
- Unity lane coverage now includes `6000.3.19f1`, `6000.5.2f1`, and
  `6000.6.0b2`; the Unity host report plus handoff archive are generated
  locally, the Unity native matrix now records the installed-editor spread and
  the planned Linux/macOS targets, and the Unity example-build lane now
  attempts the repo-owned example project in batchmode across the installed
  editors. `6000.3.19f1` remains tracked as compatibility evidence because
  Unity's licensing client still hits host licensing/profile failures in this
  environment and the package manager still tries to create
  `C:\Program Files\Unity\Hub\Editor\6000.3.19f1\Editor\Data\artifacts`, even
  after we stage the project version to the selected editor and give the package
  manager writable cache roots, including
  `C:\Users\peanu\AppData\Local\Unity\config\production.json` access denial,
  repeated `Unity-LicenseClient-peanu` mutex collisions, and BIOS-identity
  lookup denial.
- Unity Linux Docker now has a live report artifact at `artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json`, and the repo-local lane runner can fan it out across the installed `6000.5.2f1`, `6000.3.19f1`, and `6000.6.0b2` editors so the older installed editor stays in the same evidence path; the packet now also carries the host-side discovery snapshot that explains which editors were visible on Windows, but it still stops short of a full build-green proof because the Linux container does not discover an installed Unity editor here
- Unity macOS remains a separate planned proof lane alongside the Linux/Docker work
- Godot Windows evidence is explicit for `4.6.3-stable`, `4.7-stable`,
  `4.7.1-rc1`, and `4.8-dev1`
- Godot Linux evidence is explicit for the same four versions, and the Linux editor has now been exercised in Docker against the repo-owned example project
- Godot Linux Docker now has a live report artifact, and the repo-local lane passes from this checkout, so the Docker route is part of the packet even though macOS remains the next proof gap
- Godot native report lanes have been exercised for Windows and Linux; the Godot editor can headlessly import the repo-owned example project on Windows, the Linux lane can do the same inside Docker, and macOS remains the next live proof gap
  ; the macOS route is now commandable as `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
- the still-planned routes are bundled as `cesium-plugin-lanes --dry-run --lanes cross-platform-planned`
- the dedicated planned-routes packet is available as `cesium-planned-routes`
- the lane runner can also dry-run the specific planned routes directly as `cesium-plugin-lanes --dry-run --lanes godot-host-mac unity-host-linux-docker unity-host-mac`
- public discovery roots are explicit for:
  - `C:\Users\Public\Unreal`
  - `C:\Users\Public\Unity`
  - `C:\Users\Public\Godot`

## What The Repo Can Prove Without Guessing

- repository-owned matrix generation for Unreal, Unity, and Godot
- normalized package imports and bootstrap behavior
- explicit Windows, Linux Docker, and host-only lane framing
- version-specific compatibility notes for Unreal, Unity, and Godot
- fork/PR guidance that separates verification from source fixes
- packet-style rollups that union the lane evidence into one final picture
- commandable planned-route packets that keep the remaining macOS and bootstrap work explicit

## Still Open

- Unreal Linux Docker now has successful 5.7 and 5.8 build paths on this host; the lane
  reports the discovered Linux platform-support roots so the Docker path can
  distinguish staged engine zips from a real support tree, and the Packet-Stoat
  packaged plugin root gives the build the expected `Source/ThirdParty`
  layout
- Unity still needs a separate live Cesium plugin install/build proof run for
  the pinned lane, and we still need to prove the Linux/Docker Unity build path
  if we want to claim that surface as build-green in the same packet; that
  route now has a live Docker report artifact, a repo-local lane runner that
  fans out across the installed editor spread, and is commandable as
  `cesium-unity-linux-docker --native-target linux`. Unity macOS remains the
  other planned native lane, and the older installed `6000.3.19f1` editor is
  now part of the same example-build lane rather than being skipped.
- Godot still needs live import/open or build proof runs for the macOS native target,
  but the lane runner already exposes that route in dry-run form for bootstrap
  and packet planning
- the planned bootstrap bundle is now captured in a dedicated packet, so the remaining Unreal Linux parity, Unity Linux/Docker, Unity macOS, and Godot macOS routes stay visible together without being conflated with build-green evidence

## Next Proof Runs

| Surface | Next live run | Capture focus |
| --- | --- | --- |
| Unreal | `cesium-unreal-linux-docker build-plan --engine-version 5.8` | source-built Linux support tree for upstream parity, `--linux-platform-support-root`, toolchain details |
| Unity | `cesium-unity-linux-docker --native-target linux` | editor version, host/container image, package revision, live Cesium package-route proof |
| Planned bootstrap | `cesium-planned-routes` | remaining Unreal Linux, Unity Linux/Docker, Unity macOS, and Godot macOS route inventory |
| Godot | `cesium-plugin-lanes --dry-run --lanes godot-host-mac` | editor version, host architecture, addon revision, macOS import/open or build proof |

## Use In A PR

When preparing a vendor PR packet, start from:

- `docs/CESIUM_ENGINE_MATRIX.md`
- `docs/UNREAL_VERSION_MATRIX.md`
- `docs/CESIUM_UNREAL_LINUX_NOTES.md`
- `docs/CESIUM_UNITY_VERSION_MATRIX.md`
- `docs/CESIUM_UNITY_6000_5_FINDINGS.md`
- `artifacts/reports/unity_native_matrix/unity_native_matrix.json`
- `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`
- `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`
- `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`
- `docs/CESIUM_CROSS_PLATFORM_FIX_NOTES.md`
- `docs/CESIUM_PLANNED_ROUTES.md`
- `docs/CESIUM_FORK_LEDGER.md`
- `artifacts/reports/cesium_planned_routes/cesium_planned_routes.json`
- the related-packet index inside `cesium-compatibility-packet`

That packet should tell one coherent story:

1. what is verified
2. what version range is being tracked
3. what remains to be proven on live hosts
4. what code or documentation belongs in the forked vendor repo
