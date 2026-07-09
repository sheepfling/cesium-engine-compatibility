# Install

The easiest first-run path for this repository is:

```bash
python -m pip install -e .[dev]
cesium-bootstrap
```

That editable install plus bootstrap command does three things:

1. creates a dedicated virtualenv and installs the editable local dev extra
2. creates a short scratch root for temp state and artifacts
3. runs the Cesium CLI smoke and bootstrap smoke tests

On Windows, the bootstrap defaults to `C:\tmp\cesium_dev` so the scratch path
stays short even if the repo lives several directories deep.

The same flow also works as `python -m cesium bootstrap` if you want to stay
entirely in package/module form.

If you only want the source-route prep without the local smoke lane, run:

```bash
cesium-prepare-source-route
```

If you want the example-lane preview instead, run:

```bash
cesium-example doctor --engine unreal
```

If you want the quickest Godot host check, run:

```bash
cesium-godot-doctor
```

That command defaults to the Windows native lane and prints the discovered
public Godot roots, expected export templates, and next-step guidance when a
template pack is missing.

If you want the remaining cross-platform bootstrap inventory instead, run:

```bash
cesium-planned-routes
```

That packet keeps the Unreal Linux parity follow-up, Unity Linux/Docker,
Unity macOS, and Godot macOS routes commandable without mixing them into the
build-green evidence.

The discovery helpers will also look in the public alternate roots by default,
including `C:\Users\Public\Unreal`, `C:\Users\Public\Godot`, and
`C:\Users\Public\Unity`. If you mount engines elsewhere, set
`FASTDIS_UNREAL_ROOTS`, `FASTDIS_GODOT_ROOTS`, or `FASTDIS_UNITY_ROOTS` to add
those locations to the scan.

For the reviewer-facing note that turns the matrix and audit into a fix list,
run:

```bash
cesium-cross-platform-fix-notes
```

For the companion reviewer note that turns the evidence into a fix-oriented
checklist, see `docs/CESIUM_CROSS_PLATFORM_FIX_NOTES.md`.
