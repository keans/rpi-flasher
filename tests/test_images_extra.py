from rpi_flasher import images
from rpi_flasher.state import ImageEntry


def _entry(**overrides) -> ImageEntry:
    defaults = {
        "name": "Raspberry Pi OS Lite",
        "description": "",
        "icon_url": "",
        "url": "https://example.com/x.img.xz",
        "extract_size": 5,
        "extract_sha256": "abc",
        "image_download_size": 5,
        "release_date": "2026-01-01",
        "init_format": None,
        "devices": ["pi5-64bit", "pi4-64bit"],
        "capabilities": [],
        "category_path": [],
    }
    defaults.update(overrides)
    return ImageEntry(**defaults)


def test_matches_query_empty_matches_everything():
    assert images.matches_query(_entry(), "") is True


def test_matches_query_matches_name():
    assert images.matches_query(_entry(name="Ubuntu Server"), "ubuntu") is True


def test_matches_query_matches_device():
    assert images.matches_query(_entry(devices=["pi5-64bit"]), "pi5") is True
    assert images.matches_query(_entry(devices=["pi5-64bit"]), "pi3") is False


def test_matches_query_matches_category():
    entry = _entry(category_path=["Media player OS"])
    assert images.matches_query(entry, "media") is True


def test_display_label_includes_devices():
    label = images.display_label(_entry(), cached=True)
    assert "pi5-64bit" in label
    assert "pi4-64bit" in label


def test_delete_cached_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entry = _entry(extract_sha256="deadbeef")
    cache_path = images.cache_path_for(entry)
    cache_path.write_bytes(b"x" * 5)
    assert images.is_cached(entry) is True

    images.delete_cached(entry)
    assert not cache_path.exists()


def test_delete_cached_missing_file_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    images.delete_cached(_entry())  # should not raise


def test_cache_size_bytes_sums_img_files(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    assert images.cache_size_bytes() == 0

    (tmp_path / "a.img").write_bytes(b"x" * 10)
    (tmp_path / "b.img").write_bytes(b"y" * 20)
    (tmp_path / "ignored.txt").write_bytes(b"z" * 100)

    assert images.cache_size_bytes() == 30
