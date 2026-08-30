import asyncio

from textual.widgets import OptionList

from rpi_flasher import images
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.image_select import ImageSelectScreen
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


def test_lists_all_entries_without_a_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
    ]

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ImageSelectScreen(entries)
            app.push_screen(screen)
            await pilot.pause()
            option_list = screen.query_one("#image-list", OptionList)
            assert option_list.option_count == 2

    asyncio.run(run())


def test_arrow_keys_navigate_list(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
    ]

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ImageSelectScreen(entries)
            app.push_screen(screen)
            await pilot.pause()

            option_list = screen.query_one("#image-list", OptionList)
            option_list.highlighted = 0
            option_list.focus()
            await pilot.pause()

            await pilot.press("down")
            assert option_list.highlighted == 1

            await pilot.press("up")
            assert option_list.highlighted == 0

    asyncio.run(run())


def test_delete_cached_binding_removes_cache_and_updates_label(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entry = _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa")
    images.cache_path_for(entry).write_bytes(b"x" * 5)
    assert images.is_cached(entry) is True

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ImageSelectScreen([entry])
            app.push_screen(screen)
            await pilot.pause()
            option_list = screen.query_one("#image-list", OptionList)
            option_list.highlighted = 0
            await pilot.pause()

            screen.action_delete_cached()

            assert images.is_cached(entry) is False
            assert "Deleted cached copy" in str(
                screen.query_one("#status").render()
            )

    asyncio.run(run())
