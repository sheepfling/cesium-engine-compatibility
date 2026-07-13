# Cesium Vanilla Unity Example

This is the repo-owned pure-Cesium Unity example-project scaffold.

It is intentionally separate from the upstream `cesium-unity` package route.

Current purpose:

- prove a clean Unity example project exists in repo-owned layout
- keep vendor package import/compile proof separate from example-scene proof
- give us a stable home for a small geospatial demo scene once the vendor lane is green
- keep the editor-version compatibility story explicit for the current
  example-project file, now `6000.6.0b2`, while the baseline proof lane remains
  `6000.5.0f1`

Version-specific markers:

- `ProjectSettings/ProjectVersion.txt` is pinned to `6000.6.0b2` for the current example project.
- `Assets/CesiumVisualProofCapture.cs` is the version-aware proof harness for the Unity visual lane and writes `visual_proof_manifest.json` beside the six canonical PNGs.
- The lane contract lives in [`VisualProofContract.md`](./VisualProofContract.md).
- The baseline proof lane remains `6000.5.0f1`, so version drift should be called out in the notes when that baseline changes.
- Generated editor/runtime state stays out of the repo under `Library/`, `Logs/`, `Temp/`, `UserSettings/`, `build/`, and `Assets/CesiumExampleBuild/Generated/`.
- If we need to keep a version-specific Unity variant around, it should be split into a separate project workpack rather than mixed into the base scaffold.

See [`docs/CESIUM_PROJECT_SEGREGATION.md`](../../../../../docs/CESIUM_PROJECT_SEGREGATION.md)
for the repo-wide split rule.

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
5. Record any forward or backward editor drift in `docs/CESIUM_UNITY_6000_5_FINDINGS.md`.
