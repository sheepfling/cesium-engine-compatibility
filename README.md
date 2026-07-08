# cesium-engine-compatibility

Focused repository for Cesium compatibility work.

Current scope:

- Cesium source-route preparation
- Cesium vendor compatibility notes
- repo-owned pure-Cesium example scaffolds
- fork/PR guidance for Cesium-related upstream fixes

Top-level command:

- `python cesium.py bootstrap`
- `python cesium.py prepare-source-route`
- `python cesium.py example doctor --engine unreal`

Install and run:

```bash
python -m pip install -e .
python cesium.py bootstrap
cesium prepare-source-route
cesium example doctor --engine unreal
```

For a fresh host, `python cesium.py bootstrap` is the easiest first step. It
creates a local dev dependency prefix, prepares scratch roots, and runs the
Cesium CLI smoke plus the bootstrap smoke in one pass. On Windows, it prefers
a short scratch root under `C:\tmp\cesium_dev` so the path stays simple even
when the repo is nested deeper in the filesystem.

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
