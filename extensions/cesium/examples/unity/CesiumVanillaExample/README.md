# Cesium Vanilla Unity Example

This is the repo-owned pure-Cesium Unity example-project scaffold.

It is intentionally separate from the upstream `cesium-unity` package route.

Current purpose:

- prove a clean Unity example project exists in repo-owned layout
- keep vendor package import/compile proof separate from example-scene proof
- give us a stable home for a small geospatial demo scene once the vendor lane is green

Current scaffold contents:

- `Packages/manifest.json`
- `ProjectSettings/ProjectVersion.txt`
- `Assets/README.md`
- [Assets README](./Assets/README.md)

Next expected steps:

1. Add the local-package Cesium dependency during operator setup.
2. Materialize a small geospatial entry scene.
3. Keep the scene pure Cesium with no FastDIS dependency.
4. Add a rerunnable proof lane that opens the project after the Unity vendor lane passes.
