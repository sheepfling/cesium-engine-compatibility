# Unreal Version Matrix

This note keeps the repo-owned Unreal lanes explicit, especially for Linux.

The important split is not just Windows versus Linux. It is also the version
boundary between the current baseline lane and the forward-verification lane.

The current matrix we can defend from the repo evidence is:

## Windows Proof Lane

| Engine Version | Lane Role | What We Care About |
| -------------- | --------- | ------------------ |
| 5.7 | current baseline | Confirm the main Unreal Windows proof lane and keep the sample/plugin packaging path honest. |
| 5.8 | forward verification | Confirm the next Unreal 5.x release still fits the same repo-owned sample and source-route expectations. |

## Current Linux Matrix

| Engine Version | Lane Role | What We Care About |
| -------------- | --------- | ------------------ |
| 5.7 | current baseline | Confirm source checkout, plugin packaging, and editor-open behavior against the pinned 5.7-era lane. |
| 5.8 | forward verification | Confirm that Linux host/toolchain alignment still works on the newer 5.8 lane without mixing in Windows-only assumptions. |

## What The Combined Packet Should Say

- Windows and Linux both have explicit Unreal version coverage for 5.7 and 5.8
- Linux remains a separate Docker-backed proof path, not a Windows surrogate
- the version matrix is the place to record the first failing release if a newer
  or older Unreal 5.x host shifts behavior

## How To Use This Matrix

- keep 5.7 as the baseline Linux proof lane until we have a better reason to
  move the pin
- use 5.8 as the first forward-compatibility check
- record the first failing release, the host image, and the toolchain in
  `docs/CESIUM_UNREAL_LINUX_NOTES.md`
- keep the Windows 5.7/5.8 lane notes in sync with the same compatibility
  packet so the PR tells one coherent story

## Related Entrypoints

- `cesium-unreal-linux report`
- `cesium-unreal-linux report`

## Rule Of Thumb

If the failure is caused by editor/package/API drift, treat it as version
compatibility work.
If the failure is caused by host image or compiler drift, treat it as Linux
toolchain work.
