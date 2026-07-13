# Unity 6000.5 Findings

This note tracks the repo-owned Unity lane around the older `6000.5.0f1`
editor line while the example project itself has moved forward to
`6000.6.0b2`.

The goal is to keep the Unity native lane honest about what we know today and
what still needs compatibility validation when we move forward or backward
across nearby editor versions.

## Current Lane

- pinned editor proof lane: `6000.5.0f1`
- current example-project version file: `6000.6.0b2`
- repo-owned example project: `extensions/cesium/examples/unity/CesiumVanillaExample/`
- current vendor route: `CesiumGS/cesium-unity`

### Windows Verification Update (2026-07-12)

The vendored checkout was fetched from `https://github.com/CesiumGS/cesium-unity`
and is currently at upstream `main` commit `17ba7d5` (the post-`v1.24.0`
Linux-container merge). There were no upstream commits available to import at
the time of verification, so the 6000.5 compatibility work below is local
forward/backward compatibility work, not an upstream lag issue.

The latest Windows probe against Unity `6000.5.2f1` successfully connected to
the Unity Licensing Client and reported `Product: Unity Personal` followed by
`Successfully updated license`. The license is therefore available on this
host for the editor build path. The separate visual-proof player may still
need an Ion token or a reachable 3D Tiles URL; that is a Cesium content-source
gate, not a licensing gate.

The 6000.5 managed compilation boundary is now understood and patched in the
fork/package staging route. The proof harness reaches Unity startup without
Cesium `CS0619` errors after the Reinterop probes use `EntityId` for
`GetEntityId` and the `Physics.BakeMesh(EntityId, ...)` overloads, and the
example declares the `ImageConversion` module required by the PNG capture.

This means the Unity fork/package route now passes its managed compilation and
native Windows packaging gates on this host. It is **not yet PR-green** for
Cesium-earth visual proof because the latest player run had no Ion token or
3D Tiles URL, so the proof harness correctly emitted proxy controls and a
Cesium-source failure manifest instead of fabricating a Cesium frame.

## What We Are Tracking

The Unity lane should keep separate notes for:

1. the pinned editor line we are using as the current proof target
2. newer `6000.x` editors that may introduce API or package drift
3. older `6000.x` editors that may expose import or serialized-project drift
4. exact package revisions and failure modes whenever the lane changes

## Compatibility Buckets

- forward compatibility
  - watch for API surface changes in Unity editor code
  - watch for package resolution changes in the local Cesium route
  - record the first failing editor revision if a newer `6000.x` line breaks
- backward compatibility
  - watch for project serialization drift
  - watch for package or assembly-definition assumptions that only exist in the
    pinned lane
  - record the first failing editor revision if an older `6000.x` line breaks

## Current Evidence

The repo-owned example project now records `6000.6.0b2` in:

- `extensions/cesium/examples/unity/CesiumVanillaExample/ProjectSettings/ProjectVersion.txt`

The example workflow now exposes that project version as structured
compatibility metadata so reports can keep the forward/backward story attached
to the lane output.

The live Unity host report has now been captured locally, staged, and exported
as a handoff archive:

- `artifacts/reports/unity_host_6000_5_0f1/unity_host_report.json`
- `artifacts/reports/unity_host_6000_5_0f1/unity_host_report.md`
- `artifacts/verification_reports/unity_hosts/local-host-6000_5_0f1/`
- `dist/unity_host_handoff/cesium-unity-host-handoff.zip`

The local Unity editor also proved it can open and build the repo-owned example
project in batchmode on this host, so we can treat the self-contained lane as
more than a discovery-only proof:

```bash
"C:\Program Files\Unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe" -batchmode -nographics -quit -projectPath "C:\Users\peanu\GIT\sheepfling\cesium-engine-compatibility\extensions\cesium\examples\unity\CesiumVanillaExample"
```

The build proof uses a temporary scene materialized under `Assets/` during the
build and leaves the resulting Windows player under:

- `extensions/cesium/examples/unity/CesiumVanillaExample/build/unity/CesiumVanillaExample/windows/CesiumVanillaExample.exe`

The same build harness also succeeded on the forward Windows editor on this
host:

- `6000.6.0b2` via `build/unity_example_build_6000_6_0b2.log`

The older `6000.3.19f1` editor is now included in the same build lane as the
other installed editors so we can keep the compatibility evidence attached to
the actual build attempt. It still remains a riskier lane than `6000.5.2f1`
because Unity's licensing client has historically been flaky on this host, and
the fresh build attempt still hits the same licensing-init, BIOS lookup, and
package-resolution failure modes. In particular, Unity tries to create
`C:\Program Files\Unity\Hub\Editor\6000.3.19f1\Editor\Data\artifacts` and gets
`EPERM` even after we stage the project version to the selected editor and give
the package manager its own writable cache roots. The repeated failure modes we
observed before the runtime-profile isolation work were:

