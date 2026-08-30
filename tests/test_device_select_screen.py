import httpx

from rpi_flasher import images
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.config import SelectionPreferences
from rpi_flasher.screens.device_select import DeviceSelectScreen
from rpi_flasher.screens.options import OptionsScreen
from rpi_flasher.screens.os_select import OsSelectScreen
from rpi_flasher.state import ImageEntry


def _entry(name: str, devices: list[str], sha: str) -> ImageEntry:
    return ImageEntry(
        name=name,
        description="",
        icon_url="",
        url=f"https://example.com/{sha}.img.xz",
        extract_size=5,
        extract_sha256=sha,
        image_download_size=5,
        release_date="2026-01-01",
        init_format=None,
        devices=devices,
        capabilities=[],
    )


def _stub_fetch_entries(monkeypatch, entries: list[ImageEntry]) -> None:
    async def fake_fetch_entries():
        return entries, ""

    monkeypatch.setattr(images, "fetch_entries", fake_fetch_entries)


def _finish_load(app: RpiFlasherApp, screen: DeviceSelectScreen) -> None:
    screen._load_thread.join(timeout=1)
    assert not screen._load_thread.is_alive()
    app.manager.process_pending_callbacks()


def test_selecting_device_with_multiple_images_shows_os_select(
    monkeypatch,
):
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
        _entry("Other OS", ["pi4-64bit"], "ccc"),
    ]
    _stub_fetch_entries(monkeypatch, entries)

    app = RpiFlasherApp()
    screen = DeviceSelectScreen()
    app.push_screen(screen)
    _finish_load(app, screen)

    assert screen._devices == ["pi5-64bit", "pi4-64bit"]

    screen.select_device(screen._devices.index("pi5-64bit"))

    assert isinstance(app.screen, OsSelectScreen)


def test_selecting_device_with_single_image_skips_to_options(monkeypatch):
    only_match = _entry("Raspberry Pi OS Lite", ["pi4-64bit"], "aaa")
    entries = [
        only_match,
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
    ]
    _stub_fetch_entries(monkeypatch, entries)

    app = RpiFlasherApp()
    screen = DeviceSelectScreen()
    app.push_screen(screen)
    _finish_load(app, screen)

    screen.select_device(screen._devices.index("pi4-64bit"))

    assert isinstance(app.screen, OptionsScreen)
    assert app.state.image is only_match


def test_load_shows_retry_message_on_total_fetch_failure(monkeypatch):
    async def fail_fetch():
        raise httpx.ConnectError("network disabled in tests")

    monkeypatch.setattr(images, "fetch_os_list", fail_fetch)
    monkeypatch.setattr(images, "load_snapshot", lambda: None)

    app = RpiFlasherApp()
    screen = DeviceSelectScreen()
    app.push_screen(screen)
    _finish_load(app, screen)

    assert "Press 'r' to retry" in screen._status_label.value


def test_r_binding_retries_fetch(monkeypatch):
    entries = [_entry("Raspberry Pi OS", ["pi5-64bit"], "aaa")]
    calls = 0

    async def fake_fetch_entries():
        nonlocal calls
        calls += 1
        return entries, ""

    monkeypatch.setattr(images, "fetch_entries", fake_fetch_entries)
    app = RpiFlasherApp()
    screen = DeviceSelectScreen()
    app.push_screen(screen)
    _finish_load(app, screen)
    assert screen.window is not None

    app.manager.handle_key("r")
    _finish_load(app, screen)

    assert calls == 2


def test_saved_device_is_preselected(monkeypatch):
    entries = [
        _entry("Pi 5 OS", ["pi5-64bit"], "aaa"),
        _entry("Pi 4 OS", ["pi4-64bit"], "bbb"),
    ]
    _stub_fetch_entries(monkeypatch, entries)
    app = RpiFlasherApp()
    app.saved_selections = SelectionPreferences(device="pi4-64bit")
    screen = DeviceSelectScreen()
    app.push_screen(screen)
    _finish_load(app, screen)

    assert screen.window is not None
    assert screen._devices[screen.window.selected_index] == "pi4-64bit"


def test_stale_fetch_result_does_not_replace_newer_result(monkeypatch):
    app = RpiFlasherApp()
    screen = DeviceSelectScreen()
    screen.app = app
    screen._load_generation = 2
    newest = [_entry("Newest", ["pi5-64bit"], "new")]
    stale = [_entry("Stale", ["pi4-64bit"], "old")]

    screen._finish_load(newest, "new", error=None, generation=2)
    screen._finish_load(stale, "old", error=None, generation=1)

    assert screen._entries == newest
