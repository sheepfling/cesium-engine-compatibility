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
