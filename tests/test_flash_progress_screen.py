from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.flasher import FlashProgress
from rpi_flasher.screens.flash_progress import FlashProgressScreen


def _screen_without_worker(
    monkeypatch,
) -> tuple[RpiFlasherApp, FlashProgressScreen]:
    monkeypatch.setattr(
        FlashProgressScreen, "_start_flash_thread", lambda self: None
    )
    monkeypatch.setattr(
        FlashProgressScreen, "start_polling", lambda self, *args: None
    )
    app = RpiFlasherApp()
    screen = FlashProgressScreen()
    app.push_screen(screen)
    return app, screen


def test_tab_focuses_cancel_while_progress_is_running(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)

    app.manager.handle_key("\t")

    assert screen.window is not None
    assert screen.window.selected is screen.cancel_button


def test_tab_cycles_through_failure_actions(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)
    screen._error = "failed"
    screen._render()

    app.manager.handle_key("\t")
    assert screen.window is not None
    assert screen.window.selected is screen.retry_button

    app.manager.handle_key("\t")
    assert screen.window.selected is screen.quit_button

    app.manager.handle_key("\t")
    assert screen.window.selected is screen.retry_button


def test_success_only_shows_quit(monkeypatch):
    _, screen = _screen_without_worker(monkeypatch)
    screen._done = True

    screen._render()

    assert [widget for widget, _ in screen._buttons_row.selectables] == [
        screen.quit_button
    ]


def test_escape_never_leaves_flash_screen(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)
    screen._done = True

    screen.on_escape()

    assert app.screen is screen


def test_cancel_button_sets_event_during_cancellable_phase(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)
    screen._latest = FlashProgress("Downloading", 10, 100, cancellable=True)
    screen._render()
    app.manager.handle_key("\t")

    app.manager.handle_key("\r")

    assert screen._cancel_event.is_set()
    assert screen.cancel_button.label == "Cancelling..."


def test_cancel_button_works_during_raw_write(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)
    screen._latest = FlashProgress("Writing", 10, 100, cancellable=True)
    screen._render()
    app.manager.handle_key("\t")

    app.manager.handle_key("\r")

    assert screen._cancel_event.is_set() is True
    assert screen.cancel_button.label == "Cancelling..."
    assert screen.cancel_button.onclick is None


def test_ctrl_c_requests_safe_cancel_then_exits_after_acknowledgement(
    monkeypatch,
):
    app, screen = _screen_without_worker(monkeypatch)
    exits = []
    monkeypatch.setattr(app, "exit", lambda: exits.append(True))
    screen._latest = FlashProgress("Downloading", 10, 100, cancellable=True)

    screen.on_interrupt()

    assert screen._cancel_event.is_set()
    assert exits == []
    screen._error = "Download cancelled -- safe to retry."
    screen._render()
    assert exits == [True]


def test_ctrl_c_waits_for_non_cancellable_disk_operation(monkeypatch):
    app, screen = _screen_without_worker(monkeypatch)
    exits = []
    monkeypatch.setattr(app, "exit", lambda: exits.append(True))
    screen._latest = FlashProgress("Remounting", 0, 1, cancellable=False)

    screen.on_interrupt()

    assert screen._cancel_event.is_set() is False
    assert exits == []
    assert "cannot be interrupted safely" in screen._result_label.value
    screen._done = True
    screen._render()
    assert exits == [True]


def test_unexpected_worker_exception_becomes_visible_error(monkeypatch):
    _, screen = _screen_without_worker(monkeypatch)

    def fail(*_args):
        raise RuntimeError("implementation detail")

    monkeypatch.setattr("rpi_flasher.screens.flash_progress.flash", fail)
    screen._run_flash()

    assert screen._error is not None
    assert "unexpected error" in screen._error
    assert "implementation detail" not in screen._error


def test_eta_uses_moving_window_instead_of_latest_jump(monkeypatch):
    _, screen = _screen_without_worker(monkeypatch)
    times = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(
        "rpi_flasher.screens.flash_progress.time.monotonic",
        lambda: next(times),
    )

    assert screen._speed_text(FlashProgress("Writing", 0, 1000)) == ""
    assert "100 B/s" in screen._speed_text(FlashProgress("Writing", 100, 1000))
    # The latest interval jumped to 400 B/s, but the two-second window is
    # 500 bytes / 2 seconds, producing a steadier 250 B/s estimate.
    text = screen._speed_text(FlashProgress("Writing", 500, 1000))
    assert "250 B/s" in text
    assert "ETA 00:02" in text


def test_eta_ignores_duplicate_redraw_samples(monkeypatch):
    _, screen = _screen_without_worker(monkeypatch)
    times = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(
        "rpi_flasher.screens.flash_progress.time.monotonic",
        lambda: next(times),
    )

    screen._speed_text(FlashProgress("Downloading", 0, 1000))
    first = screen._speed_text(FlashProgress("Downloading", 100, 1000))
    duplicate = screen._speed_text(FlashProgress("Downloading", 100, 1000))

    assert duplicate == first
    assert len(screen._rate_samples) == 2


def test_eta_resets_when_phase_changes(monkeypatch):
    _, screen = _screen_without_worker(monkeypatch)
    times = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(
        "rpi_flasher.screens.flash_progress.time.monotonic",
        lambda: next(times),
    )

    screen._speed_text(FlashProgress("Downloading", 0, 1000))
    assert screen._speed_text(FlashProgress("Downloading", 100, 1000))

    assert screen._speed_text(FlashProgress("Writing", 0, 1000)) == ""
    assert list(screen._rate_samples) == [(2.0, 0)]
