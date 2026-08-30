import json

from rpi_flasher import config
from rpi_flasher.state import (
    DiskInfo,
    FlashOptions,
    ImageEntry,
    UserConfig,
    WizardState,
    WlanConfig,
)


def test_load_preferences_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    prefs = config.load_preferences()
    assert prefs == FlashOptions(configure_user=True)


def test_load_preferences_ignores_malformed_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.config_dir().mkdir(parents=True)
    config.config_path().write_text(
        json.dumps(
            {
                "enable_ssh": "yes",
                "wlan": "not an object",
                "selections": {
                    "device": ["not", "a", "string"],
                    "disk_size_bytes": "large",
                },
            }
        )
    )

    assert config.load_preferences().enable_ssh is False
    assert config.load_preferences().wlan is None
    assert config.load_selections().device is None
    assert config.load_selections().disk_size_bytes is None


def test_save_and_load_preferences_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    options = FlashOptions(
        enable_ssh=True,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret", country="DE"),
        delete_image_after_flash=True,
    )
    config.save_preferences(options, remember_wlan=True)
    loaded = config.load_preferences()

    assert loaded.enable_ssh is True
    assert loaded.setup_wlan is True
    assert loaded.wlan == WlanConfig(
        ssid="home", password="secret", country="DE"
    )
    # delete_image_after_flash is a per-run choice, not persisted.
    assert loaded.delete_image_after_flash is False


def test_user_account_preferences_round_trip_as_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    options = FlashOptions(
        configure_user=True,
        user=UserConfig("pi-user", "$6$salt$hash"),
    )

    config.save_preferences(options)
    loaded = config.load_preferences()

    assert loaded.configure_user is True
    assert loaded.user == UserConfig("pi-user", "$6$salt$hash")


def test_wifi_credentials_are_not_saved_without_explicit_opt_in(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    options = FlashOptions(
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret", country="DE"),
    )

    config.save_preferences(options)

    assert config.load_preferences().wlan is None


def test_save_preferences_writes_owner_only_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_preferences(FlashOptions())
    mode = config.config_path().stat().st_mode & 0o777
    assert mode == 0o600


def test_wizard_selections_round_trip_without_losing_other_preferences(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_preferences(FlashOptions(enable_ssh=True))
    image = ImageEntry(
        "OS",
        "",
        "",
        "https://example.com/os.img",
        5,
        "sha",
        5,
        "",
        None,
        [],
        [],
    )
    state = WizardState(
        disk=DiskInfo("/dev/disk9", "/dev/rdisk9", 100, []),
        device="pi5-64bit",
        os_category="Raspberry Pi OS",
        image=image,
    )

    config.save_selections(state)
    selections = config.load_selections()

    assert selections.disk_device_node == "/dev/disk9"
    assert selections.disk_size_bytes == 100
    assert selections.disk_volume_names == ()
    assert selections.device == "pi5-64bit"
    assert selections.os_category == "Raspberry Pi OS"
    assert selections.image_id == "sha"
    assert config.load_preferences().enable_ssh is True
