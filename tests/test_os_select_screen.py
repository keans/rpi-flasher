import asyncio

from textual.widgets import OptionList

from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.image_select import ImageSelectScreen
from rpi_flasher.screens.options import OptionsScreen
from rpi_flasher.screens.os_select import OsSelectScreen
from rpi_flasher.state import ImageEntry


def _entry(name: str, category_path: list[str], sha: str) -> ImageEntry:
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
        devices=["pi5-64bit"],
        capabilities=[],
        category_path=category_path,
    )


def test_top_level_entries_grouped_under_raspberry_pi_os():
    entries = [
        _entry("Raspberry Pi OS (64-bit)", [], "aaa"),
        _entry("RetroPie", ["Media player OS"], "bbb"),
    ]
    screen = OsSelectScreen(entries)
    assert screen._categories == ["Raspberry Pi OS", "Media player OS"]


def test_selecting_category_with_multiple_images_shows_image_select():
    entries = [
        _entry("Raspberry Pi OS (64-bit)", [], "aaa"),
        _entry("Raspberry Pi OS Lite", [], "bbb"),
        _entry("RetroPie", ["Media player OS"], "ccc"),
    ]

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = OsSelectScreen(entries)
            app.push_screen(screen)
            await pilot.pause()

            option_list = screen.query_one("#os-list", OptionList)
            option_list.highlighted = screen._categories.index(
                "Raspberry Pi OS"
            )
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert isinstance(app.screen, ImageSelectScreen)

    asyncio.run(run())


def test_selecting_category_with_single_image_skips_to_options():
    only_match = _entry("RetroPie", ["Media player OS"], "ccc")
    entries = [
        _entry("Raspberry Pi OS (64-bit)", [], "aaa"),
        only_match,
    ]

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = OsSelectScreen(entries)
            app.push_screen(screen)
            await pilot.pause()

            option_list = screen.query_one("#os-list", OptionList)
            option_list.highlighted = screen._categories.index(
                "Media player OS"
            )
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert isinstance(app.screen, OptionsScreen)
            assert app.state.image is only_match

    asyncio.run(run())
