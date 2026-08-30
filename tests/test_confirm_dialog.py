import asyncio

from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.confirm_dialog import ConfirmFlashDialog


def test_no_is_default_and_dismisses_false():
    result = {}

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(
                ConfirmFlashDialog("/dev/disk9"),
                lambda value: result.update(confirmed=value),
            )
            await pilot.pause()

            no_button = app.screen.query_one("#no-button")
            assert app.screen.focused is no_button

            await pilot.press("enter")
            await pilot.pause()

            assert result["confirmed"] is False

    asyncio.run(run())


def test_right_then_enter_confirms_yes():
    result = {}

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(
                ConfirmFlashDialog("/dev/disk9"),
                lambda value: result.update(confirmed=value),
            )
            await pilot.pause()

            await pilot.press("right")
            await pilot.press("enter")
            await pilot.pause()

            assert result["confirmed"] is True

    asyncio.run(run())


def test_escape_dismisses_as_no():
    result = {}

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(
                ConfirmFlashDialog("/dev/disk9"),
                lambda value: result.update(confirmed=value),
            )
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert result["confirmed"] is False

    asyncio.run(run())
