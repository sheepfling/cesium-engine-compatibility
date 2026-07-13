# cesium-engine-compatibility

Focused repository for Cesium compatibility work.

Current scope:

- Cesium source-route preparation
- Cesium vendor compatibility notes
- repo-owned pure-Cesium example scaffolds
- fork/PR guidance for Cesium-related upstream fixes
- three-engine coverage across Windows, Linux native or Docker proxy, and macOS
- macOS coverage split into Intel `x86_64` and Apple Silicon `arm64` where the engine supports both

Top-level command:

- `cesium-bootstrap`
- `cesium-prepare-source-route`
- `cesium-godot-bootstrap`
- `cesium-host-inventory`
- `cesium-fork-workpack`
- `cesium-visual-proof`
- `cesium-visual-proof-contracts`
- `cesium-visual-proof-roots`
- `cesium-visual-proof-audit`
- `cesium-visual-proof-check`
- `cesium-godot-doctor`
- `cesium-example doctor --engine unreal`
- `cesium-planned-routes`
- `cesium-cross-platform-fix-notes`
- `docs/CESIUM_CROSS_PLATFORM_FIX_NOTES.md`

Install and run:

```bash
python -m pip install -e .[dev]
cesium-bootstrap
cesium-prepare-source-route
cesium-godot-bootstrap editor --godot-version 4.7-stable --native-target windows
cesium-host-inventory
cesium-fork-workpack
cesium-visual-proof
cesium-visual-proof-contracts
cesium-visual-proof-roots
cesium-visual-proof-audit
cesium-visual-proof-check
cesium-godot-doctor
cesium-example doctor --engine unreal
cesium-planned-routes
cesium-cross-platform-fix-notes
```

For a fresh host, `cesium-bootstrap` is the easiest first step after the
editable install. It creates a local dev dependency virtualenv, prepares scratch
roots, and runs the Cesium CLI smoke plus the bootstrap smoke in one pass. On
Windows, it prefers a short scratch root under `C:\tmp\cesium_dev` so the path
stays simple even when the repo is nested deeper in the filesystem.

`cesium-planned-routes` shows the remaining Unreal Linux, Unity Linux/Docker,
Unity macOS, and Godot macOS routes as a dedicated dry-run packet, which is a
useful second command on a fresh host after bootstrap.

`cesium-godot-doctor` is the quickest Godot-specific host check. It defaults to
the Windows native lane and reports the public Godot search roots, the expected
export template paths, and the next-step guidance when templates are missing.

`cesium-godot-bootstrap` is the fallback lane for staging Godot editor zips or
export templates into the public locations the discovery helpers already know
how to scan. Use `editor` for the engine zip and `templates` for the export
template pack. Both commands accept `--godot-version` for an exact tag or
`--godot-selector` for inclusive ranges like `4.7-stable..4.8-dev1`.
`cesium-godot-example-build` now accepts the same selector flow when you want
the build lane to pick the best matching installed editor.

`cesium-host-inventory` is the quickest way to see what engines, platforms,
architectures, and core apps are already discoverable on the current host.
Pass `--godot-selector` to trim the Godot runway view and
`--max-godot-matches` to keep the filtered list short when there are many
installed or downloadable targets.

`cesium-fork-workpack` is the standard compatibility work surface. It records
the exact Cesium workspace commit, the source-route checkout state, and the
per-engine/per-host checklist that should stay green for each fork.

`cesium-visual-proof` is the screenshot-plan packet. It records the canonical
camera poses and output locations for the Unreal, Unity, and Godot example
projects so the eventual capture harness can stay consistent across engines and
architectures. Windows is the first capture host, with the Windows-native lanes
listed in `docs/CESIUM_VISUAL_PROOF_PLAN.md`.

`cesium-visual-proof-contracts`, `cesium-visual-proof-roots`, and
`cesium-visual-proof-audit` are the programmatic gates that validate the checked
in contracts, the manifest-backed proof roots, and the composed contract/root/
comparison audit in one pass.

`cesium-visual-proof-check` is the single convenience command that runs the
combined visual-proof audit when you want one memorable gate to type.

`cesium-cross-platform-fix-notes` turns the current matrix, audit, and planned
routes packets into a reviewer-facing checklist for the remaining fixes.

`docs/CESIUM_CROSS_PLATFORM_FIX_NOTES.md` is the companion note for the
remaining compatibility work and fix-oriented reviewer checklist.

If you prefer module-style invocation, the same bootstrap flow also works as
`python -m cesium bootstrap`.

Imported during the split:

- `extensions/cesium/`
- `docs/CESIUM_FORK_LEDGER.md`
- `docs/INSTALL.md`
- `docs/CESIUM_EXAMPLE_STANDARD.md`
- `docs/research/CESIUM_FORK_PUSH_PLAN.md`
- `docs/research/CESIUM_SOURCE_ROUTE.md`

The next porting step is to keep the Cesium workflow helpers self-contained in
this repo so the source-route and example lanes do not depend on a broader
workspace.
