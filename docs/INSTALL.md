# Install

The easiest first-run path for this repository is:

```bash
python -m pip install -e .
python cesium.py bootstrap
```

That bootstrap command does three things:

1. installs the editable local dev extra into a dedicated prefix
2. creates a short scratch root for temp state and artifacts
3. runs the Cesium CLI smoke and bootstrap smoke tests

On Windows, the bootstrap defaults to `C:\tmp\cesium_dev` so the scratch path
stays short even if the repo lives several directories deep.

If you only want the source-route prep without the local smoke lane, run:

```bash
python cesium.py prepare-source-route
```

If you want the example-lane preview instead, run:

```bash
python cesium.py example doctor --engine unreal
```
