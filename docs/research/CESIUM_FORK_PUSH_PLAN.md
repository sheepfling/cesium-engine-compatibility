# Cesium Fork Push Plan

This note adapts the current Cesium verification work into a fork-friendly
push plan so we can keep proving things here, then move the smallest useful
changes into the sheepfling forks and eventually open PRs from those forks.

Fork remotes:

- [sheepfling/cesium-unreal](https://github.com/sheepfling/cesium-unreal)
- [sheepfling/cesium-unity](https://github.com/sheepfling/cesium-unity)
- [sheepfling/3D-Tiles-For-Godot](https://github.com/sheepfling/3D-Tiles-For-Godot)

## Working Rules

- keep verification evidence in this repo first
- keep code changes narrow enough to fit in a single fork PR
- do not mix Unreal, Unity, and Godot changes in the same branch
- if a change depends on `cesium-native`, land that dependency first, then bump
  the submodule or vendored pointer in the engine repo
- preserve exact engine version, host, command, and log tail in the handoff
  packet before pushing the branch

## Track 1: Unreal 5.7/5.8 Verification

Goal:

- verify the current Unreal 5.7 and 5.8 artifacts on Windows, macOS, and
  Linux without duplicating the existing support work

What this track is for:

- proving the current 5.7 and 5.8 CI intent still matches reality
- catching gaps in packaging, smoke tests, or toolchain logging
- separating “the lane works” from “the docs or logs need clarification”

What this track is not for:

- adding a brand-new 5.8 support feature
- bundling Linux toolchain cleanup into the verification result

Suggested verification order:

1. confirm the 5.7 and 5.8 CI blocks are present in the current workflow
2. verify Windows 5.7/5.8 build/package/test evidence
3. verify macOS 5.7/5.8 build/package/test evidence
4. verify Linux 5.7/5.8 build/package/test evidence
5. capture any host-specific blockers as evidence packets instead of patch
   packets

## Track 2: Linux Image And Toolchain Alignment

Goal:

- make the Linux image and compiler/toolchain alignment changes as a separate,
  small PR

Why this is separate:

- the verification work should not get mixed with image/toolchain edits
- the Linux host image/toolchain alignment is a distinct failure surface
- a small PR is easier to review, bisect, and port into the fork remote

Suggested contents:

- logging the active Unreal Linux toolchain inputs
- documenting the Linux image/toolchain assumptions directly where the build
  uses them
- adjusting only the Linux alignment code, not the rest of the 5.8 verification
  story

## Fork Push Sequence

1. finish the evidence packet for the relevant lane
2. branch the fork work from a clean upstream-sync point
3. keep the first fork branch tiny and focused
4. push that branch to the sheepfling fork remote
5. open the PR from the fork branch after the branch is stable
6. repeat with the next smallest change

Branch naming suggestion:

- `fork/unreal-57-58-verify`
- `fork/unreal-57-58-linux-align`
- `fork/unity-6000_5-verify`
- `fork/godot-4_7-verify`

## PR Ordering

Recommended order for fork pushes:

1. Unreal 5.7/5.8 verification/doc updates
2. Unreal Linux image/toolchain alignment
3. Unreal Windows/Linux code or packaging fixes that fall out of the evidence
4. Unity source-route or import/compile fixes
5. Godot source-route or build fixes

## Review Boundary

Keep these boundaries intact:

- this repo owns orchestration, evidence, and route discovery
- the fork repos own source fixes and platform-specific compatibility patches
- PRs should explain whether they are verification-only, toolchain-only, or a
  real source fix

