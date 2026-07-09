# Cesium Vanilla Godot Example

This is the repo-owned pure-Cesium Godot example-project scaffold for the current
Cesium-style route.

It is intentionally separate from the community `3D-Tiles-For-Godot` vendor
checkout.

Current purpose:

- prove a clean Godot project exists in repo-owned layout
- keep addon import/version proof separate from example-scene proof
- give us a stable home for a small tileset scene once the vendor lane grows past doctor-only checks
- keep the Windows-native 4.7 compatibility story explicit
- reserve separate proof notes for Linux and macOS Godot lanes in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`

Next expected steps:

1. Copy or link `addons/cesium_godot` from the vendor checkout during setup.
2. Enable the plugin in project settings.
3. Keep the scene pure Cesium with no FastDIS dependency.
4. Add a rerunnable proof lane that opens the project after the Godot vendor lane grows scratch-project smoke.
5. Record any Windows-native forward or backward drift in `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`.
