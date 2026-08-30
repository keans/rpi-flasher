from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.base import Screen


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
