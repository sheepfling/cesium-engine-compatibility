#!/usr/bin/env python3
"""Probe host GPU and Vulkan visibility from the Unreal Linux Docker lane."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = "cesium-linux-proof:ubuntu24.04"
DEFAULT_OUT = ROOT / "artifacts" / "reports" / "unreal_visual_proof" / "linux" / "gpu_probe.json"


def probe(image: str, gpus: str) -> dict[str, Any]:
    command = [
        "docker",
        "run",
        "--rm",
        "--gpus",
        gpus,
        "-e",
        "NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display",
        image,
        "bash",
        "-lc",
        "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq vulkan-tools mesa-vulkan-drivers >/dev/null; "
        "echo __NVIDIA_SMI__; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1 || true; "
        "echo __VULKANINFO__; vulkaninfo --summary 2>&1 || true",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=180)
        output = (result.stdout or "") + (result.stderr or "")
        returncode: int | None = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        output += (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        returncode = None

    vulkan_section = output.split("__VULKANINFO__", 1)[-1]
    has_vulkan_device = any(
        device_type in vulkan_section
        for device_type in (
            "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
            "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
        )
    )
    cpu_only = "PHYSICAL_DEVICE_TYPE_CPU" in vulkan_section and not has_vulkan_device
    return {
        "schema": "cesium.unreal_linux_gpu_probe.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if returncode == 0 and has_vulkan_device else "fail",
        "image": image,
        "gpus_request": gpus,
        "host_gpu_selection": "Docker-selected host GPU(s); no model is hardcoded",
        "returncode": returncode,
        "has_vulkan_device": has_vulkan_device,
        "cpu_only_vulkan": cpu_only,
        "output": output,
        "next_step": (
            "Run the Unreal Linux visual proof lane with the Docker-selected Vulkan device."
            if has_vulkan_device
            else "Enable host GPU/Vulkan passthrough; Docker currently exposes no suitable non-CPU Vulkan device."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--gpus", default="all", help="Docker GPU request; defaults to all host GPUs")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    payload = probe(args.image, args.gpus)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "output"}, indent=2))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
