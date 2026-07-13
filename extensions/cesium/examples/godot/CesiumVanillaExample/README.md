# Cesium Vanilla Godot Example

This is the repo-owned pure-Cesium Godot example-project scaffold for the current
Cesium-style route.

It is intentionally separate from the community `3D-Tiles-For-Godot` vendor
checkout.

Current purpose:

- prove a clean Godot project exists in repo-owned layout
- keep addon import/version proof separate from example-scene proof
- give us a stable home for a small tileset scene once the vendor lane grows past doctor-only checks
- keep the Windows-native 4.7 compatibility story explicit
- reserve separate proof notes for Linux and macOS Godot lanes in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`

Version-specific markers:

- `project.godot` is the pinned Godot example-project config for the current proof lane.
- `scenes/StartupHealthProbe.tscn` and the scripts in `scripts/` are the version-aware proof harness.
- `scripts/VisualProofRunner.gd` writes the canonical six PNGs plus `visual_proof_manifest.json` into the proof root for the Windows lane.
- The lane contract lives in [`VisualProofContract.md`](./VisualProofContract.md).
- The launcher tracks the tested Godot versions: `4.6.3-stable`, `4.7-stable`, `4.7.1-rc1`, and `4.8-dev1`.
- Generated editor/runtime state stays out of the repo under `.godot/`, `build/`, and `logs/`.
- Cesium-earth proof requires a local `CESIUM_ION_ACCESS_TOKEN`, `CESIUM_ION_TOKEN`,
  or `CESIUMION_TOKEN` environment variable;
  the launcher passes it only to the isolated Godot process and never records its value.
- The Cesium lane fails closed unless the tileset update loop produces at least one
  rendered tile node. A screenshot by itself is not accepted as Cesium proof.
- If we need a version-specific variant of the example project, it should live in a separate workpack or report tree instead of being folded into the base scaffold.

See [`docs/CESIUM_PROJECT_SEGREGATION.md`](../../../../../docs/CESIUM_PROJECT_SEGREGATION.md)
for the repo-wide split rule.

Next expected steps:

1. Copy or link `addons/cesium_godot` from the vendor checkout during setup.
2. Enable the plugin in project settings.
3. Keep the scene pure Cesium with no FastDIS dependency.
4. Add a rerunnable proof lane that opens the project after the Godot vendor lane grows scratch-project smoke.
5. Record any Windows-native forward or backward drift in `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`.

For a local Cesium proof run on Windows, set the token in the current PowerShell
session and run the launcher. Do not commit the token or place it in a project file:

```powershell
$env:CESIUM_ION_ACCESS_TOKEN = "<your local Cesium ion token>"
python -m tools.godot_aggressive_launcher `
  --native-target windows `
  --godot-selector 4.7-stable `
  --split-proof-lanes
```
