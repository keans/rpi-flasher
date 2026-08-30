"""Fetching, flattening, and caching the Raspberry Pi Imager OS list feed."""

from __future__ import annotations

import json
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
    """Format a selectable row label. `cached` is passed in rather than
    recomputed here, since callers (e.g. a filterable list re-rendered on
    every keystroke) should stat each cache file once, not per render."""
    prefix = (
        f"[{' / '.join(entry.category_path)}] " if entry.category_path else ""
    )
    if cached:
        status = "[Cached]"
    else:
        status = f"[Download {human_bytes(entry.image_download_size)}]"
    devices = f" ({', '.join(entry.devices)})" if entry.devices else ""
    return f"{status} {prefix}{entry.name}{devices}"


def matches_query(entry: ImageEntry, query: str) -> bool:
    """Substring match used by the image list's filter box, covering name,
    category, and target device (e.g. typing "pi5" narrows to images that
    declare compatibility with a Pi 5)."""
    query = query.lower().strip()
    if not query:
        return True
    haystacks = [
        entry.name.lower(),
        " ".join(entry.category_path).lower(),
        " ".join(entry.devices).lower(),
    ]
    return any(query in h for h in haystacks)
