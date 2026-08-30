from rpi_flasher import config
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.overview import OverviewScreen
from rpi_flasher.screens.user_details import UserDetailsScreen
from rpi_flasher.screens.wlan_details import WlanDetailsScreen
from rpi_flasher.state import DiskInfo, FlashOptions, ImageEntry, UserConfig


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
    app.state.image = ImageEntry(
        "Raspberry Pi OS",
        "",
        "",
        "https://example.com/os.img.xz",
        5,
        "sha",
        5,
        "",
        None,
        [],
        [],
    )
    return app


def _fill(screen, username="pi-user", password="secret"):
    screen.username_field._lines = [username]
    screen.password_field._lines = [password]
    screen.confirm_field._lines = [password]


def test_invalid_username_is_rejected(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))
    app.push_screen(screen)
    _fill(screen, username="Invalid User")

    screen.next()

    assert app.screen is screen
    assert "Username must" in screen._validation_error


def test_password_must_match(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))
    app.push_screen(screen)
    _fill(screen)
    screen.confirm_field._lines = ["different"]

    screen.next()

    assert app.screen is screen
    assert "do not match" in screen._validation_error


def test_password_is_hashed_and_plaintext_discarded(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))
    app.push_screen(screen)
    _fill(screen)

    screen.next()

    assert isinstance(app.screen, OverviewScreen)
    assert app.state.options.user is not None
    assert app.state.options.user.password_hash.startswith("$6$")
    assert "secret" not in app.state.options.user.password_hash
    assert screen.password_field.value == ""
    assert screen.confirm_field.value == ""


def test_wlan_details_follow_user_details(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(
        FlashOptions(configure_user=True, setup_wlan=True)
    )
    app.push_screen(screen)
    _fill(screen)

    screen.next()

    assert isinstance(app.screen, WlanDetailsScreen)


def test_tab_moves_through_input_fields(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))
    app.push_screen(screen)

    app.manager.handle_key("\t")

    assert screen.window is not None
    assert screen.window.selected is screen.password_field

    app.manager.handle_key("\t")
    assert screen.window.selected is screen.confirm_field

    app.manager.handle_key("\t")
    assert screen.window.selected is screen.next_button


def test_username_field_is_focused_on_mount(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))

    app.push_screen(screen)

    assert screen.window is not None
    assert screen.window.selected is screen.username_field


def test_saved_user_is_prefilled_and_hash_can_be_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_preferences(
        FlashOptions(
            configure_user=True,
            user=UserConfig("saved-user", "$6$salt$hash"),
        )
    )
    app = _app(tmp_path, monkeypatch)
    screen = UserDetailsScreen(FlashOptions(configure_user=True))
    app.push_screen(screen)

    assert screen.username_field.value == "saved-user"
    screen.next()

    assert isinstance(app.screen, OverviewScreen)
    assert app.state.options.user == UserConfig("saved-user", "$6$salt$hash")


def test_user_is_saved_when_quitting_from_details(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    options = FlashOptions(configure_user=True)
    app.state.options = options
    screen = UserDetailsScreen(options)
    app.push_screen(screen)
    _fill(screen, username="saved-user", password="secret")

    app.exit()

    saved = config.load_preferences()
    assert saved.user is not None
    assert saved.user.username == "saved-user"
    assert saved.user.password_hash.startswith("$6$")
    assert "secret" not in saved.user.password_hash
