import asyncio

from textual.widgets import Button, Static

from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.overview import OverviewScreen
from rpi_flasher.state import DiskInfo, ImageEntry


def _image(extract_size: int) -> ImageEntry:
    return ImageEntry(
        name="Test OS",
        description="",
        icon_url="",
        url="https://example.com/x.img.xz",
        extract_size=extract_size,
        extract_sha256="abc",
        image_download_size=extract_size,
        release_date="2026-01-01",
        init_format=None,
        devices=[],
        capabilities=[],
    )


def test_flash_button_disabled_when_image_larger_than_disk():
    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state.disk = DiskInfo(
                "/dev/disk9", "/dev/rdisk9", 100, ["boot"]
            )
            app.state.image = _image(extract_size=1000)
            app.push_screen(OverviewScreen())
            await pilot.pause()

            screen = app.screen
            screen.query_one("#confirm-input").value = "/dev/disk9"
            await pilot.pause()

            assert screen.query_one("#flash-button", Button).disabled is True
            assert "larger than the card" in str(
                screen.query_one("#warnings", Static).render()
            )

    asyncio.run(run())


def test_flash_button_enabled_when_image_fits():
    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state.disk = DiskInfo(
                "/dev/disk9", "/dev/rdisk9", 32_000_000_000, ["boot"]
            )
            app.state.image = _image(extract_size=1000)
            app.push_screen(OverviewScreen())
            await pilot.pause()

            screen = app.screen
            screen.query_one("#confirm-input").value = "/dev/disk9"
            await pilot.pause()

            assert screen.query_one("#flash-button", Button).disabled is False

    asyncio.run(run())


def test_suspiciously_large_disk_shows_warning_but_stays_enabled():
    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.state.disk = DiskInfo(
                "/dev/disk9", "/dev/rdisk9", 1024**4, ["boot"]
            )
            app.state.image = _image(extract_size=1000)
            app.push_screen(OverviewScreen())
            await pilot.pause()

            screen = app.screen
            assert "unusually large" in str(
                screen.query_one("#warnings", Static).render()
            )
            screen.query_one("#confirm-input").value = "/dev/disk9"
            await pilot.pause()
            assert screen.query_one("#flash-button", Button).disabled is False

    asyncio.run(run())
