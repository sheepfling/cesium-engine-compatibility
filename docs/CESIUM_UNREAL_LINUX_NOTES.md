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
- the archive route uses host-side staging before Docker launch; that keeps the
  engine tree unpacked once on the host and lets us copy any discovered Linux
  support tree into the staged root before the container run
- the Docker lane uses the repo-owned plugin checkout by default and accepts an
  explicit `--plugin-root` or `CESIUM_UNREAL_PLUGIN_ROOT` override for a
  separately prepared local plugin tree
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
- the lane uses the repo-owned plugin tree, which gives the build the expected
  `Source/ThirdParty/include` layout
- the host-side staging root is short enough to avoid the earlier Windows path
  length issues
- the public archive remains an evidence input rather than the thing that makes
  the build green
- the 5.8 run is recorded in
  `artifacts/reports/unreal_linux_docker/cesium_unreal_linux_build_5.8.log`
  and contains `Result: Succeeded`, `BUILD SUCCESSFUL`, and `ExitCode=0`
- the 5.8 source checkout used the fork branch `fork/unreal-57-58-verify`
  through commits `3275999d` and `da44a289`; those remove Clang 20
  warnings-as-errors in the Unreal Linux compile path
- the Docker client wrapper exceeded its host-side wait while the successful
  container was still being reaped, so the build log is the authoritative
  result for this run; the container was cleaned up afterward

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

The Linux visual-proof lane has now reached Unreal runtime startup, but it is
not green on this host. WSL-native Vulkan now exposes the host-provided GPUs
through Mesa `dzn`/D3D12, including the NVIDIA device, while Docker Desktop
and the WSL-local Docker daemon both fail to create a D3D12 device inside a
container. This means the current viable execution boundary is the WSL distro
itself, not a Linux container.

The WSL-native Unreal 5.8 run reaches the real NVIDIA device and then crashes
while Unreal resets its timestamp query pool:

```text
libvulkan_dzn.so -> FVulkanQueryPool::Reset -> FVulkanDynamicRHI::InitInstance
```

That is a Vulkan `dzn`/Unreal runtime compatibility blocker. It is not a
missing GPU, a Cesium tileset-load failure, or acceptable visual proof. The
launcher must fail closed when this signature occurs and must not publish a
screenshot packet.

The current runtime logs are:

- `artifacts/reports/unreal_visual_proof/linux/unreal_linux_proxy_5.8.log`
- `artifacts/reports/unreal_visual_proof/linux/unreal_linux_proxy_5.8_llvmpipe.log`

The WSL-native NVIDIA attempt is recorded in
`artifacts/reports/unreal_visual_proof/linux/unreal_wsl_proxy_norhi.log`.
The WSL-native control attempt is recorded in
`artifacts/reports/unreal_visual_proof/linux/unreal_wsl_proxy_5.8.log`.

Both runs correctly stopped before screenshot capture. This is a host
renderer-capability blocker, not evidence that Cesium tiles failed to load.
The next meaningful step is to rerun the same lane on a Linux host or Docker
runtime with GPU/Vulkan passthrough and then apply the six-image comparison
gate.

Run the hardware-agnostic preflight with:

```text
cesium-unreal-linux-gpu-probe --gpus all
```

For the combined Windows/WSL/Docker diagnosis, use:

```text
cesium-unreal-linux-gpu-doctor --distro Ubuntu --gpus all
```

`--gpus all` delegates device selection to Docker. The report records the
actual host GPU and Vulkan device, without assuming NVIDIA, RTX 5080, or any
other specific model.

The doctor reports `partial` when WSL has a non-CPU Vulkan device but Docker
does not. That is the expected state for this WSLg setup and means the next
runtime experiment should run directly in WSL. A `pass` still requires both
WSL and Docker to expose a render-capable Vulkan device.

Current follow-up:

- launcher Unreal installs are good enough for inspection and report lanes
- the Docker build now completes successfully on both the 5.7 baseline and 5.8
  forward-verification lanes when the staged archive and repo-owned plugin
  checkout are available
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
