from rpi_flasher import config
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import FlashOptions, UserConfig


class _Screen(Screen):
    def build(self):
        raise AssertionError("not needed")


def test_ctrl_c_uses_active_screen_shutdown_policy(monkeypatch):
    app = RpiFlasherApp()
    screen = _Screen()
    screen.app = app
    app._stack.append(screen)
    called = []
    monkeypatch.setattr(screen, "on_interrupt", lambda: called.append(True))

    app.handle_interrupt()

    assert called == [True]
    assert app._interrupted is True


def test_quit_uses_active_screen_shutdown_policy(monkeypatch):
    app = RpiFlasherApp()
    screen = _Screen()
    screen.app = app
    app._stack.append(screen)
    called = []
    monkeypatch.setattr(screen, "on_interrupt", lambda: called.append(True))

    app._sync_quit_binding(screen)
    app.manager.handle_key("q")

    assert called == [True]
    assert app._interrupted is False
    assert app.shutdown_trigger == "Quit"


def test_interrupt_hint_confirms_saved_selections(capsys):
    app = RpiFlasherApp()

    app.show_interrupt_hint()

    error = capsys.readouterr().err
    assert "interrupted with Ctrl+C" in error
    assert "selections were saved" in error


def test_quitting_before_options_does_not_erase_saved_settings(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_preferences(
        FlashOptions(
            enable_ssh=True,
            configure_user=True,
            user=UserConfig("pi", "$6$salt$hash"),
        )
    )
    app = RpiFlasherApp()

    app.exit()

    saved = config.load_preferences()
    assert saved.enable_ssh is True
    assert saved.user == UserConfig("pi", "$6$salt$hash")
