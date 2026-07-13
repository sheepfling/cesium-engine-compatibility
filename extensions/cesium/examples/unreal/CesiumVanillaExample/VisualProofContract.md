# Cesium Unreal Visual Proof Contract

This file records the repo-owned visual-proof contract for the Unreal example
project. Windows and Linux use the same six canonical camera shots; Linux
requires a Vulkan-capable host because Unreal 5.8 removed desktop OpenGL.

## Canonical Windows Lane

- Engine: Unreal
- Native target: `windows`
- Architecture: `x86_64`
- Example project: `CesiumVanillaExample.uproject`

## Canonical Linux Lane

- Engine: Unreal
- Native target: `linux`
- Architecture: `x86_64`
- Renderer requirement: Vulkan `VP_UE_Vulkan_SM5`
- Docker fallback: only valid with GPU/Vulkan passthrough; Mesa llvmpipe is
  currently rejected by Unreal 5.8

## Capture Command

```text
UnrealEditor.exe CesiumVanillaExample.uproject -NoEOS -ExecCmds="Automation RunTests Cesium.VisualProof.Windows.ProxyEarth; Quit"
```

This lane is expected to execute `Cesium.VisualProof.Windows.ProxyEarth`
first, then `Cesium.VisualProof.Windows.CesiumEarth` in a second invocation.

## Raw Screenshot Root

- `Saved/Screenshots/WindowsEditor`

## Normalized Proof Root

- `artifacts/reports/cesium_visual_proof/unreal/windows/x86_64/`

## Normalized Manifest

- `artifacts/reports/cesium_visual_proof/unreal/windows/x86_64/visual_proof_manifest.json`

## Canonical Output Files

- `proxy_overview.png`
- `proxy_oblique.png`
- `proxy_close.png`
- `cesium_overview.png`
- `cesium_oblique.png`
- `cesium_close.png`

## Contract Notes

- The engine-side Unreal screenshot harness is leveraged from `external/cesium/cesium-unreal/Source/CesiumRuntime/Private/Tests/CesiumVisualProof.spec.cpp`.
- The automation test names are platform-aware: `Cesium.VisualProof.Windows.*`
  on Windows and `Cesium.VisualProof.Linux.*` on Linux.
- Normalize only the six canonical PNGs into the shared proof root.
- Keep the manifest beside the normalized PNGs so downstream tools can filter
  out stray editor artifacts and read the canonical camera shot metadata.
- Keep this contract in sync with `tools/build_cesium_visual_proof.py`,
  `tools/proof_runs.py`, and `docs/CESIUM_VISUAL_PROOF_PLAN.md`.
