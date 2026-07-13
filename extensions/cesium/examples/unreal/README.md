# Cesium Unreal Example

The pure-Cesium Unreal example-project root now lives under:

- `extensions/cesium/examples/unreal/CesiumVanillaExample/`
- [Example project README](./CesiumVanillaExample/README.md)

That project is currently a source-backed scaffold, not yet a full demo.

For local source development on Windows, the Cesium Unreal samples checkout
should also expose the plugin under `Plugins/cesium-unreal` so Unreal can open
the project directly from source.

Linux stays a separate native proof lane and is tracked in
`docs/CESIUM_UNREAL_LINUX_NOTES.md`.

The repo keeps the Unreal work split by lane rather than by duplicate project:

- 5.7 baseline Windows proof
- 5.8 forward-verification Windows proof
- Linux Docker proof as a separate lane

That keeps the sample tree simple while still making the version split explicit
in the reports and notes.

If Unreal needs a version-specific project root, keep it separate from this
base scaffold and follow [`docs/CESIUM_PROJECT_SEGREGATION.md`](../../../../docs/CESIUM_PROJECT_SEGREGATION.md).
