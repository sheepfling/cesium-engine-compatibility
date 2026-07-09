# Cesium macOS Silicon Build Notes

This note kicks off the macOS proof lane for the Cesium source-route and
example workflows in this repo.

The immediate goal is not to pretend macOS is green. The goal is to keep the
lane explicit, commandable, and fork-friendly so we can start collecting real
evidence on both Apple Silicon `arm64` and Intel `x86_64`.

## What We Can Reuse

The Packet-Stoat macOS branch pointed at three useful ideas that carry over
cleanly here:

1. keep the source-route prep flexible enough to point at fork remotes
2. keep macOS proof notes separate from Windows and Linux proof notes
3. treat macOS as a split-architecture lane, not a single host bucket

This repo now supports fork/branch overrides for the public Cesium source-route
prep helper:

- `FASTDIS_CESIUM_UNREAL_REMOTE`
- `FASTDIS_CESIUM_UNREAL_BRANCH`
- `FASTDIS_CESIUM_UNITY_REMOTE`
- `FASTDIS_CESIUM_UNITY_BRANCH`
- `FASTDIS_CESIUM_UNREAL_SAMPLES_BRANCH`
- `FASTDIS_CESIUM_GODOT_REMOTE`
- `FASTDIS_CESIUM_GODOT_BRANCH`

Those are the knobs we want when we start carrying macOS-specific proof work
through forked remotes.

## Current macOS Contract

The repo-owned example workflow already treats macOS as a first-class native
target for Unreal, Unity, and Godot, but the macOS lanes are still planned
until we have host evidence.

Expected command shape:

```bash
cesium-example doctor --engine unreal --native-target mac
cesium-example doctor --engine unity --native-target mac
cesium-example doctor --engine godot --native-target mac
```

Planned macOS evidence should always capture:

- exact editor or engine version
- host architecture
- remote or fork revision
- command used
- failure or success tail
- whether the issue is install, import, open, build, export, or runtime related

## Proof Checklist

When we get a real macOS lane running, keep the first packet narrow:

1. prove source-route prep against the intended fork or upstream remote
2. prove one native import/open or build smoke per engine
3. record separate notes for `arm64` and `x86_64`
4. keep the macOS lane commandable from the repo root
5. avoid folding macOS-only fixes into the Windows or Linux proof notes

## Next Step

The next useful step is to turn this note into a live packet by wiring in the
actual macOS discovery and build evidence, starting with the engine that fails
first on this host.
