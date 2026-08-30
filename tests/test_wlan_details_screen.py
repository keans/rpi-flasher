from rpi_flasher import config
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.overview import OverviewScreen
from rpi_flasher.screens.wlan_details import WlanDetailsScreen
from rpi_flasher.state import DiskInfo, FlashOptions, ImageEntry


def _entry() -> ImageEntry:
    return ImageEntry(
        name="Test OS",
        description="",
        icon_url="",
        url="https://example.com/x.img.xz",
        extract_size=5,
        extract_sha256="abc",
        image_download_size=5,
        release_date="2026-01-01",
        init_format=None,
        devices=[],
        capabilities=[],
    )


def test_country_defaults_to_germany(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
    app.push_screen(screen)

    assert screen.country_field.value == "DE"


def test_empty_ssid_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
    app.push_screen(screen)

    screen.next()

    assert app.screen is screen
    assert "SSID is required" in screen._validation_error


def test_non_iso_country_code_is_rejected(tmp_path, monkeypatch):
    # "UK" is a common mistake for the United Kingdom's actual ISO/Wi-Fi
    # regulatory code, "GB" -- raspi-config's do_wifi_country rejects it
    # on the Pi and never unblocks rfkill, silently leaving Wi-Fi radio-
    # blocked with no visible error, so this must be caught here instead.
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
    app.push_screen(screen)

    screen.ssid_field._lines = ["home"]
    screen.country_field._lines = ["UK"]
    screen.next()

    assert app.screen is screen
    assert "ISO Wi-Fi regulatory code" in screen._validation_error


def test_filling_details_saves_and_advances_to_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
    app.state.image = _entry()
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
    app.push_screen(screen)

    screen.ssid_field._lines = ["home"]
    screen.country_field._lines = ["US"]
    screen.remember_box.checked = True
    screen.next()

    assert isinstance(app.screen, OverviewScreen)
    assert app.state.options.wlan.ssid == "home"
    assert app.state.options.wlan.country == "US"

    prefs = config.load_preferences()
    assert prefs.wlan.country == "US"


def test_tab_jumps_to_next_button(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    app = RpiFlasherApp()
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
    app.push_screen(screen)

    app.manager.handle_key("\t")

    assert screen.window is not None
    assert screen.window.selected is screen.next_button
