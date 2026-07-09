# Cesium Extension

This subtree owns the repository's Cesium-specific compatibility work.

It exists to keep Cesium source-route prep, vendor compatibility work, and
pure-Cesium example-project planning separate from the rest of the repo.

For a fresh host, the quickest starting point is:

```bash
cesium-bootstrap
```

That prepares the local dev prefix, creates the short scratch roots, and runs
the Cesium smoke lanes before you move into source-route prep or example
workflow work.

Current ownership:

- `tools/`: Cesium-specific workflow wrappers and source-route prep
- `docs/`: Cesium-specific route, parity, and example standards
- `examples/`: repo-owned pure-Cesium example-project roots and placeholders

Key entry points:

- [Cesium source-route note](./docs/CESIUM_SOURCE_ROUTE.md)
- [Cesium fork ledger](../../docs/CESIUM_FORK_LEDGER.md)
- [Cesium example standard](./docs/CESIUM_EXAMPLE_STANDARD.md)
- [Cesium Unreal example root](./examples/unreal/README.md)
- [Cesium Unity example root](./examples/unity/README.md)
- [Cesium Godot example root](./examples/godot/README.md)

Boundary:

- `extensions/cesium` owns Cesium-specific workflow policy, docs, and example
  planning
- repo-root `tools/` may host thin command wrappers when the workflow needs a
  top-level entry point
