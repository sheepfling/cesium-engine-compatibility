# Cesium Visual Proof Plan

This note is the human-readable plan for the screenshot proof packet.

Current goal:

- get the Windows route totally done for Unreal, Unity, and Godot
- make each engine produce proper visual evidence for proxy-earth and Cesium-earth
- keep the evidence commensurate across engines, with the same canonical Windows capture set
- keep discovery, launch, capture, normalization, and comparison programmatic, host-aware, and robust
- treat launch failures, license blockers, black/gray frames, empty frames, and drift as first-class failures
- do not call the Windows route done until the packet can boot, capture, normalize, and compare without manual cleanup on this host

The machine-readable contract lives in `cesium-visual-proof`. This note explains
how to use it first on Windows, where we can compare the capture output against
the current host without mixing in other platform variables.

## What The Packet Fixes

The visual-proof packet standardizes:

- canonical camera poses
- output roots for screenshots
- one target row per engine and host/architecture combination
- a clear Windows-first capture order
- a `visual_proof_manifest.json` contract beside each capture root so tools can
  filter the right screenshots without guessing from directory names alone
- canonical camera-shot metadata inside the manifest so the proof root is
  self-describing instead of filename-only

## Windows Done Bar

The Windows route is only "done" when all of the following are true:

- Unreal, Unity, and Godot each launch on Windows without manual cleanup
- each engine emits the six canonical PNGs for proxy-earth and Cesium-earth
- each capture root includes a `visual_proof_manifest.json`
- the normalization step produces a shared evidence tree for each engine
- the compare gate is programmatic and rejects obvious drift or empty frames
- the launcher/reporting flow is robust enough to recover from transient host
  noise without relying on documentation assertions as the proof itself
- the packet can be re-run on this host and still produce the same engine rows,
  so the result is repeatable rather than a one-off success

## Windows First Order

Start here on the current host:

1. Unreal Windows `x86_64`
2. Unity Windows `x86_64`
3. Godot Windows `x86_64`

That order gives us the cleanest first captures because the screenshot outputs
can be validated against the same host that generated the packet.

## Canonical Shot Set

Every target should emit the same three named screenshots:

- `overview`
- `oblique`
- `close`

Keep the camera positions and field-of-view ladder consistent across engines
whenever the scene layout allows it. The current canonical Windows proof set is
the `overview` and `oblique` shots centered on the origin, plus a `close`
shot aimed at the close marker with `55`, `45`, and `50` degree fields of
view. If one engine needs a special capture path, keep the packet wording
explicit about the difference.

Each target should emit both proxy-earth and Cesium-earth variants for the same
three shots, so the shared output contract is six PNGs per engine/host row:

- `proxy_overview`, `proxy_oblique`, `proxy_close`
- `cesium_overview`, `cesium_oblique`, `cesium_close`

## Windows Capture Pattern

For each Windows target:

1. open the example project
2. frame the canonical camera pose
3. capture both the proxy-earth and Cesium-earth variants where the engine supports both
4. save the six named PNGs under the reported capture root for each engine row
5. write a `visual_proof_manifest.json` beside the capture root with the engine,
   target, architecture, screenshot path list, and camera-shot metadata
6. keep the exact command and path in the packet

For Unreal Windows, the checked-in automation lane is
`Cesium.VisualProof.Windows.ProxyEarth`, which writes into the Unreal editor
`Saved/Screenshots/WindowsEditor` tree and should be normalized into the same
packet as the Unity and Godot captures.

The packet does not invent the harness. It only keeps the expected output shape
visible so the eventual capture automation can be checked against the same
contract.

The programmatic gate for a real run is:

1. `cesium-visual-proof-contracts`
2. `cesium-visual-proof-roots`
3. `cesium-visual-proof-audit`

If you want a single command name, `cesium-visual-proof-check` is the alias for
the combined audit.

That sequence checks the checked-in contracts, validates the manifest-backed
roots, and composes the comparison gate into one auditable pass.

## Image Quality Gate

The capture step should be followed by a visual comparison pass that:

- compares the canonical shots across engines with perceptual-image metrics
- flags obvious drift even when a frame still "looks close" by eye
- treats black, gray, flat, or otherwise low-detail frames as hard failures
- rejects monotone captures with little color diversity or edge energy, even if
  the frame is not literally black
- keeps the proof packet honest when one lane silently renders garbage

## What To Record

When a Windows visual proof run lands, record:

- engine
- native target
- host architecture
- exact command
- capture root
- PNG paths
- whether the run was a dry-run, a manual capture, or an automated capture

## Next Expansion

Once the Windows-first path is proven, extend the same packet shape to Linux and
macOS without changing the contract.
