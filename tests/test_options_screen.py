from rpi_flasher import config
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.options import OptionsScreen
from rpi_flasher.screens.overview import OverviewScreen
from rpi_flasher.screens.user_details import UserDetailsScreen
from rpi_flasher.screens.wlan_details import WlanDetailsScreen
from rpi_flasher.state import DiskInfo, ImageEntry


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


def test_unchecked_wlan_skips_details_screen(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
    app.state.image = _entry()
    screen = OptionsScreen()
    app.push_screen(screen)

    screen.configure_user = False
    screen.next()

    assert isinstance(app.screen, OverviewScreen)
    assert app.state.options.wlan is None


def test_checked_wlan_advances_to_details_screen(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
    app.state.image = _entry()
    screen = OptionsScreen()
    app.push_screen(screen)

    screen.configure_user = False
    screen.setup_wlan = True
    screen.next()

    assert isinstance(app.screen, WlanDetailsScreen)


def test_checked_user_advances_to_user_details(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    app = RpiFlasherApp()
    screen = OptionsScreen()
    app.push_screen(screen)

    screen.configure_user = True
    screen.next()

    assert isinstance(app.screen, UserDetailsScreen)


def test_tab_jumps_to_next_button(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    app = RpiFlasherApp()
    screen = OptionsScreen()
    app.push_screen(screen)

    app.manager.handle_key("\t")

    assert screen.window is not None
    assert screen.window.selected is screen.next_button


def test_user_configuration_is_enabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    screen = OptionsScreen()

    assert screen.configure_user is True
    assert screen._configure_user_box.checked is True


def test_option_changes_are_saved_when_quitting(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    app = RpiFlasherApp()
    screen = OptionsScreen()
    app.push_screen(screen)
    screen.enable_ssh = True
    screen.configure_user = False

    app.exit()

    saved = config.load_preferences()
    assert saved.enable_ssh is True
    assert saved.configure_user is False
