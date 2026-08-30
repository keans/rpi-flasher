from rpi_flasher import config
from rpi_flasher.state import FlashOptions, WlanConfig


def test_load_preferences_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    prefs = config.load_preferences()
    assert prefs == FlashOptions()


def test_save_and_load_preferences_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    options = FlashOptions(
        enable_ssh=True,
        setup_wlan=True,
        wlan=WlanConfig(ssid="home", password="secret", country="DE"),
        delete_image_after_flash=True,
    )
    config.save_preferences(options)
    loaded = config.load_preferences()

    assert loaded.enable_ssh is True
    assert loaded.setup_wlan is True
    assert loaded.wlan == WlanConfig(
        ssid="home", password="secret", country="DE"
    )
    # delete_image_after_flash is a per-run choice, not persisted.
    assert loaded.delete_image_after_flash is False


def test_save_preferences_writes_owner_only_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_preferences(FlashOptions())
    mode = config.config_path().stat().st_mode & 0o777
    assert mode == 0o600
