import asyncio

from textual.widgets import Checkbox, Input

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

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
            app.push_screen(screen)
            await pilot.pause()
            assert screen.query_one("#wlan-country", Input).value == "DE"

    asyncio.run(run())


def test_empty_ssid_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
            app.push_screen(screen)
            await pilot.pause()

            screen.query_one("#next-button").press()
            await pilot.pause()

            assert isinstance(app.screen, WlanDetailsScreen)
            assert "SSID is required" in str(
                screen.query_one("#validation-error").render()
            )

    asyncio.run(run())


def test_filling_details_saves_and_advances_to_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))

    async def run():
        app = RpiFlasherApp()
        app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, [])
        app.state.image = _entry()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))
            app.push_screen(screen)
            await pilot.pause()

            screen.query_one("#wlan-ssid", Input).value = "home"
            screen.query_one("#wlan-country", Input).value = "US"
            screen.query_one("#remember-wlan", Checkbox).value = True
            await pilot.pause()
            screen.query_one("#next-button").press()
            await pilot.pause()

            assert isinstance(app.screen, OverviewScreen)
            assert app.state.options.wlan.ssid == "home"
            assert app.state.options.wlan.country == "US"

            prefs = config.load_preferences()
            assert prefs.wlan.country == "US"

    asyncio.run(run())
