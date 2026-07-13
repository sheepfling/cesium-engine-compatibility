#!/usr/bin/env python3
"""Diagnose host, WSL, and Docker GPU/Vulkan readiness for Unreal Linux proof."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
from typing import Any

from tools import unreal_linux_gpu_probe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "reports" / "unreal_visual_proof" / "linux" / "gpu_doctor.json"


def _run(command: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        return {"returncode": result.returncode, "output": (result.stdout or "") + (result.stderr or "")}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "output": str(exc)}


def _has_render_gpu(output: str) -> bool:
    return any(
        device_type in output
        for device_type in (
            "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
            "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
        )
    )


def build_payload(distro: str, image: str, gpus: str) -> dict[str, Any]:
    host = _run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    wsl = _run(
        [
            "wsl.exe",
            "-d",
            distro,
            "--",
            "bash",
            "-lc",
            "vulkaninfo --summary 2>&1 || true",
        ]
    )
    docker = unreal_linux_gpu_probe.probe(image, gpus)
    wsl_render = _has_render_gpu(wsl["output"])
    docker_render = bool(docker.get("has_vulkan_device"))
    if wsl_render and docker_render:
        status = "pass"
        next_step = "Run Unreal Linux visual proof with the Docker-selected Vulkan device."
    elif wsl_render:
        status = "partial"
        next_step = (
            "Run Unreal directly inside the WSL distro with the WSL-selected Vulkan device. "
            "Docker render passthrough is not available on this host."
        )
    else:
        status = "fail"
        next_step = "Install or enable the WSL graphics/Vulkan bridge, then rerun this doctor before launching Unreal."

    return {
        "schema": "cesium.unreal_linux_gpu_doctor.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "selection_policy": "Use the host-provided GPU; no model or vendor is hardcoded.",
        "host_cuda": host,
        "wsl_vulkan": {**wsl, "has_render_gpu": wsl_render},
        "docker_gpu_probe": docker,
        "findings": [
            finding
            for finding, failed in (
                ("Host CUDA query failed.", host["returncode"] != 0),
                ("WSL Vulkan exposes no non-CPU device.", not wsl_render),
                ("Docker Vulkan exposes no non-CPU device.", not docker_render),
            )
            if failed
        ],
        "next_step": next_step,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distro", default="Ubuntu")
    parser.add_argument("--image", default=unreal_linux_gpu_probe.DEFAULT_IMAGE)
    parser.add_argument("--gpus", default="all")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    payload = build_payload(args.distro, args.image, args.gpus)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
