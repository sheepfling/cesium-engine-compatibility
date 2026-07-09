# Cesium Godot Cross-Platform Notes

This note tracks the repo-owned Godot native lane across Windows, Linux, and
macOS.

The macOS target is intentionally split into Intel `x86_64` and Apple Silicon
`arm64` when we get a real host proof run, because those are separate
compatibility surfaces even when the editor version matches.

The goal is to keep the current Windows baseline honest while making room for
separate Linux and macOS native proof lanes that share the same source route
but not the same host assumptions.

## Current Lane Shape

- source route: `Battle-Road-Labs/3D-Tiles-For-Godot`
- pinned editor family: `4.7`
- current baseline target: `windows`
- expansion targets: `linux`, `mac`
- public engine discovery prefers `C:\Users\Public\Godot`

## Current Contract

The shared Cesium example workflow already tracks the Godot route as a
first-class example lane. What changes per host is the compatibility framing:

- Windows: baseline import/open and renderer proof
- Linux: separate native import/open proof
- macOS: separate native import/open proof

The live Godot report lanes have now been exercised locally for the Windows
and Linux native targets, while macOS remains the next live proof gap:

- `cesium-example report --engine godot --native-target windows`
- `cesium-example report --engine godot --native-target linux`
- `cesium-example report --engine godot --native-target mac`

The macOS route is also commandable in the lane bundle as
`cesium-plugin-lanes --dry-run --lanes godot-host-mac`, which keeps the future
proof path visible alongside the Windows and Linux lanes.

## macOS Packet Shape

When the real macOS lane lands, the packet should keep the same shape as the
Windows and Linux lanes:

- report name: `godot-mac`
- command bundle: `cesium-plugin-lanes --dry-run --lanes godot-host-mac`
- capture focus: editor version, host architecture, addon revision, and the
  specific import/open or build proof message
- artifact family: `artifacts/reports/cesium_examples/`

That keeps the pending route explicit while still matching the report style we
already use for the Windows and Linux native lanes.

The local Godot editor also proved it can open the repo-owned example project in
headless import mode on Windows:

```bash
"C:\Users\Public\Godot\engines\windows\Godot_v4.7-stable_win64.exe\Godot_v4.7-stable_win64.exe" --headless --path "C:\Users\peanu\GIT\sheepfling\cesium-engine-compatibility\extensions\cesium\examples\godot\CesiumVanillaExample" --import --quit
```

That smoke completed successfully and is not a full export/build proof yet, but
it does exercise the actual repo-owned project path rather than just the
version discovery layer.

The Linux editor also proved it can open the repo-owned example project inside
Docker with the same headless import flow, so the Linux native lane is now a
real proof lane rather than a discovery-only placeholder.

The repo-local Godot Linux Docker lane now passes from this checkout, which
means the Docker path is runnable without depending on a preinstalled wrapper on
`PATH`.

The repo now also carries explicit export/build scaffolding for the pinned
Godot lane:

- `extensions/cesium/examples/godot/CesiumVanillaExample/export_presets.cfg`
- `cesium-godot-example-build --build-target windows --godot-version 4.7`
- `cesium-godot-linux-docker --mode build --build-target linux --godot-version 4.7`

Those commands are not proof-green yet, but they make the Windows export and
Linux Docker export paths part of the same repo-owned workflow shape as the
report lanes.

The local discovery helper now recognizes the public `win64.exe` and
`linux.x86_64` Godot install layout, so the host audit can see the full four
version set on both Windows and Linux. It also accepts a configured install
root directly when that path is already the version directory, which keeps the
Docker mount path closer to the actual editor layout.

That means a hand-mounted Godot install can be discovered either as the parent
engine root or as the version directory itself, without losing the lane shape.

Each platform should keep its own failure notes, even though all three reuse the
same source-route checkout and example scaffold.

## macOS Proof Checklist

The macOS lane is still planned, but it should use the same evidence shape as
the Windows and Linux lanes once a host is available.

Use the installed version spread as the compatibility anchor:

- `4.6.3-stable` as compatibility evidence
- `4.7-stable` as the current baseline
- `4.7.1-rc1` as release-candidate evidence
- `4.8-dev1` as forward verification

The planned route is:

```bash
cesium-plugin-lanes --dry-run --lanes godot-host-mac
```

When we exercise it for real, capture the following in the packet:

- exact Godot editor version
- host OS and architecture
- addon revision or checkout commit
- target being exercised
- command used
- log tail or failure message
- whether the issue is import-time, editor-open, renderer, export, or scene/runtime related

When generating reports, use host-specific filenames:

- `godot-windows`
- `godot-linux`
- `godot-mac`

## Public Search Roots

Search these first when looking for local Godot editor installs:

- `C:\Users\Public\Godot\engines\windows`
- `C:\Users\Public\Godot\engines\linux`

The Windows tree uses directories like `Godot_v4.7-stable_win64.exe`, and the
Linux tree uses directories like `Godot_v4.7-stable_linux.x86_64`.

Add a macOS equivalent once a real macOS lane lands.

The Linux evidence matrix is tracked separately in
`docs/CESIUM_GODOT_LINUX_VERSION_MATRIX.md`.

## Evidence To Capture

When a live lane fails or succeeds, record:

- exact Godot editor version
- host OS and architecture
- addon revision or checkout commit
- command used
- log tail or failure message
- whether the issue is import-time, editor-open, renderer, export, or scene/runtime related

## Next Step

The next useful step is to add one native smoke per host:

1. Windows import/open smoke
2. Linux import/open smoke
3. macOS import/open smoke

Keep those smokes separated in documentation and reporting so the host-specific
compatibility story stays obvious.
