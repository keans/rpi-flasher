"""Download + decompress + verify + write pipeline, and the flash orchestrator."""

from __future__ import annotations

import hashlib
import lzma
import os
import tempfile
import threading
import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from rpi_flasher import boot_customize, disks, images
from rpi_flasher.privilege import chown_to_invoking_user, ensure_user_owned_dir
from rpi_flasher.state import WizardState

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB
HTTP_TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=30.0, pool=15.0)


class FlashError(RuntimeError):
    pass


class DownloadError(FlashError):
    pass


class ChecksumMismatchError(FlashError):
    pass


class UnsupportedFormatError(FlashError):
    pass


class FlashCancelled(FlashError):
    pass


def _check_cancelled(
    cancel_event: threading.Event | None, message: str
) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise FlashCancelled(message)


@dataclass
class FlashProgress:
    phase: str
    current: int
    total: int
    # True while the phase observes the cancellation event. Cancelling a raw
    # write is supported, but leaves the card incomplete and needing reflash.
    cancellable: bool = False
    # Non-fatal problems that must remain visible on the final success screen.
    warning: bool = False


ProgressCallback = Callable[[FlashProgress], None]


def _url_filename(url: str) -> str:
    return Path(urlparse(url).path).name


def _decompress_xz_stream(chunks: Iterator[bytes]) -> Iterator[bytes]:
    decompressor = lzma.LZMADecompressor()
    for chunk in chunks:
        out = decompressor.decompress(chunk)
        if out:
            yield out


def _decompress_zip_file(path: Path) -> Iterator[bytes]:
    with zipfile.ZipFile(path) as zf:
        members = [i for i in zf.infolist() if not i.is_dir()]
        if not members:
            raise UnsupportedFormatError(
                f"Zip archive {path} contains no files"
            )
        # Pi OS zip downloads contain exactly one .img member.
        member = max(members, key=lambda i: i.file_size)
        with zf.open(member) as fh:
            while True:
                data = fh.read(CHUNK_SIZE)
                if not data:
                    break
                yield data


def _stream_url(url: str) -> Iterator[bytes]:
    with httpx.stream(
        "GET",
        url,
        headers={"User-Agent": images.USER_AGENT},
        timeout=HTTP_TIMEOUT,
    ) as r:
        r.raise_for_status()
        yield from r.iter_bytes(CHUNK_SIZE)


