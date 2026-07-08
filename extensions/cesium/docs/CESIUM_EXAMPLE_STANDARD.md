# Cesium Example Standard

This document defines the repo-owned pure-Cesium example-project quality bar for Cesium
across Unreal, Unity, and Godot.

It is intentionally separate from the vendor-plugin lane.

## Why Split It

Two different questions matter:

1. does the upstream Cesium plugin install and open on the engine versions we support
2. do we ship a clean pure-Cesium example project that proves the vendor route well

The first question belongs to the vendor lane.
The second question belongs to the example lane.

For Cesium specifically, every supported engine path should have both lanes:

1. `Vendor lane`
   Plugin/package/addon compatibility on the supported engine version.
2. `Example lane`
   A repo-owned pure-Cesium small project that uses that vendor lane as a prerequisite.

We should not let a good upstream plugin hide a weak example project, and we
should not let a weak sample repo imply the plugin-core route is broken.

## Required Bar

Every Cesium example lane should prove:

1. `Open`
   The project opens cleanly on the supported engine version.
2. `Install`
   The Cesium plugin/package/addon is installed and enabled through a short,
   rerunnable setup path.
3. `Scene`
   A known geospatial scene loads with a predictable camera start.
4. `Purity`
   The project stays pure Cesium for this proof stage and does not require
   FastDIS or other repo-specific runtime plugins.
5. `Demo`
   A junior operator can run the example with a short documented flow.
6. `Proof`
   The lane emits a report showing setup state, plugin state, and scene/demo
   status.

## Current Engine Targets

- Unreal: first-class example lane target
- Unity: first-class example lane target
- Godot: first-class example lane target, but on a narrower current Cesium-style
  plugin surface

## Current Readiness Policy

- `Cesium Unreal Example` should be built after the Unreal vendor matrix is
  passing.
- `Cesium Unity Example` should be built after Unity package/install proof is
  pinned for the chosen editor lane.
- `Cesium Godot Example` should be built after the Godot vendor doctor grows
  into a scratch-project import/open smoke.

## Operator Flow

Start with:

```bash
python extensions/cesium/tools/prepare_cesium_source_route.py
python extensions/cesium/tools/cesium_example_workflow.py doctor --engine unreal
python extensions/cesium/tools/cesium_example_workflow.py doctor --engine unity
python extensions/cesium/tools/cesium_example_workflow.py doctor --engine godot
```

These doctor lanes are planning/quality gates over real repo-owned pure-Cesium example
project scaffolds. They still need live runtime automation to become full proof
lanes.
