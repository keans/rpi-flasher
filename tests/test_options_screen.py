import asyncio

from textual.widgets import Checkbox

from rpi_flasher import config
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.options import OptionsScreen
from rpi_flasher.screens.overview import OverviewScreen
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

    async def run():
        app = RpiFlasherApp()
        app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
        app.state.image = _entry()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = OptionsScreen()
            app.push_screen(screen)
            await pilot.pause()

            screen.query_one("#next-button").press()
            await pilot.pause()

            assert isinstance(app.screen, OverviewScreen)
            assert app.state.options.wlan is None

    asyncio.run(run())


def test_checked_wlan_advances_to_details_screen(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    async def run():
        app = RpiFlasherApp()
        app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
        app.state.image = _entry()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = OptionsScreen()
            app.push_screen(screen)
            await pilot.pause()

            screen.query_one("#setup-wlan", Checkbox).value = True
            await pilot.pause()
            screen.query_one("#next-button").press()
            await pilot.pause()

            assert isinstance(app.screen, WlanDetailsScreen)

    asyncio.run(run())
