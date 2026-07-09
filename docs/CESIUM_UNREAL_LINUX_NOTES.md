# Unreal Linux Notes

This note tracks the repo-owned Unreal Linux lane.

The goal is to keep Linux distinct from the Windows source-route and Windows
editor lanes, because the Linux failure surface is mostly host image, compiler,
and packaging alignment.

## Current Lane Shape

- upstream plugin route: `CesiumGS/cesium-unreal`
- repo-owned example project: `extensions/cesium/examples/unreal/CesiumVanillaExample/`
- Linux is a supported native target in the upstream plugin manifest and build
  rules
- the 5.7 baseline and 5.8 forward-verification split lives in
  [`docs/UNREAL_VERSION_MATRIX.md`](./UNREAL_VERSION_MATRIX.md)

## What We Know

- the plugin advertises `Linux` in its supported target platforms
- the runtime and editor build rules both have Linux-specific branches
- the source checkout already includes Linux toolchain and developer-setup
  documentation
- the public `C:\Users\Public\Unreal\engines\linux\Linux_Unreal_Engine_*.zip`
  archives are useful as discovery and staging evidence
- the archive route now uses host-side staging before Docker launch, following
  the Packet-Stoat smart-unpack pattern; that keeps the engine tree unpacked
  once on the host and lets us copy any discovered Linux support tree into the
  staged root before the container run
- the Docker lane now prefers the packaged Packet-Stoat plugin root when it is
  available and it has the expected `Source/ThirdParty/include` layout
- the cached `cesium-linux-proof:ubuntu24.04` container has `python3`, `cmake`,
  `ninja`, `git`, and `unzip`, but not the Unreal Linux host toolchain or
  `dotnet`
- default engine discovery prefers `C:\Users\Public\Unreal` before falling
  back to installed `UE_*` roots under `C:\Program Files\Epic Games`

## Current Docker Result

The Docker lane now runs the Unreal Linux report path and completes the full
`BuildPlugin` build on this host for both the 5.7 baseline lane and the 5.8
forward-verification lane.

Build command used:

```bash
cesium-unreal-linux-docker build --engine-version 5.7
cesium-unreal-linux-docker build --engine-version 5.8
```

Observed result:

- the report path runs to completion inside Docker
- `BuildPlugin` completes successfully and emits the Linux shipping binary on
  both the 5.7 and 5.8 lanes
- the latest build log reports `Result: Succeeded` and `ExitCode=0`
- the lane now uses the Packet-Stoat packaged plugin tree as the preferred
  plugin root when available, which gives the build the expected
  `Source/ThirdParty/include` layout
- the host-side staging root is short enough to avoid the earlier Windows path
  length issues
- the public archive remains an evidence input rather than the thing that makes
  the build green

Follow-up evidence worth keeping:

- `RHICreateTexture` deprecation warnings appear in `CesiumTextureResource.cpp`
- `Materials/MaterialParameters.h` emits a deprecation note during the 5.7 and
  5.8 builds
- these warnings are still worth tracking, but they are separate from the Linux
  build-success proof

## Compatibility Buckets

- forward compatibility
  - track Unreal 5.x Linux build and editor-open drift on newer hosts
  - capture the first failing UE release if a newer Linux lane breaks
- backward compatibility
  - track Unreal 5.x Linux source, toolchain, or dependency drift on older
    hosts
  - capture the first failing UE release if an older Linux lane breaks

## What To Capture

For any Linux proof run, record:

- exact Unreal version
- Linux host image or distro
- compiler and sysroot/toolchain details
- command used
- whether the failure happened in source build, plugin package, editor open,
  or runtime smoke

## Next Step

The next meaningful step is to keep the Windows, Linux, and Linux Docker
evidence aligned with the remaining live Unity and Godot host lanes.

Current follow-up:

- launcher Unreal installs are good enough for inspection and report lanes
- the Docker build now completes successfully on both the 5.7 baseline and 5.8
  forward-verification lanes when the staged archive and Packet-Stoat packaged
  plugin root are available
- the public Unreal Linux zip archives remain evidence and staging inputs for
  the lane bootstrap, while the packaged plugin root supplies the
  `Source/ThirdParty` layout that makes the build green
- the lane now accepts an explicit `--linux-platform-support-root` override so a
  mounted source-built Linux tree can be used when one exists
- the Unreal Linux lane now reports discovered Linux platform-support roots so
  we can tell at a glance when the Docker path has a real source-built support
  tree versus only a staged engine root
- the report also lists the Linux platform-support search roots that were
  checked, so the upstream note can distinguish a missing tree from an
  unsearched one
- the report path now also prints the discovered support roots and public
  archive inputs before it launches Docker, which keeps the support-tree
  evidence visible even when the lane is running from a staged zip

## Source-Built Proof Checklist

The staged archive path is useful evidence, but the long-lived upstream story
still benefits from a source-built Linux support tree before we treat the Docker
lane as fully general and upstream-defensible.

Use the current Linux matrix as the version anchor:

- `5.7` as the baseline Linux proof lane
- `5.8` as the forward-verification lane

The live route should exercise the explicit support-tree override:

```bash
cesium-unreal-linux-docker build-plan --engine-version 5.8
```

When we exercise it for real, capture the following in the packet:

- exact Unreal version
- Linux host image or distro
- compiler and sysroot/toolchain details
- whether a mounted source-built Linux support tree was present
- whether the path used `--linux-platform-support-root`
- command used
- whether the failure happened in source build, plugin package, editor open, or runtime smoke

To inspect the repo evidence and generate a report packet, use:

```bash
cesium-unreal-linux report
```

The top-level wrapper also exposes the same lane as:

```bash
cesium-unreal-linux report
```

To run the same inspection inside the cached Linux Docker image, use:

```bash
cesium-unreal-linux-docker report --engine-version 5.8
```

If a local Linux-ready Unreal engine root exists, the Docker wrapper will look
in `C:\Users\Public\Unreal` first, then scan installed `UE_*` roots.
