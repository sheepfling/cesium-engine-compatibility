#!/usr/bin/env python3
"""Shared Docker runner helpers for Cesium Linux proof lanes."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


def sanitize_label(value: str) -> str:
    return value.replace(" ", "_").replace("/", "__")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"invalid env line in {path}: {raw_line}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def resolved_container_name(prefix: str, *, identifier: str | None = None, explicit: str | None = None, pid: int | None = None) -> str:
    if explicit:
        return explicit
    suffix = sanitize_label(identifier or "unknown")
    return f"{prefix}-{suffix}-{pid or os.getpid()}"


def docker_log_path(base_dir: Path, *, command_name: str, identifier: str | None = None) -> Path:
    return base_dir / f"{command_name}_{sanitize_label(identifier or 'unknown')}.log"


def cleanup_container(container_name: str) -> None:
    try:
        subprocess.run(["docker", "rm", "-f", container_name], text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass


def tail_lines(text: str, lines: int) -> list[str]:
    rows = [row for row in text.splitlines() if row.strip()]
    return rows[-max(1, lines):]


def preserve_artifact(path: Path, *, preserve_root: Path, preserve_label: str, prefix: str) -> Path | None:
    if not path.is_file():
        return None
    snapshot_dir = preserve_root / preserve_label
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    preserved = snapshot_dir / f"{prefix}_{path.name}"
    shutil.copy2(path, preserved)
    return preserved


def run_command_with_logging(
    command: list[str],
    *,
    log_out: Path,
    log_mode: str,
    timeout_seconds: int,
    log_tail_lines: int,
    container_name: str,
) -> tuple[int | None, list[str], list[str], str]:
    log_out.parent.mkdir(parents=True, exist_ok=True)
    if log_mode == "capture":
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            log_out.write_text(stdout + stderr, encoding="utf-8")
            cleanup_container(container_name)
            raise
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        log_out.write_text(stdout + stderr, encoding="utf-8")
        return result.returncode, tail_lines(stdout, log_tail_lines), tail_lines(stderr, log_tail_lines), stdout + "\n" + stderr

    tail: deque[str] = deque(maxlen=max(1, log_tail_lines))
    line_queue: queue.Queue[str | None] = queue.Queue()
    with log_out.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None

        def enqueue_output() -> None:
            try:
                for output_line in process.stdout:
                    line_queue.put(output_line)
            finally:
                line_queue.put(None)

        reader = threading.Thread(target=enqueue_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + max(1, timeout_seconds)
        reader_done = False
        while True:
            if time.monotonic() > deadline:
                process.kill()
                cleanup_container(container_name)
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            try:
                line = line_queue.get(timeout=1)
            except queue.Empty:
                if reader_done and process.poll() is not None:
                    break
                continue
            if line is None:
                reader_done = True
                if process.poll() is not None:
                    break
                continue
            log_file.write(line)
            log_file.flush()
            stripped = line.rstrip()
            if stripped:
                tail.append(stripped)
            print(line, end="", flush=True)
        return process.wait(timeout=5), list(tail), [], ""
