# Cesium macOS Silicon Build Notes

This note records the current macOS scaffolding we use to keep Cesium engine
work reproducible on both Apple Silicon and Intel Macs.

The goal is to keep the macOS lane narrow and explicit:

1. discover the installed engine root before running a proof lane
2. keep the source-route checkout and fork workpack stable
3. preserve separate `arm64` and `x86_64` evidence where the engine supports
   both slices
4. record the exact command, version, and failure artifact when the lane does
   not go green

## Current Host-Discovery Rules

The shared engine-root discovery helpers now treat macOS as a first-class
surface:

- Unreal public roots are searched under `/Users/Shared/Epic Games`
- Unity public roots are searched under `/Applications/Unity/Hub/Editor` and
  `~/Applications/Unity/Hub/Editor`
- Godot public roots include `/Applications`, `~/Applications`, and
  `~/Dev/Godot`

That keeps the "what is installed on this host?" answer aligned with the
macOS proof route instead of only the Windows defaults.

## Current Proof Shape

The packet and example tooling keep the same core structure across hosts:

- version-aware source route preparation
- explicit host discovery
- a per-engine proof row
- a manifest-backed screenshot root
- a comparison gate after capture

For macOS, the important part is not a special packet shape. It is keeping the
same shape while the lane switches between Intel and Apple Silicon layouts.

## What To Watch For

Known macOS failure modes usually fall into one of these buckets:

- source route checkout drift
- editor or plugin binary layout drift
- architecture split mismatch between `arm64` and `x86_64`
- plugin/package build tooling that assumes the wrong host install root

If the lane fails, keep the artifact and record:

- engine
- version
- architecture
- command
- checkout commit
- log tail

## Relation To The Rest Of The Repo

This note is intentionally small. It should stay in sync with:

- `extensions/cesium/docs/CESIUM_SOURCE_ROUTE.md`
- `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`
- `extensions/cesium/tools/engine_root_discovery.py`
- `tools/build_cesium_visual_proof.py`

The macOS lane is only green when the packet, the discovery layer, and the
captured evidence all say the same thing.
