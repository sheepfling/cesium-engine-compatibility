# Cesium Fork Workpack

This document defines the standard reporting surface for Cesium compatibility
work across the engine forks.

Use the workpack when you need one place to answer all of these questions:

1. Which Cesium workspace commit was the work based on?
2. Which source-route checkouts and branches were present?
3. Which engine fork are we targeting?
4. Which host and platform combinations still need to go green?

## Canonical Command

```bash
cesium-fork-workpack
```

## Canonical Locations

- packet JSON: `artifacts/reports/cesium_fork_workpack/cesium_fork_workpack.json`
- packet Markdown: `artifacts/reports/cesium_fork_workpack/cesium_fork_workpack.md`
- engine host rows: `artifacts/reports/cesium_fork_workpack/<engine>/<host>-<arch>.json`

## Required Fields

The workpack should always surface:

- the Cesium workspace branch and `HEAD` commit
- the source-route root under `external/cesium`
- inspected source-route repos, branches, and commits
- one engine card for Unreal, Unity, and Godot
- one host row per engine/platform/architecture combination
- the commands required to get each host row green
- the docs and packet paths that hold the supporting evidence
- whether a lane requires a separate version-specific project root

## Host Model

Keep the host model explicit:

- Windows uses `x86_64`
- Linux uses `x86_64`
- macOS is split into `x86_64` and `arm64`

That split keeps the Apple Silicon story visible instead of folding it into a
single Mac bucket.

## Relationship To Other Packets

- `cesium-engine-matrix` keeps the version coverage visible.
- `cesium-execution-audit` keeps host readiness and blockers visible.
- `cesium-planned-routes` keeps the remaining bootstrap routes commandable.
- `cesium-visual-proof` keeps the screenshot/camera evidence contract visible.
- `cesium-compatibility-packet` unions the packet set into the reviewer-facing
  rollup.

## Working Rule

If you update the compatibility work for a fork, update the workpack first so
the current Cesium version, source-route state, host coverage, and proof paths
stay obvious in one place.

If a lane needs a version-specific project variant, record the split in
[`CESIUM_PROJECT_SEGREGATION.md`](./CESIUM_PROJECT_SEGREGATION.md) and keep the
base scaffold untouched.
