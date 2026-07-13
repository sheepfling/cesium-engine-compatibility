# Cesium Godot Visual Proof Contract

This file records the repo-owned Windows visual-proof contract for the Godot
example project.

## Canonical Windows Lane

- Engine: Godot
- Native target: `windows`
- Architecture: `x86_64`
- Example project: `CesiumVanillaExample`
- Version-aware proof harness: `scripts/VisualProofRunner.gd`

## Capture Command

```text
cesium-godot-aggressive-launcher --native-target windows --max-versions 1
```

## Normalized Proof Root

- `artifacts/reports/cesium_visual_proof/godot/windows/x86_64/`

## Normalized Manifest

- `artifacts/reports/cesium_visual_proof/godot/windows/x86_64/visual_proof_manifest.json`

## Canonical Output Files

- `proxy_overview.png`
- `proxy_oblique.png`
- `proxy_close.png`
- `cesium_overview.png`
- `cesium_oblique.png`
- `cesium_close.png`

## Contract Notes

- Keep the six canonical PNGs plus `visual_proof_manifest.json` in the shared
  proof root.
- Keep the manifest pose-aware so downstream tools can read the canonical
  camera-shot metadata, not just the PNG filenames.
- Keep this contract in sync with `tools/build_cesium_visual_proof.py`,
  `tools/godot_aggressive_launcher.py`, and `docs/CESIUM_VISUAL_PROOF_PLAN.md`.
