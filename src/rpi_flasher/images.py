"""Fetching, flattening, and caching the Raspberry Pi Imager OS list feed."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from rpi_flasher.privilege import (
    ensure_user_owned_dir,
    invoking_user_home,
    write_user_owned_file,
)
from rpi_flasher.state import ImageEntry
from rpi_flasher.utils import human_bytes

OS_LIST_URL = (
    "https://downloads.raspberrypi.org/os_list_imagingutility_v4.json"
)
# A default httpx/curl User-Agent gets a 403 from this endpoint.
USER_AGENT = "Mozilla/5.0 (rpi-flasher)"


class ImageListError(RuntimeError):
    pass


def cache_root() -> Path:
    return Path(invoking_user_home()) / ".cache" / "rpi-flasher"


def images_dir() -> Path:
    return cache_root() / "images"


def os_list_snapshot_path() -> Path:
    return cache_root() / "os_list.json"


async def fetch_os_list() -> dict:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=20.0
    ) as client:
        response = await client.get(OS_LIST_URL)
        response.raise_for_status()
        data = response.json()

    _save_snapshot(data)
    return data


def _save_snapshot(data: dict) -> None:
    ensure_user_owned_dir(cache_root())
    write_user_owned_file(os_list_snapshot_path(), json.dumps(data))


def load_snapshot() -> dict | None:
    path = os_list_snapshot_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def flatten_os_list(
    raw_os_list: list[dict], path: list[str] | None = None
) -> list[ImageEntry]:
    """Recursively expand `subitems` categories into leaf ImageEntry objects.
    Categories themselves (entries with `subitems` instead of `url`) are
    never emitted as selectable leaves."""
    path = path or []
    entries: list[ImageEntry] = []
    for item in raw_os_list:
        subitems = item.get("subitems")
        if subitems:
            entries.extend(
                flatten_os_list(subitems, path + [item.get("name", "")])
            )
            continue
        if "url" not in item:
            continue
        entries.append(
            ImageEntry(
                name=item.get("name", "Unknown"),
                description=item.get("description", ""),
                icon_url=item.get("icon", ""),
                url=item["url"],
                extract_size=int(item.get("extract_size", 0)),
                extract_sha256=item.get("extract_sha256", ""),
                image_download_size=int(item.get("image_download_size", 0)),
                release_date=item.get("release_date", ""),
                init_format=item.get("init_format"),
                devices=item.get("devices", []),
                capabilities=item.get("capabilities", []),
                category_path=path,
            )
        )
    return entries


def cache_path_for(entry: ImageEntry) -> Path:
    return images_dir() / f"{entry.extract_sha256}.img"


def is_cached_at(path: Path, expected_size: int) -> bool:
    return path.exists() and path.stat().st_size == expected_size


def is_cached(entry: ImageEntry) -> bool:
    return is_cached_at(cache_path_for(entry), entry.extract_size)


def delete_cached(entry: ImageEntry) -> None:
    cache_path_for(entry).unlink(missing_ok=True)


def cache_size_bytes() -> int:
    """Total size of all cached (downloaded+decompressed) images."""
    directory = images_dir()
    if not directory.exists():
        return 0
    return sum(
        p.stat().st_size for p in directory.glob("*.img") if p.is_file()
    )


def display_label(entry: ImageEntry, *, cached: bool) -> str:
    """Format a selectable row label, name-first so the list reads like a
    menu rather than a stack of status tags. `cached` is passed in rather
    than recomputed here, since callers (e.g. a filterable list re-rendered
    on every keystroke) should stat each cache file once, not per render.
    Neither the target devices nor the OS category are repeated here since
    the image list is already narrowed to the chosen Pi model and OS
    family before this label is shown."""
    status = (
        "✓ Cached"
        if cached
        else f"⬇ Download {human_bytes(entry.image_download_size)}"
    )
    return f"{entry.name} -- {status}"


async def fetch_entries() -> tuple[list[ImageEntry], str]:
    """Fetch and flatten the OS list, falling back to the last cached
    snapshot on network failure. Returns (entries, status) where status is
    empty after a clean live fetch, or an explanatory message if the
    fallback snapshot was used instead. Raises ImageListError if the fetch
    fails and there's no usable snapshot to fall back to."""
    try:
        data = await fetch_os_list()
        return flatten_os_list(data.get("os_list", [])), ""
    except httpx.HTTPError as exc:
        snapshot = await asyncio.to_thread(load_snapshot)
        if snapshot is None:
            raise ImageListError(str(exc)) from exc
        return (
            flatten_os_list(snapshot.get("os_list", [])),
            f"Live fetch failed ({exc}); showing last cached list.",
        )


# Matches the feed's Raspberry Pi device ids (e.g. "pi5-64bit",
# "pi4-32bit") but not other boards' ids that happen to contain "pi" as a
# substring (e.g. "opi3-64bit" for Orange Pi 3).
_PI_DEVICE_RE = re.compile(r"^pi(\d+)-(\d+)bit$")


def _device_sort_key(device: str) -> tuple[int, int, int, str]:
    match = _PI_DEVICE_RE.match(device)
    if match is None:
        # Non-Pi boards sort after all Raspberry Pi models, alphabetically.
        return (1, 0, 0, device)
    version, bits = int(match.group(1)), int(match.group(2))
    return (0, -version, -bits, device)


def unique_devices(entries: list[ImageEntry]) -> list[str]:
    """All distinct Pi models referenced across the entries' `devices`
    lists, for the device-select step -- newest Raspberry Pi model first."""
    devices = {device for entry in entries for device in entry.devices}
    return sorted(devices, key=_device_sort_key)


def matches_device(entry: ImageEntry, device: str) -> bool:
    """An entry with no declared devices is treated as device-agnostic
    (e.g. general-purpose tools), so it matches any model."""
    return not entry.devices or device in entry.devices


def os_category(entry: ImageEntry) -> str:
    """Top-level OS family for the OS-select step. Top-level feed entries
    (the main Raspberry Pi OS desktop builds) have no category_path at
    all, while their Lite/Full variants are filed a level down under a
    separate "Raspberry Pi OS (other)" category -- both are grouped under
    one "Raspberry Pi OS" family here so choosing it offers the full
    Full/Lite/Legacy lineup instead of just the single top-level desktop
    build. Everything else keeps its own top-level category (e.g. "Media
    player OS")."""
    top = entry.category_path[0] if entry.category_path else "Raspberry Pi OS"
    return "Raspberry Pi OS" if top.startswith("Raspberry Pi OS") else top


def unique_categories(entries: list[ImageEntry]) -> list[str]:
    """Distinct OS families, with "Raspberry Pi OS" pinned first since
    it's the overwhelmingly common choice; everything else alphabetical."""
    categories = {os_category(e) for e in entries}
    rest = sorted(categories - {"Raspberry Pi OS"})
    return (
        ["Raspberry Pi OS"] if "Raspberry Pi OS" in categories else []
    ) + rest
