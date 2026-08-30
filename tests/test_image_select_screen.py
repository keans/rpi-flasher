from rpi_flasher import images
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.config import SelectionPreferences
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

    app = RpiFlasherApp()
    screen = ImageSelectScreen(entries)
    app.push_screen(screen)

    assert len(screen._list_container.selectables) == 2


def test_remote_image_names_are_escaped_as_literal_markup(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entry = _entry("OS [red]name[/]", ["pi5-64bit"], "aaa")

    app = RpiFlasherApp()
    screen = ImageSelectScreen([entry])
    app.push_screen(screen)

    button = screen._list_container.selectables[0][0]
    assert r"\[red]" in button.label


def test_selecting_an_entry_advances_to_options(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu Server", ["pi5-64bit"], "bbb"),
    ]

    app = RpiFlasherApp()
    screen = ImageSelectScreen(entries)
    app.push_screen(screen)

    screen.select_image(1)

    from rpi_flasher.screens.options import OptionsScreen

    assert isinstance(app.screen, OptionsScreen)
    assert app.state.image is entries[1]


def test_delete_cached_removes_cache_and_updates_label(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entry = _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa")
    images.cache_path_for(entry).write_bytes(b"x" * 5)
    assert images.is_cached(entry) is True

    app = RpiFlasherApp()
    screen = ImageSelectScreen([entry])
    app.push_screen(screen)

    screen.delete_cached(0)

    assert images.is_cached(entry) is False
    assert "Deleted cached copy" in screen._status_label.value


def test_d_binding_deletes_the_selected_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Keep", ["pi5-64bit"], "aaa"),
        _entry("Delete", ["pi5-64bit"], "bbb"),
    ]
    images.cache_path_for(entries[1]).write_bytes(b"x" * 5)
    app = RpiFlasherApp()
    screen = ImageSelectScreen(entries)
    app.push_screen(screen)
    assert screen.window is not None
    screen.window.select(1)

    app.manager.handle_key("d")

    assert images.is_cached(entries[1]) is False


def test_saved_image_is_preselected(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    entries = [
        _entry("Raspberry Pi OS", ["pi5-64bit"], "aaa"),
        _entry("Ubuntu", ["pi5-64bit"], "bbb"),
    ]
    app = RpiFlasherApp()
    app.saved_selections = SelectionPreferences(image_id="bbb")
    screen = ImageSelectScreen(entries)
    app.push_screen(screen)

    assert screen.window is not None
    assert screen.window.selected_index == 1
