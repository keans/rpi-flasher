import asyncio

import httpx
from textual.widgets import OptionList

from rpi_flasher import images
from rpi_flasher.app import RpiFlasherApp
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


def test_selecting_device_with_multiple_images_shows_os_select(
    monkeypatch,
):
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
        _entry("Other OS", ["pi4-64bit"], "ccc"),
    ]
    _stub_fetch_entries(monkeypatch, entries)

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = DeviceSelectScreen()
            app.push_screen(screen)
            await pilot.pause()
            assert screen._devices == ["pi5-64bit", "pi4-64bit"]

            option_list = screen.query_one("#device-list", OptionList)
            option_list.highlighted = screen._devices.index("pi5-64bit")
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert isinstance(app.screen, OsSelectScreen)

    asyncio.run(run())


def test_selecting_device_with_single_image_skips_to_options(monkeypatch):
    only_match = _entry("Raspberry Pi OS Lite", ["pi4-64bit"], "aaa")
    entries = [
        only_match,
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
    ]
    _stub_fetch_entries(monkeypatch, entries)

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = DeviceSelectScreen()
            app.push_screen(screen)
            await pilot.pause()

            option_list = screen.query_one("#device-list", OptionList)
            option_list.highlighted = screen._devices.index("pi4-64bit")
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert isinstance(app.screen, OptionsScreen)
            assert app.state.image is only_match

    asyncio.run(run())


def test_load_shows_retry_message_on_total_fetch_failure(monkeypatch):
    async def fail_fetch():
        raise httpx.ConnectError("network disabled in tests")

    monkeypatch.setattr(images, "fetch_os_list", fail_fetch)
    monkeypatch.setattr(images, "load_snapshot", lambda: None)

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = DeviceSelectScreen()
            app.push_screen(screen)
            await pilot.pause()
            assert "Press 'r' to retry" in str(
                screen.query_one("#status").render()
            )

    asyncio.run(run())
