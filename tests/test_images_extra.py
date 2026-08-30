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


def test_image_codename_extracts_from_url():
    entry = _entry(
        url=(
            "https://downloads.raspberrypi.com/raspios_arm64/images/"
            "raspios_arm64-2026-06-19/2026-06-18-raspios-trixie-arm64.img.xz"
        )
    )
    assert images.image_codename(entry) == "trixie"


def test_image_codename_none_when_not_a_raspios_filename():
    entry = _entry(url="https://example.com/some-other-image.img.xz")
    assert images.image_codename(entry) is None


def test_uses_real_cloudinit_true_only_for_trixie():
    trixie = _entry(
        url="https://example.com/2026-06-18-raspios-trixie-arm64.img.xz"
    )
    bookworm = _entry(
        url="https://example.com/2025-01-01-raspios-bookworm-arm64.img.xz"
    )
    assert images.uses_real_cloudinit(trixie) is True
    assert images.uses_real_cloudinit(bookworm) is False


def test_uses_real_cloudinit_false_for_unrecognized_codename():
    # An unrecognized/future codename must NOT be assumed to be the
    # newer format -- that would silently write files nothing reads.
    future = _entry(
        url="https://example.com/2027-01-01-raspios-forky-arm64.img.xz"
    )
    assert images.uses_real_cloudinit(future) is False


def test_unrecognized_cloudinit_codename_flags_unknown_codename():
    future = _entry(
        init_format="cloudinit-rpi",
        url="https://example.com/2027-01-01-raspios-forky-arm64.img.xz",
    )
    assert images.unrecognized_cloudinit_codename(future) == "forky"


def test_unrecognized_cloudinit_codename_none_for_known_codenames():
    bookworm = _entry(
        init_format="cloudinit-rpi",
        url="https://example.com/2025-01-01-raspios-bookworm-arm64.img.xz",
    )
    trixie = _entry(
        init_format="cloudinit-rpi",
        url="https://example.com/2026-06-18-raspios-trixie-arm64.img.xz",
    )
    assert images.unrecognized_cloudinit_codename(bookworm) is None
    assert images.unrecognized_cloudinit_codename(trixie) is None


def test_unrecognized_cloudinit_codename_none_when_not_cloudinit_rpi():
    future = _entry(
        init_format="systemd",
        url="https://example.com/2027-01-01-raspios-forky-arm64.img.xz",
    )
    assert images.unrecognized_cloudinit_codename(future) is None


def test_display_label_is_name_first_with_cache_status():
    label = images.display_label(
        _entry(name="Raspberry Pi OS Lite"), cached=True
    )
    assert label.startswith("Raspberry Pi OS Lite")
    assert "Cached" in label


def test_display_label_shows_download_size_when_not_cached():
    label = images.display_label(
        _entry(image_download_size=500_000_000), cached=False
    )
    assert "Download" in label
    assert "MB" in label or "GB" in label


def test_display_label_omits_category_and_devices():
    # Both are already implied by the OS-select/device-select steps that
    # precede this list.
    label = images.display_label(
        _entry(category_path=["Media player OS"], devices=["pi5-64bit"]),
        cached=True,
    )
    assert "Media player OS" not in label
    assert "pi5-64bit" not in label


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


def test_unique_devices_dedupes_and_puts_newest_pi_first():
    entries = [
        _entry(devices=["pi5-64bit", "pi4-64bit"]),
        _entry(devices=["pi4-64bit"]),
        _entry(devices=[]),
    ]
    assert images.unique_devices(entries) == ["pi5-64bit", "pi4-64bit"]


def test_unique_devices_orders_by_version_then_bits_then_non_pi_last():
    entries = [
        _entry(
            devices=[
                "pi3-32bit",
                "pi5-32bit",
                "pi5-64bit",
                "pi4-64bit",
                "opi3-64bit",
            ]
        ),
    ]
    assert images.unique_devices(entries) == [
        "pi5-64bit",
        "pi5-32bit",
        "pi4-64bit",
        "pi3-32bit",
        "opi3-64bit",
    ]


def test_matches_device_matches_declared_device():
    entry = _entry(devices=["pi5-64bit"])
    assert images.matches_device(entry, "pi5-64bit") is True
    assert images.matches_device(entry, "pi4-64bit") is False


def test_matches_device_no_devices_matches_anything():
    entry = _entry(devices=[])
    assert images.matches_device(entry, "pi5-64bit") is True


def test_os_category_merges_top_level_and_other_raspberry_pi_os():
    # The flagship desktop build is a top-level entry (no category_path);
    # its Lite/Full variants are filed under "Raspberry Pi OS (other)".
    # Both must land in one family so choosing it offers the full lineup.
    desktop = _entry(category_path=[])
    lite = _entry(category_path=["Raspberry Pi OS (other)"])
    assert images.os_category(desktop) == "Raspberry Pi OS"
    assert images.os_category(lite) == "Raspberry Pi OS"
    assert images.unique_categories([desktop, lite]) == ["Raspberry Pi OS"]


def test_unique_categories_pins_raspberry_pi_os_first():
    entries = [
        _entry(category_path=["Media player OS"]),
        _entry(category_path=["Other general-purpose OS"]),
        _entry(category_path=[]),
    ]
    assert images.unique_categories(entries) == [
        "Raspberry Pi OS",
        "Media player OS",
        "Other general-purpose OS",
    ]


def test_os_category_keeps_unrelated_categories_distinct():
    entry = _entry(category_path=["Media player OS"])
    assert images.os_category(entry) == "Media player OS"


def test_cache_size_bytes_sums_img_files(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    assert images.cache_size_bytes() == 0

    (tmp_path / "a.img").write_bytes(b"x" * 10)
    (tmp_path / "b.img").write_bytes(b"y" * 20)
    (tmp_path / "ignored.txt").write_bytes(b"z" * 100)

    assert images.cache_size_bytes() == 30
