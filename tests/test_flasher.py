import hashlib
import threading

import pytest

from rpi_flasher import flasher
from rpi_flasher.flasher import (
    FlashCancelled,
    _ensure_cached_image,
    _url_filename,
    stream_to_raw_disk,
    verify_cached_file,
)


def test_url_filename_extracts_basename():
    assert (
        _url_filename("https://example.com/dir/image.img.xz") == "image.img.xz"
    )


def test_verify_cached_file_missing_returns_false(tmp_path):
    assert verify_cached_file(tmp_path / "missing.img", "abc") is False


def test_verify_cached_file_matches_hash(tmp_path):
    data = b"hello world"
    path = tmp_path / "cached.img"
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    assert verify_cached_file(path, digest) is True
    assert verify_cached_file(path, "wrong") is False


def test_verify_cached_file_reports_progress(tmp_path):
    data = b"x" * (flasher.CHUNK_SIZE + 10)
    path = tmp_path / "cached.img"
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    calls = []
    verify_cached_file(path, digest, progress_cb=calls.append)

    assert len(calls) == 2  # one full chunk, one partial chunk
    assert calls[-1].current == len(data)
    assert calls[-1].total == len(data)


def test_ensure_cached_image_skips_download_when_valid(tmp_path, monkeypatch):
    data = b"cached image bytes"
    cache_path = tmp_path / "img.img"
    cache_path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    def fail_download(*args, **kwargs):
        raise AssertionError("should not re-download a valid cache")

    monkeypatch.setattr(flasher, "download_and_cache", fail_download)

    _ensure_cached_image(
        "https://example.com/img.img.xz",
        digest,
        len(data),
        cache_path,
        progress_cb=lambda _: None,
    )


def test_ensure_cached_image_redownloads_when_corrupt(tmp_path, monkeypatch):
    cache_path = tmp_path / "img.img"
    cache_path.write_bytes(b"corrupt data of right size!!")

    called = {}

    def fake_download(
        url, extract_sha256, extract_size, dest, progress_cb, cancel_event=None
    ):
        called["invoked"] = True
        dest.write_bytes(b"corrupt data of right size!!")

    monkeypatch.setattr(flasher, "download_and_cache", fake_download)

    _ensure_cached_image(
        "https://example.com/img.img.xz",
        "does-not-match",
        len(b"corrupt data of right size!!"),
        cache_path,
        progress_cb=lambda _: None,
    )

    assert called.get("invoked") is True


def test_verify_cached_file_raises_when_cancelled(tmp_path):
    data = b"x" * (flasher.CHUNK_SIZE + 10)
    path = tmp_path / "cached.img"
    path.write_bytes(data)

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(FlashCancelled, match="safe to retry"):
        verify_cached_file(
            path, hashlib.sha256(data).hexdigest(), cancel_event=cancel_event
        )


def test_stream_to_raw_disk_raises_when_cancelled_before_start(tmp_path):
    src = tmp_path / "src.img"
    src.write_bytes(b"x" * 100)
    dst = tmp_path / "dst.img"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(FlashCancelled, match="inconsistent state"):
        stream_to_raw_disk(
            src, str(dst), 100, lambda _: None, cancel_event=cancel_event
        )


def test_stream_to_raw_disk_completes_when_not_cancelled(tmp_path):
    src = tmp_path / "src.img"
    data = b"x" * 100
    src.write_bytes(data)
    dst = tmp_path / "dst.img"

    stream_to_raw_disk(src, str(dst), len(data), lambda _: None)

    assert dst.read_bytes() == data


def test_ensure_cached_image_propagates_cancellation_from_verify(
    tmp_path, monkeypatch
):
    data = b"cached image bytes"
    cache_path = tmp_path / "img.img"
    cache_path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    cancel_event = threading.Event()
    cancel_event.set()

    def fail_download(*args, **kwargs):
        raise AssertionError("should not reach download when cancelled")

    monkeypatch.setattr(flasher, "download_and_cache", fail_download)

    with pytest.raises(FlashCancelled):
        _ensure_cached_image(
            "https://example.com/img.img.xz",
            digest,
            len(data),
            cache_path,
            progress_cb=lambda _: None,
            cancel_event=cancel_event,
        )
