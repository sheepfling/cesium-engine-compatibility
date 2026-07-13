# Cesium Vanilla Unreal Example

This is the repo-owned pure-Cesium Unreal example-project scaffold.

It is intentionally separate from:

- the upstream Cesium plugin source route
- the Cesium vendor package/install smoke lane

## Purpose

This project is the place where the repo proves a minimal pure-Cesium Unreal
example, rather than depending on whatever the upstream sample project happens
to demonstrate.

The target bar is:

- open cleanly on supported Unreal lanes
- enable the Cesium plugin only
- load one canonical geospatial scene
- keep the project free of FastDIS dependencies
- produce a rerunnable demo and proof lane

Generated editor/runtime state stays out of the repo under `Binaries/`,
`Build/`, `DerivedDataCache/`, `Intermediate/`, `Saved/`, and `.vs/`.
If we need a version-specific Unreal variant, keep it in a separate project
workpack or lane report rather than folding it into this base scaffold.

The Windows proof lane is expected to normalize `Saved/Screenshots/WindowsEditor`
into `artifacts/reports/cesium_visual_proof/unreal/windows/x86_64/` and write
`visual_proof_manifest.json` beside the normalized PNGs.

The lane contract is also checked in as
[`VisualProofContract.md`](./VisualProofContract.md) so the output shape stays
easy to review next to the example project itself.

Version and lane markers:

- Unreal 5.7 is the current baseline Windows lane.
- Unreal 5.8 is the forward-verification lane.
- Linux stays a separate Docker-backed proof lane.
- The sample should stay segmented by lane in staging and reporting even
  though it remains a single repo-owned example tree.
- If Unreal needs a version-specific variant, put it in a separate project
  root and keep the base scaffold untouched.

Linux proof is tracked separately in `docs/CESIUM_UNREAL_LINUX_NOTES.md`.

See [`docs/CESIUM_PROJECT_SEGREGATION.md`](../../../../../docs/CESIUM_PROJECT_SEGREGATION.md)
for the repo-wide split rule.

## Current State

Current scaffold only:

- source-backed `.uproject`
- basic `Config/`
- minimal runtime module
- no committed content assets yet
- no automated demo lane yet

## Expected Plugins

The project descriptor currently expects only:

- `CesiumForUnreal`

## Next Steps

1. Materialize `/Game/Maps/CesiumVanillaEntry`.
2. Add a simple startup scene contract.
3. Add a doctor/build/demo workflow that proves the project opens with Cesium on
   supported Unreal versions.
