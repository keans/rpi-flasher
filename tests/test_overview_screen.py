import asyncio

from textual.widgets import Button, Static

from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.confirm_dialog import ConfirmFlashDialog
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


def test_next_button_disabled_when_image_larger_than_disk():
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
            assert screen.query_one("#next-button", Button).disabled is True
            assert "larger than the card" in str(
                screen.query_one("#warnings", Static).render()
            )

    asyncio.run(run())


def test_next_button_opens_confirm_dialog():
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
            next_button = screen.query_one("#next-button", Button)
            assert next_button.disabled is False
            next_button.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ConfirmFlashDialog)

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
            assert screen.query_one("#next-button", Button).disabled is False

    asyncio.run(run())