- access denied on `C:\Users\peanu\AppData\Local\Unity\config\production.json`
- repeated `Unity-LicenseClient-peanu` mutex collisions
- BIOS-identity lookup denied by the local Windows environment

The licensing client itself does expose a small supported surface, including
`--showContext`, `--disable-file-watcher`, and the
`UNITY_LICENSING_SERVER_BASE_URL` / `UNITY_LICENSING_SERVER_TOOLSET`
environment hooks. When we forced the runtime profile to a disposable
workspace-local tree and ran `--showContext`, the client still reported the
host BIOS lookup as denied, which is why we treat the blocker as a real host
limit rather than a missing env var.

That keeps it in compatibility-evidence territory until we get a successful
build on the current host profile.

The older pre-fix attempt against the local package route on `6000.5.2f1`
exited during Cesium C# compilation. That historical log is retained under:

- `artifacts/reports/unity_example_build/logs/unity_example_build_6000_5_2f1_windows.log`

The historical compilation failures were specifically:

- `UnityEngine.EventSystems` is missing from the Cesium UI source references.
- `DownloadHandlerScript` is missing from the Cesium networking source
  references.
- Deprecated editor `TreeView` APIs are hard errors in Unity 6000.5.

Those failures are addressed by the fork/package compatibility patch. A live
Unity visual-proof run still needs a real Cesium source before we can claim the
Cesium-earth image set is green.

## Fork Fixes Required For The PR

The Unity fork must carry these compatibility changes together; applying only
the package manifest changes is not sufficient for a reproducible proof build:

- declare the built-in `UnityWebRequestTexture` and `ScreenCapture` modules in
  the example/package manifests where those APIs are used
- use the Unity 6000.5 `EntityId` overloads in Reinterop probes while retaining
  the integer `GetInstanceID`/`Physics.BakeMesh` path for older Unity editors
- guard the native `EntityId` include and call sites behind
  `CESIUM_UNITY_USE_ENTITY_ID`, so older Unity editor packages still compile
  against the integer bindings
- update the editor `TreeView` call sites for Unity 6000.5's obsolete-API
  treatment
- stage `System.Collections.Immutable.dll` with Reinterop so Unity's bundled
  .NET compiler can resolve the generator dependency
- build the Cesium native library before `BuildPipeline.BuildPlayer` for the
  visual-proof lane; the normal post-build callback otherwise leaves a
  58-byte placeholder DLL in the player
- capture proof frames from the proof camera through a `RenderTexture` rather
  than relying on the optional `UnityEngine.ScreenCapture` assembly
- set `EZVCPKG_BASEDIR` to a writable temp-backed directory. The fork now
  defaults this to `%TEMP%/cesium-ezvcpkg` when the caller does not provide an
  override, preventing the previous `/.ezvcpkg` root fallback

The native-before-player path is opt-in through
`CESIUM_BUILD_NATIVE_BEFORE_PLAYER=1`, so ordinary package/editor workflows
retain their existing behavior while the proof lane can require a real native
bridge before packaging.

## Current Proof Boundary

### Cesium Earth Acceptance Gate (2026-07-13)

The Unity visual harness must distinguish a real Cesium 3D Tiles frame from a
scene that merely contains the orange orientation cube. The proof scene now
uses the following source order:

1. `CESIUM_ION_TOKEN`, `CESIUM_ION_ACCESS_TOKEN`, or `CESIUMION_TOKEN`, loading Cesium ion World Terrain
   asset `1` and ion imagery asset `2`.
2. `CESIUM_3DTILES_URL`, loading a caller-supplied tileset URL.
3. no Cesium capture. The run records a configuration error rather than
   silently falling back to the proxy earth.

The runtime waits up to `CESIUM_VISUAL_PROOF_TIMEOUT_SECONDS` (30 seconds by
default) for a tileset child and at least one renderer. The manifest records
`cesium_configured`, `cesium_ready`, `cesium_renderer_count`, and
`cesium_failure`. `validate_visual_proof_roots` rejects a Unity root unless
the configured source and rendered-content markers are both present. The
image comparison remains a second gate for black, gray, cube-only, and drifted
frames.

