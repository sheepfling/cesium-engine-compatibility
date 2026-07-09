from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from typing import Iterable


_VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?(?:-(?P<label>[A-Za-z]+)(?P<num>\d+)?)?$"
)
_ARCHIVE_TAG_PATTERN = re.compile(r"/download/archive/([^/]+)/")
_CHANNEL_RANK = {
    "stable": 4,
    "rc": 3,
    "beta": 2,
    "dev": 1,
    "alpha": 0,
}


@dataclass(frozen=True)
class GodotVersion:
    tag: str
    major: int
    minor: int
    patch: int
    label: str
    label_rank: int
    label_number: int

    @property
    def sort_key(self) -> tuple[int, int, int, int, int]:
        return (self.major, self.minor, self.patch, self.label_rank, self.label_number)


def parse_version(tag: str) -> GodotVersion | None:
    match = _VERSION_PATTERN.match(tag.strip())
    if not match:
        return None
    label = (match.group("label") or "stable").lower()
    number = int(match.group("num") or 0)
    return GodotVersion(
        tag=tag,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch") or 0),
        label=label,
        label_rank=_CHANNEL_RANK.get(label, -1),
        label_number=number,
    )


def _parse_selector(selector: str | None) -> list[str]:
    if not selector:
        return []
    return [part.strip() for part in selector.split(",") if part.strip()]


def _matches_range(candidate: GodotVersion, start: GodotVersion, end: GodotVersion) -> bool:
    return start.sort_key <= candidate.sort_key <= end.sort_key


def version_matches_selector(tag: str, selector: str | None) -> bool:
    version = parse_version(tag)
    if version is None:
        return False
    tokens = _parse_selector(selector)
    if not tokens:
        return True
    for token in tokens:
        if ".." in token:
            left, right = [part.strip() for part in token.split("..", 1)]
            start = parse_version(left)
            end = parse_version(right)
            if start is None or end is None:
                continue
            if _matches_range(version, start, end):
                return True
            continue
        if token == tag:
            return True
    return False


def select_versions(tags: Iterable[str], selector: str | None = None, *, limit: int | None = None) -> list[str]:
    parsed = [parse_version(tag) for tag in tags]
    candidates = [item for item in parsed if item is not None and version_matches_selector(item.tag, selector)]
    candidates.sort(key=lambda item: item.sort_key, reverse=True)
    selected: list[str] = []
    for item in candidates:
        if item.tag not in selected:
            selected.append(item.tag)
    if limit is not None:
        selected = selected[: max(0, limit)]
    return selected


def parse_archive_index(html: str) -> list[str]:
    tags: list[str] = []
    for match in _ARCHIVE_TAG_PATTERN.finditer(html):
        tag = match.group(1).strip("/")
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def fetch_archive_tags(archive_index_url: str = "https://godotengine.org/download/archive/") -> list[str]:
    with urllib.request.urlopen(archive_index_url) as response:  # nosec: B310
        html = response.read().decode("utf-8", errors="replace")
    return parse_archive_index(html)
