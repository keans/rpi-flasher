import asyncio

import httpx
from textual.widgets import Input, OptionList

from rpi_flasher import images
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.image_select import ImageSelectScreen
from rpi_flasher.state import ImageEntry


def _block_network(monkeypatch) -> None:
    """Screens fetch the OS list on mount; block that so these tests never
    hit the real network, and drive screen state directly instead."""

    async def fail_fetch():
        raise httpx.ConnectError("network disabled in tests")

    monkeypatch.setattr(images, "fetch_os_list", fail_fetch)
    monkeypatch.setattr(images, "load_snapshot", lambda: None)


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


def test_filter_narrows_by_device(monkeypatch, tmp_path):
    _block_network(monkeypatch)
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi4-64bit"], "bbb"),
    ]

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ImageSelectScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen._relabel_all(entries)
            screen._apply_filter("")
            assert len(screen._filtered) == 2

            screen.query_one("#filter", Input).value = "pi5"
            screen._apply_filter("pi5")
            assert [e.name for e in screen._filtered] == ["Raspberry Pi OS"]

    asyncio.run(run())


def test_delete_cached_binding_removes_cache_and_updates_label(
    monkeypatch, tmp_path
):
    _block_network(monkeypatch)
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entry = _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa")
    images.cache_path_for(entry).write_bytes(b"x" * 5)
    assert images.is_cached(entry) is True

    async def run():
        app = RpiFlasherApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ImageSelectScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen._relabel_all([entry])
            screen._apply_filter("")
            option_list = screen.query_one("#image-list", OptionList)
            option_list.highlighted = 0
            await pilot.pause()

            screen.action_delete_cached()

            assert images.is_cached(entry) is False
            assert "Deleted cached copy" in str(
                screen.query_one("#status").render()
            )

    asyncio.run(run())