The Unity license preflight is bounded to 15 seconds by default through
`CESIUM_UNITY_LICENSE_PROBE_TIMEOUT_SECONDS`; the Hub settle window remains
configurable through `CESIUM_UNITY_HUB_SETTLE_SECONDS`. This keeps report
generation from becoming an unbounded licensing wait while still leaving Hub
open for interactive activation when the probe is blocked.

This is an intentional credential boundary: a host without an Ion token can
still build the player and produce proxy controls, but it cannot claim Ion
account coverage. The Windows proof lane also accepts `CESIUM_3DTILES_URL`.
With the repository's local 3D Tiles fixture, that credential-free route
created four Cesium child renderers and emitted all six captures. This proves
the packaged Unity/Cesium runtime and camera contract without claiming Ion
account access.

The tooling regression suite remains green (`96 passed`). A current Windows
`6000.5.2f1` run compiles the managed fork and packages a real
`CesiumForUnityNative.dll` (about 51 MB), then the player emits all six named
captures and exits cleanly. The URL-fixture run records
`cesium_configured=true`, `cesium_ready=true`, and four bootstrap tile
renderers; the normalized Windows root passes its six-frame contract. Human
review does not accept the resulting Cesium-earth images as a populated Cesium
globe, so the PR must not claim completed Unity visual proof yet. Live Ion
authentication remains a separate, unverified host capability.

### Fork Patch Boundary

The fetched `external/cesium/cesium-unity` fork carries the Unity 6000.5
compatibility patch. `Source/Editor/CompileCesiumForUnityNative.cs` passes
`-DCESIUM_UNITY_USE_ENTITY_ID=1` for Unity 6000.5 or newer; the native CMake
option and runtime sources then select `EntityId` bindings, while the
pre-6000.5 branches continue to use integer instance IDs. This is a source
compatibility fix, not a screenshot workaround.

The repo-owned proof harness is a separate layer. It registers its camera with
`CesiumCameraManager.additionalCameras`, applies the URL fixture's ECEF origin
and scale, waits for child renderers, and refuses to emit a Cesium claim when
the source or rendered-content markers are absent. ECEF values are parsed with
invariant culture so the same command works on Windows hosts using comma
decimal locales.

For the PR, include the fork checkout revision and the generated native DLL
from the same build. Do not treat a temporary patched player as a replacement
for that reproducible fork build; it is only a diagnostic fallback when the
Unity licensing client prevents `BuildPipeline.BuildPlayer` from completing.

That is still separate from a live Cesium package-route install/build proof, but
it is stronger than version discovery alone because it exercises the actual
example-project path and the editor build pipeline.

The current Unity version matrix is tracked in
[`docs/CESIUM_UNITY_VERSION_MATRIX.md`](./CESIUM_UNITY_VERSION_MATRIX.md).

## Linux/Docker Proof Checklist

The Windows host proof is already in place, but the Linux/Docker route still
needs a live Cesium package-route run before we can claim that surface in the
same packet.

Use the installed Unity spread as the compatibility anchor for the Linux route:

- `6000.3.19f1` as compatibility evidence only
- `6000.5.2f1` as the current baseline
- `6000.6.0b2` as forward verification

The planned route is:

```bash
cesium-unity-linux-docker --native-target linux
```

The real probe now exists as a report artifact under
`artifacts/reports/unity_linux_docker/cesium-unity_linux_docker.json`; it still
lands in `partial` because the Linux container does not discover an installed
Unity editor in this environment, so it remains a live proof route rather than
a build-green claim.

The packet now also records the host-side Unity discovery snapshot, so we can
see the installed editor spread that the container consumes. The Docker lane
now mounts the discovered install roots directly instead of only the broad
public parent, which lets the container enumerate the actual version
directories when they are present.

The repo-local lane runner can now fan that route out across the installed
Windows editors from this checkout using `unity-host-linux-docker`, and the
bundle now includes `6000.3.19f1` alongside `6000.5.2f1` and `6000.6.0b2` so
we can keep the older editor in the same evidence path.

The example-build harness now also tries to clear stale Unity licensing client
processes before launching a build, but that did not change the host blocker on
`6000.3.19f1`.

When we exercise it for real, capture the following in the packet:

- exact editor version
- host OS and container image
- package revision or checkout commit
- target being exercised
- command used
- log tail or failure message
- whether the build was against the self-contained example scaffold or the live
  Cesium package route

## What To Capture Next

When the Unity source route or example lane is exercised, keep the packet small
and explicit:

- exact editor version
- package revision or checkout commit
- host OS
- target being exercised
- command used
- log tail or failure message
- whether the build was against the self-contained example scaffold or the live
  Cesium package route

If the lane fails on a newer or older editor, update this note before broadening
the supported range.
