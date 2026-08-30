from rpi_flasher.boot_customize import (
    apply,
    write_cloudinit_custom_toml,
    write_userconf,
    write_wpa_supplicant,
)
from rpi_flasher.state import FlashOptions, ImageEntry, UserConfig, WlanConfig


def _image(init_format: str | None) -> ImageEntry:
    return ImageEntry(
        name="Test OS",
        description="",
        icon_url="",
        url="https://example.com/x.img.xz",
        extract_size=1,
        extract_sha256="abc",
        image_download_size=1,
        release_date="2026-01-01",
        init_format=init_format,
        devices=[],
        capabilities=[],
    )


def test_write_wpa_supplicant_contains_ssid_and_psk(tmp_path):
    wlan = WlanConfig(ssid="home", password="secret", country="DE")
    write_wpa_supplicant(tmp_path, wlan)
    content = (tmp_path / "wpa_supplicant.conf").read_text()
    assert 'ssid="home"' in content
    assert 'psk="secret"' in content
    assert "country=DE" in content


def test_write_cloudinit_custom_toml_includes_ssh_when_enabled(tmp_path):
    wlan = WlanConfig(ssid="home", password="secret", country="DE")
    write_cloudinit_custom_toml(tmp_path, wlan, enable_ssh=True)
    content = (tmp_path / "custom.toml").read_text()
    assert "[wlan]" in content
    assert 'ssid = "home"' in content
    assert "[ssh]" in content
    assert "enable = true" in content


def test_write_cloudinit_custom_toml_omits_ssh_when_disabled(tmp_path):
    wlan = WlanConfig(ssid="home", password="secret")
    write_cloudinit_custom_toml(tmp_path, wlan, enable_ssh=False)
    content = (tmp_path / "custom.toml").read_text()
    assert "[ssh]" not in content


def test_apply_touches_ssh_file_when_enabled(tmp_path):
    options = FlashOptions(enable_ssh=True, setup_wlan=False)
    apply(tmp_path, _image(None), options)
    assert (tmp_path / "ssh").exists()


def test_apply_picks_wpa_supplicant_for_legacy_images(tmp_path):
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    apply(tmp_path, _image(None), options)
    assert (tmp_path / "wpa_supplicant.conf").exists()
    assert not (tmp_path / "custom.toml").exists()


def test_apply_picks_custom_toml_for_cloudinit_images(tmp_path):
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    apply(tmp_path, _image("cloudinit-rpi"), options)
    assert (tmp_path / "custom.toml").exists()
    assert not (tmp_path / "wpa_supplicant.conf").exists()


def test_write_userconf_contains_hash_not_plaintext(tmp_path):
    user = UserConfig("pi-user", "$6$salt$hashed")
    write_userconf(tmp_path, user)

    assert (tmp_path / "userconf.txt").read_text() == (
        "pi-user:$6$salt$hashed\n"
    )


def test_apply_writes_userconf_for_raspberry_pi_os(tmp_path):
    image = _image(None)
    options = FlashOptions(
        configure_user=True,
        user=UserConfig("pi", "$6$salt$hashed"),
    )

    apply(tmp_path, image, options)

    assert (tmp_path / "userconf.txt").exists()


def test_apply_skips_userconf_for_incompatible_image(tmp_path):
    image = _image(None)
    image.category_path = ["Other general-purpose OS"]
    options = FlashOptions(
        configure_user=True,
        user=UserConfig("pi", "$6$salt$hashed"),
    )

    apply(tmp_path, image, options)

    assert not (tmp_path / "userconf.txt").exists()
