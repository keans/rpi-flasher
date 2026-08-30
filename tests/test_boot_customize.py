from rpi_flasher.boot_customize import (
    apply,
    write_cloudinit_custom_toml,
    write_cloudinit_network_config,
    write_userconf,
    write_wpa_supplicant,
)
from rpi_flasher.state import FlashOptions, ImageEntry, UserConfig, WlanConfig


def _image(
    init_format: str | None,
    url: str = "https://example.com/x.img.xz",
) -> ImageEntry:
    return ImageEntry(
        name="Test OS",
        description="",
        icon_url="",
        url=url,
        extract_size=1,
        extract_sha256="abc",
        image_download_size=1,
        release_date="2026-01-01",
        init_format=init_format,
        devices=[],
        capabilities=[],
    )


BOOKWORM_URL = (
    "https://downloads.raspberrypi.com/raspios_arm64/images/"
    "raspios_arm64-2025-01-01/2025-01-01-raspios-bookworm-arm64.img.xz"
)
TRIXIE_URL = (
    "https://downloads.raspberrypi.com/raspios_arm64/images/"
    "raspios_arm64-2026-06-19/2026-06-18-raspios-trixie-arm64.img.xz"
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
    assert "password_encrypted = false" in content
    assert "[ssh]" in content
    assert "enabled = true" in content


def test_write_cloudinit_custom_toml_omits_ssh_when_disabled(tmp_path):
    wlan = WlanConfig(ssid="home", password="secret")
    write_cloudinit_custom_toml(tmp_path, wlan, enable_ssh=False)
    content = (tmp_path / "custom.toml").read_text()
    assert "[ssh]" not in content


def test_write_cloudinit_custom_toml_marks_wlan_password_plaintext(tmp_path):
    # init_config's [wlan] parsing defaults password_encrypted to True,
    # so a plaintext password without this explicit override is treated
    # as an already-hashed value and Wi-Fi never actually connects.
    wlan = WlanConfig(ssid="home", password="secret")
    write_cloudinit_custom_toml(tmp_path, wlan, enable_ssh=False)
    content = (tmp_path / "custom.toml").read_text()
    assert "password_encrypted = false" in content


def test_write_cloudinit_network_config_contains_ssid_password_country(
    tmp_path,
):
    wlan = WlanConfig(ssid="home", password="secret", country="DE")
    write_cloudinit_network_config(tmp_path, wlan)
    content = (tmp_path / "network-config").read_text()
    assert "wifis:" in content
    assert '"home":' in content
    assert 'password: "secret"' in content
    assert "regulatory-domain: DE" in content


def test_write_cloudinit_network_config_escapes_special_characters(
    tmp_path,
):
    wlan = WlanConfig(ssid='my "network"', password="a\\b", country="US")
    write_cloudinit_network_config(tmp_path, wlan)
    content = (tmp_path / "network-config").read_text()
    # json.dumps-style escaping should round-trip through a YAML parser
    # without needing one available in this test environment: just check
    # the raw escape sequences are present, not raw unescaped quotes.
    assert '\\"network\\"' in content
    assert "a\\\\b" in content


def test_apply_picks_network_config_for_trixie_images(tmp_path):
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    apply(tmp_path, _image("cloudinit-rpi", url=TRIXIE_URL), options)
    assert (tmp_path / "network-config").exists()
    assert not (tmp_path / "custom.toml").exists()


def test_apply_picks_custom_toml_for_bookworm_images(tmp_path):
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    apply(tmp_path, _image("cloudinit-rpi", url=BOOKWORM_URL), options)
    assert (tmp_path / "custom.toml").exists()
    assert not (tmp_path / "network-config").exists()


def test_apply_warns_on_unrecognized_cloudinit_codename(tmp_path):
    unrecognized_url = (
        "https://downloads.raspberrypi.com/raspios_arm64/images/"
        "raspios_arm64-2027-01-01/2027-01-01-raspios-forky-arm64.img.xz"
    )
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    warnings = apply(
        tmp_path, _image("cloudinit-rpi", url=unrecognized_url), options
    )
    assert (tmp_path / "custom.toml").exists()
    assert any("forky" in w for w in warnings)


def test_apply_does_not_warn_for_known_bookworm_codename(tmp_path):
    options = FlashOptions(
        enable_ssh=False,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret"),
    )
    warnings = apply(
        tmp_path, _image("cloudinit-rpi", url=BOOKWORM_URL), options
    )
    assert warnings == []


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
