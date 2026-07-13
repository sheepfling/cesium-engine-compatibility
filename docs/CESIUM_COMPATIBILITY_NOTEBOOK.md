# Cesium Compatibility Notebook

This notebook is the single, reviewer-friendly structure for Cesium fork work in
this repo.

Use it when you need to answer, without guessing:

1. Which Cesium source version did we work from?
2. Which fork or vendor route does the fix belong to?
3. Which host, platform, and architecture were we proving?
4. What still needs to go green before the PR is defensible?

## Canonical Packet Chain

Keep the packet chain stable:

- [Cesium fork workpack](./CESIUM_FORK_WORKPACK.md)
- [Cesium engine matrix](./CESIUM_ENGINE_MATRIX.md)
- [Cesium visual proof command](../tools/build_cesium_visual_proof.py)
- [Cesium compatibility packet](./CESIUM_PR_PACKET_SUMMARY.md)

The workpack is the source-of-truth index for exact revision and host coverage.
The engine matrix and compatibility packet are reviewer-facing rollups.

## Source Version Anchors

Record the source version in the same place every time:

| Surface | Source Version Anchor | Where It Comes From | Notes |
| --- | --- | --- | --- |
| Unreal | `2.28.0` | `external/cesium/cesium-unreal/CesiumForUnreal.uplugin` | This is the Cesium for Unreal plugin version we should cite in the notes and PR narrative. |
| Unity | `1.24.0` | `external/cesium/cesium-unity/package.json` | This is the current Cesium for Unity package version in the local checkout. |
| Godot | commit-tracked community route | `Battle-Road-Labs/3D-Tiles-For-Godot` | This route is not semver-packaged like the official Cesium plugins; use the exact checkout commit and branch in the workpack. |

For Godot, keep the version language honest:

- cite the exact checkout commit in the workpack
- keep the branch name visible when it matters
- avoid implying semver parity when the route is actually commit-tracked

## Host And Platform Matrix

Use the same host model everywhere:

| Engine | Windows x86_64 | Linux x86_64 | macOS x86_64 | macOS arm64 |
| --- | --- | --- | --- | --- |
| Unreal | verified | verified | planned | planned |
| Unity | verified | planned | planned | planned |
| Godot | verified | verified | planned | planned |

Keep Apple Intel and Apple Silicon separate whenever a macOS proof exists or is
planned. Do not collapse them into one bucket.

## What Each Packet Must Say

Every fork note should be able to answer:

- exact source version or checkout commit
- fork target
- host OS
- host architecture
- engine version or package version
- command used
- evidence path
- failure class or success proof
- whether the lane is verified or still planned

## PR Defense Checklist

Before calling a fork packet "ready", make sure it can show:

1. the exact source version we started from
2. the exact host and architecture we proved
3. the exact command that was run
4. the artifact or log tail that proves the result
5. the next lane that remains open

## Update Rule

If you change the source-route prep, host discovery, or example workflow in a
way that affects fork evidence, update the workpack first and then update the
engine notes. That keeps the PR story reproducible.
