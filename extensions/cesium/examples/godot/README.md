# Cesium Godot Example

Current pure-Cesium Godot example project scaffold:

- `extensions/cesium/examples/godot/CesiumVanillaExample/`
- [Example project README](./CesiumVanillaExample/README.md)

Target bar:

- clean project materialization
- 3D Tiles plugin installed on the pinned Godot lane
- pinned Godot lane currently means `4.7` on Windows-native proof
- Windows-native drift is tracked in `docs/CESIUM_GODOT_WINDOWS_4_7_BUILD_NOTES.md`
- Linux and macOS drift are tracked in `docs/CESIUM_GODOT_CROSS_PLATFORM_NOTES.md`
- one canonical geospatial scene
- one pure-Cesium scene proof with no FastDIS dependency
- one rerunnable demo/report lane
- one export/build lane for Windows and Linux that uses `export_presets.cfg`
