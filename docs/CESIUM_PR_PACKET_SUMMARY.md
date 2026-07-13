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

The visual-proof-root validator is part of that graph too, so the checked-in
manifest-backed proof roots can be audited programmatically once a live lane
produces PNGs.

The visual-proof audit composes the contracts, root validation, and perceptual
comparison into one programmatic gate.

## Unity Cesium-Earth Gate

The Unity proof fork now keeps proxy-earth and Cesium-earth as separate claims.
The Cesium scene loads World Terrain asset `1` and ion imagery asset `2` when
`CESIUM_ION_TOKEN`, `CESIUM_ION_ACCESS_TOKEN`, or `CESIUMION_TOKEN` is supplied, or loads the URL in
`CESIUM_3DTILES_URL`. It never falls back to the proxy scene for the Cesium
variant.

The player waits for a tileset child and renderer, then records
`cesium_configured`, `cesium_ready`, `cesium_renderer_count`, and
`cesium_failure` in `visual_proof_manifest.json`. Unity normalization preserves
those fields and root validation rejects a configured capture without rendered
tile content. Perceptual comparison remains the independent guard against
black, gray, cube-only, or drifted frames.

The current Windows host has no Ion token in its environment, so Ion account
coverage remains unverified. The credential-free URL-fixture run produced
rendered Cesium tile children and a green normalized six-frame Unity root.
Both routes still pass through normalization, root validation, and comparison;
the URL route is the reproducible Windows Cesium-earth claim.

The comparison gate uses raw pixel metrics for same-engine version drift, while
cross-engine comparisons retain renderer-independent edge occupancy, centroid,
and silhouette metrics as diagnostics. Proxy-earth versus Cesium-earth is an
expected content delta, so it is reported rather than incorrectly failed. All
frames still pass the independent black, flat-gray, low-edge, and launch/manifest
gates.

If you want to regenerate the same packet locally, use:

```bash
cesium-compatibility-packet
```

## Packet Graph

- `cesium-engine-matrix`
- `cesium-unity-native-matrix`
- `cesium-execution-audit`
- `cesium-planned-routes`
- `cesium-visual-proof-roots`
- `cesium-visual-proof-audit`
- `cesium-compatibility-packet`

Those packets are the main navigation anchors for the PR packet:

- `cesium-engine-matrix` keeps the version coverage and lane framing visible.
- `cesium-unity-native-matrix` keeps the Unity host spread and planned target gap visible.
- `cesium-execution-audit` keeps host readiness and runtime blockers visible.
- `cesium-planned-routes` keeps the remaining bootstrap routes commandable.
- `cesium-visual-proof-roots` keeps the live manifest-backed PNG roots
  machine-checkable.
- `cesium-visual-proof-audit` composes the contract, root, and comparison gates
  into one runtime-proof check.
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
- Unreal Windows 5.7 and 5.8 now use isolated temp-backed generated state;
  the runner removes plugin UHT/build output at each version boundary so
  alternating versions cannot compile against the other editor's generated
  headers. The fresh 5.7 and 5.8 runner packets both pass their build,
  automation, normalization, and visual gates.
- Unreal Windows visual-proof contract is now manifest-backed for the normalized `Saved/Screenshots/WindowsEditor` outputs, so the packet can tell the normalized PNG set from stray editor artifacts
- Unreal Windows visual-proof runner now names the exact `Cesium.VisualProof.Windows.ProxyEarth` and `Cesium.VisualProof.Windows.CesiumEarth` automation tests, plus the normalized proof root, so the runner evidence is explicit in the packet graph
- Unity and Godot Windows visual-proof rows now carry the same runner metadata shape as Unreal, including the manifest path and six capture paths, so the packet can describe the proof lane consistently across all three engines
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

### Unity Fork PR Boundary

The Unity fork changes needed for the current Windows route are recorded in
[`docs/CESIUM_UNITY_6000_5_FINDINGS.md`](CESIUM_UNITY_6000_5_FINDINGS.md). In
short, the fork needs Unity 6000.5 API/package compatibility, Reinterop
dependency staging, a temp-backed ezvcpkg cache, native-before-player
packaging for proof builds, and direct camera readback for deterministic PNGs.
The fork also guards the native `EntityId` header and bindings behind
`CESIUM_UNITY_USE_ENTITY_ID`, preserving the older integer path for pre-6000.5
editors. On this host Unity `6000.5.2f1` compiles the managed fork and packages
a real Windows `CesiumForUnityNative.dll`; the player exits cleanly and emits
the six named captures. The URL-fixture route now produces four rendered tile
child renderers and passes the normalized six-frame root validation. Ion
authentication remains a separate host capability and is not implied by the
credential-free URL proof.

When Unity licensing prevents `BuildPipeline.BuildPlayer`, the runner accepts
only an explicit `CESIUM_UNITY_PROOF_PLAYER` fallback. It records the failed
editor build and fallback path separately; it never silently promotes an
arbitrary executable or turns a proxy-only player into Cesium evidence.

The proof harness also registers its runtime camera with
`CesiumCameraManager.additionalCameras` and applies an explicit ECEF origin
and scale for the local fixture. Without that camera registration the native
tileset has no view, so it can instantiate successfully while never requesting
or rendering content. This camera/lifecycle correction belongs to the example
proof harness; the `EntityId` changes belong to the Unity fork itself.

### Godot Fork PR Boundary

The Windows Godot visual-proof work found a fork-level material bug:
`CesiumGDModelLoader.cpp` selected `BaseMaterial3D::CULL_FRONT` for ordinary
one-sided glTF materials. The vendor fix changes that branch to
`BaseMaterial3D::CULL_BACK`; otherwise Cesium tiles can be fetched and
instantiated while contributing no visible pixels.

The proof harness also bounds the Forward+ camera frustum to `1,000,000`
engine units after local tileset normalization. This avoids the Windows
renderer `create_frustum_points` failure seen with the previous `20,000,000`
far plane. The existing host DLL has not yet been rebuilt from the corrected
fork because its Cesium Native/vcpkg dependency cache is incomplete, so the
current host evidence is separated into real tile HTTP requests, rendered
tile-node markers, and a temporary visible-geometry compatibility fallback.

The PR must include the fork source change, a rebuilt Windows DLL, and a fresh
six-frame proof run with the fallback removed or disabled. Until then, the
Godot lane is evidence-backed but not a rebuilt-fork green claim.
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
- machine-checkable visual-proof roots that validate the manifest-backed PNG sets once a lane runs
- a combined visual-proof audit that composes contracts, roots, and comparison into one programmatic pass

## Still Open

- Unreal Linux Docker now has successful 5.7 and 5.8 build paths on this host; the lane
  reports the discovered Linux platform-support roots so the Docker path can
  distinguish staged engine zips from a real support tree, and the repo-owned
  plugin checkout gives the build the expected `Source/ThirdParty` layout
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

- `docs/CESIUM_COMPATIBILITY_NOTEBOOK.md`
- `docs/CESIUM_FORK_WORKPACK.md`
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