def _download_zip_to_temp(
    url: str,
    dest_dir: Path,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Zip needs random access to extract, so buffer the raw download to a
    temp file first; the caller is responsible for deleting it."""
    fd, tmp_path_str = tempfile.mkstemp(dir=dest_dir, prefix=".compressed-")
    tmp_path = Path(tmp_path_str)
    try:
        with (
            os.fdopen(fd, "wb") as cf,
            httpx.stream(
                "GET",
                url,
                headers={"User-Agent": images.USER_AGENT},
                timeout=HTTP_TIMEOUT,
            ) as r,
        ):
            r.raise_for_status()
            for chunk in r.iter_bytes(CHUNK_SIZE):
                _check_cancelled(
                    cancel_event,
                    "Download cancelled -- no data was written to the "
                    "SD card, it's safe to retry.",
                )
                cf.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def _decompressed_chunks(
    url: str,
    filename: str,
    dest_dir: Path,
    cancel_event: threading.Event | None = None,
) -> Iterable[bytes]:
    """Dispatch on archive format and return an iterator of decompressed
    bytes -- the one thing that differs between .zip/.xz/.img downloads.
    Everything else (hashing, writing, progress) is handled uniformly by
    the caller."""
    if filename.endswith(".zip"):
        compressed_path = _download_zip_to_temp(url, dest_dir, cancel_event)
        try:
            yield from _decompress_zip_file(compressed_path)
        finally:
            compressed_path.unlink(missing_ok=True)
    elif filename.endswith(".xz"):
        yield from _decompress_xz_stream(_stream_url(url))
    elif filename.endswith(".img"):
        yield from _stream_url(url)
    else:
        raise UnsupportedFormatError(
            f"Unsupported image archive format: {filename}"
        )


def _hash_stream(
    chunks: Iterable[bytes],
    total: int,
    phase: str,
    cancel_message: str,
    progress_cb: ProgressCallback | None,
    cancel_event: threading.Event | None,
    on_chunk: Callable[[bytes], None] | None = None,
) -> str:
    """Hash a chunk stream, reporting progress and checking for
    cancellation between chunks; `on_chunk` is called with each chunk for
    callers that also need to write it out (download does, verify doesn't)."""
    sha256 = hashlib.sha256()
    processed = 0
    for chunk in chunks:
        _check_cancelled(cancel_event, cancel_message)
        sha256.update(chunk)
        if on_chunk is not None:
            on_chunk(chunk)
        processed += len(chunk)
        if progress_cb is not None:
            progress_cb(
                FlashProgress(phase, processed, total, cancellable=True)
            )
    return sha256.hexdigest()


def _read_in_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk


def download_and_cache(
    url: str,
    extract_sha256: str,
    extract_size: int,
    dest: Path,
    progress_cb: ProgressCallback,
    cancel_event: threading.Event | None = None,
) -> None:
    """Stream-download `url`, decompress on the fly, verify against
    `extract_sha256`, and atomically place the result at `dest`."""
    filename = _url_filename(url)
    ensure_user_owned_dir(dest.parent)

    fd, tmp_path_str = tempfile.mkstemp(dir=dest.parent, prefix=".download-")
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "wb") as tmp_file:
            progress_cb(
                FlashProgress("Downloading", 0, extract_size, cancellable=True)
            )
            digest = _hash_stream(
                _decompressed_chunks(url, filename, dest.parent, cancel_event),
                extract_size,
                "Downloading",
                "Download cancelled -- no data was written to the "
                "SD card, it's safe to retry.",
                progress_cb,
                cancel_event,
                on_chunk=tmp_file.write,
            )

        if extract_sha256 and digest != extract_sha256:
            raise ChecksumMismatchError(
                f"Checksum mismatch for {filename}: "
                f"expected {extract_sha256}, got {digest}"
            )

        os.replace(tmp_path, dest)
        chown_to_invoking_user(str(dest))
    except httpx.HTTPError as exc:
        raise DownloadError(f"Download failed: {exc}") from exc
    except (zipfile.BadZipFile, lzma.LZMAError, EOFError) as exc:
        raise DownloadError(
            f"Downloaded image archive is corrupt: {exc}"
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def verify_cached_file(
    path: Path,
    extract_sha256: str,
    progress_cb: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> bool:
    if not path.exists():
        return False
    total = path.stat().st_size
    digest = _hash_stream(
        _read_in_chunks(path),
        total,
        "Verifying cached image",
        "Verification cancelled -- no data was written to the "
        "SD card, it's safe to retry.",
        progress_cb,
        cancel_event,
    )
    return digest == extract_sha256


def _ensure_cached_image(
    url: str,
    extract_sha256: str,
    extract_size: int,
    cache_path: Path,
    progress_cb: ProgressCallback,
    cancel_event: threading.Event | None = None,
) -> None:
    """Make sure a verified copy of the image exists at `cache_path`,
    downloading (or re-downloading, if the existing cache is corrupt) as
    needed."""
    if images.is_cached_at(cache_path, extract_size):
        if verify_cached_file(
            cache_path, extract_sha256, progress_cb, cancel_event
        ):
            return
        cache_path.unlink(missing_ok=True)

    download_and_cache(
        url,
        extract_sha256,
        extract_size,
        cache_path,
        progress_cb,
        cancel_event,
    )


def stream_to_raw_disk(
    cache_path: Path,
    raw_device_node: str,
    total_size: int,
    progress_cb: ProgressCallback,
    cancel_event: threading.Event | None = None,
) -> None:
    written = 0
    progress_cb(FlashProgress("Writing", 0, total_size, cancellable=True))
    with (
        cache_path.open("rb") as src,
        open(raw_device_node, "wb", buffering=0) as dst,
    ):
        while True:
            # Once bytes have hit the raw device, the card is no longer
            # a valid image until the write finishes -- cancelling here
            # must say so plainly rather than pretending it's a clean
            # abort like the download/verify phases are.
            _check_cancelled(
                cancel_event,
                "Flash cancelled while writing to the SD card -- it is "
                "now in an inconsistent state and must be reflashed "
                "before use.",
            )
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
            progress_cb(
                FlashProgress("Writing", written, total_size, cancellable=True)
            )
        dst.flush()
        os.fsync(dst.fileno())


def flash(
    state: WizardState,
    progress_cb: ProgressCallback,
    cancel_event: threading.Event | None = None,
) -> None:
    """Orchestrates the full flash pipeline.

    Any disk-related failure (card removed mid-flash, I/O error while
    writing, etc.) or unexpected OSError is normalized into a FlashError
    so the UI only ever has to handle one exception type. `cancel_event`,
    if given, is polled between chunks so the UI can offer a Cancel
    button; FlashCancelled (a FlashError) is raised with a message that
    says whether it's safe to just retry or whether the card write was
    left in an inconsistent state.
    """
    try:
        _flash_inner(state, progress_cb, cancel_event)
    except (disks.DiskError, OSError) as exc:
        raise FlashError(str(exc)) from exc


def _flash_inner(
    state: WizardState,
    progress_cb: ProgressCallback,
    cancel_event: threading.Event | None,
) -> None:
    assert state.disk is not None
    assert state.image is not None
    disk = state.disk
    image = state.image
    options = state.options

    progress_cb(FlashProgress("Unmounting", 0, 1))
    disks.unmount_disk(disk.device_node)

    cache_path = images.cache_path_for(image)
    _ensure_cached_image(
        image.url,
        image.extract_sha256,
        image.extract_size,
        cache_path,
        progress_cb,
        cancel_event,
    )

    stream_to_raw_disk(
        cache_path,
        disk.raw_device_node,
        image.extract_size,
        progress_cb,
        cancel_event,
    )

    progress_cb(FlashProgress("Remounting", 0, 1))
    disks.mount_disk(disk.device_node)

    if options.enable_ssh or options.setup_wlan:
        progress_cb(FlashProgress("Customizing boot partition", 0, 1))
        # The image itself is already flashed correctly at this point;
        # a customization failure (card removed, boot partition slow to
        # remount) is reported but shouldn't fail the whole flash.
        skip_reason = disks.best_effort(
            lambda: boot_customize.apply(
                disks.find_boot_partition_mountpoint(disk.device_node),
                image,
                options,
            )
        )
        if skip_reason:
            progress_cb(
                FlashProgress(
                    f"Boot partition customization skipped: {skip_reason}",
                    0,
                    1,
                    warning=True,
                )
            )

    if options.delete_image_after_flash:
        progress_cb(FlashProgress("Deleting cached image", 0, 1))
        cache_path.unlink(missing_ok=True)

    progress_cb(FlashProgress("Ejecting", 0, 1))
    # Write already succeeded; a failed eject (e.g. card pulled by the
    # user right at the end) shouldn't be reported as failure.
    eject_error = disks.best_effort(lambda: disks.eject_disk(disk.device_node))
    if eject_error:
        progress_cb(
            FlashProgress(
                f"Could not eject the card: {eject_error}",
                0,
                1,
                warning=True,
            )
        )

    progress_cb(FlashProgress("Done", 1, 1))
