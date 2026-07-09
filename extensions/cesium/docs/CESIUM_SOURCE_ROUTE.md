# Cesium Source Route

This note records the current source-first route for Cesium compatibility work.
For this repository, Cesium is an early proving ground: every supported engine
lane should first answer whether the public Cesium plugin route installs,
opens, and supports a minimal project on the versions we claim to support.

That makes Cesium both:

- a light-up gate for our engine routes
- an early-warning lane for upstream breakage that we can hand back quickly as
  focused fixes or evidence

## Public Repositories

Observed in the CesiumGS and Battle-Road-Labs GitHub organizations on
2026-07-01:

- `CesiumGS/cesium-unreal`
- `CesiumGS/cesium-unreal-samples`
- `CesiumGS/cesium-unity`
- `Battle-Road-Labs/3D-Tiles-For-Godot`

## Fork Remotes

When you are ready to carry fixes in your own remotes, the intended fork
targets are:

- [sheepfling/cesium-unreal](https://github.com/sheepfling/cesium-unreal)
- [sheepfling/cesium-unity](https://github.com/sheepfling/cesium-unity)
- [sheepfling/3D-Tiles-For-Godot](https://github.com/sheepfling/3D-Tiles-For-Godot)

These do not all have the same status:

- `cesium-unreal` is the official Cesium Unreal plugin
- `cesium-unity` is the official Cesium Unity plugin
- `cesium-unreal-samples` is the official sample-project lane for Unreal
- `3D-Tiles-For-Godot` is a community Godot plugin, not an official CesiumGS
  product surface

The engine forks still rely on upstream `CesiumGS/cesium-native` for their
submodule bootstrap until a dedicated fork exists for that dependency.

That governance difference matters when we compare parity claims.

## Compatibility Policy

Use Cesium as a selective compatibility route, not as a repo-wide dependency.

The narrow compatibility question is:

1. can the current public source route be prepared reproducibly
2. can the plugin package or install on our supported engine versions
3. can a clean scratch project open with the plugin enabled
4. if not, can we produce exact failure evidence and a patch candidate quickly

The broader product-parity question stays separate:

- official Unreal and Unity plugins are the parity reference
- the Godot 3D Tiles route is a narrower capability lane until proven otherwise

## Unreal Route

Current public Cesium Unreal plugin route:

- source plugin repo: `CesiumGS/cesium-unreal`
- richer sample repo: `CesiumGS/cesium-unreal-samples`
- working branch policy for source prep: `main`
- Linux is a supported native target, but it gets its own host/toolchain notes
  in `docs/CESIUM_UNREAL_LINUX_NOTES.md`

Lane policy:

- primary proof lane: package plugin and install it into a clean scratch
  project
- secondary proof lane: open or exercise the public sample project after the
  plugin-core lane already passes
- Windows source-development uses the samples checkout with the plugin exposed
  under `Plugins/cesium-unreal` so Unreal can discover the local source route
  without relying on a marketplace install
- Unreal Linux proof uses `cesium-unreal-linux
  report` as the repo-owned inspection/report entry point

Why split them:

- plugin-core failure belongs with Cesium for Unreal
- sample-project failure may be content, dependency, or host drift

## Unity Route

Current public Cesium Unity plugin route:

- source plugin repo: `CesiumGS/cesium-unity`
- working branch policy for source prep: `main`
- current proof lane: `6000.5.0f1`
- repo-owned example project version file: `6000.6.0b2`

Lane policy:

- treat Cesium Unity as an official plugin compatibility lane
- use install/import smoke first
- only broaden into richer sample or parity checks after the base lane is green
- keep forward/backward editor drift notes in
  `docs/CESIUM_UNITY_6000_5_FINDINGS.md`
- keep the current Unity version/package matrix in
  `docs/CESIUM_UNITY_VERSION_MATRIX.md`

## Godot Route

Current public Godot Cesium-style route:

- source plugin repo: `Battle-Road-Labs/3D-Tiles-For-Godot`
- working branch policy for source prep: `master`
- current repo pin: `4.7`

Important boundary:

- this is a community Godot 4 GDExtension focused on 3D Tiles capabilities
- it should not be described as full official Cesium product parity unless
  direct evidence says so
- Windows-native compatibility notes live in
  `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`
- the four Windows evidence builds are tracked in
  `docs/CESIUM_GODOT_WINDOWS_VERSION_MATRIX.md`
- the four Linux evidence builds are tracked in
  `docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`
- Linux and macOS compatibility notes live in
  `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`

Lane policy:

- first prove version/layout compatibility
- then add scratch-project import/open smoke
- then classify exact parity gaps versus the official Unreal and Unity routes
- preserve Windows-native proof separately from Linux or macOS proof

## Current Workspace Mapping

The repo now exposes:

- `cesium-prepare-source-route`
- `cesium-example discover --engine unreal`
- `cesium-example doctor --engine unreal`
- `cesium-example report --engine unreal`
- `cesium-example full --engine unreal`
- `cesium-example doctor --engine unity`
- `cesium-example doctor --engine godot`

The Cesium example workflow currently owns:

- discover
- doctor
- report
- full

and tracks only the example scaffolds and source-route checkouts that live in
this repo.

## Checkout Layout And Future Forks

The current source-route prep uses fixed checkout roots under `external/cesium/`
so the repo workflows can stay stable while the public source routes are
being evaluated.

That layout is intentionally fork-friendly:

- keep the checkout directory names stable
- swap the Git remotes to your fork URLs when you are ready to carry fixes
- keep the workflow commands pointed at the same checkout roots
- let the forked repos carry the source patches and PR history

In other words, the current public checkouts are the staging area, and your
eventual Cesium forks should slide into those same roots without requiring a
workflow rewrite.

See also: [Cesium fork push plan](../../../docs/research/CESIUM_FORK_PUSH_PLAN.md).

## Prepare Command

Use this before live vendor work so the public-route checkouts are on the
expected branches and submodules are initialized where needed:

```bash
cesium-prepare-source-route
```

For raw source checkouts, branch prep is not enough by itself:

- run the example workflow doctor lanes after the source-route prep step
- verify the example scaffolds still match the checked-out source route
- capture any missing checkout or scaffold as a focused compatibility gap

## Early-Warning Workflow

Recommended operator order:

1. `cesium-prepare-source-route`
2. `cesium-example doctor --engine unreal`
3. `cesium-example report --engine unreal`
4. `cesium-example full --engine unreal`
5. `cesium-example doctor --engine unity`
6. `cesium-example report --engine unity`
7. `cesium-example doctor --engine godot`
8. `cesium-example report --engine godot`

When a live lane fails:

1. keep the failure artifact
2. reduce it to plugin-core versus sample/content failure
3. prepare a minimal repro against the public source route
4. capture exact engine version, commit, command, and logs
5. upstream the smallest credible fix or failure report quickly

## Messaging Guardrails

Safe:

- "Cesium is an early installability and compatibility gate for our engine lanes."
- "The official Cesium Unreal and Unity routes are part of our upstream-facing
  early-warning matrix."
- "The current Godot Cesium-style route is community-maintained and is tracked
  separately from official Cesium parity."

Unsafe:

- "Godot has full Cesium parity."
- "A sample-project failure proves the plugin is broken."
- "A private local patch means the public route is fixed."
