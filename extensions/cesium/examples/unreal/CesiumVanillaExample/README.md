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
