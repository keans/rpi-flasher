from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens._widgets import CENTER_ALIGN
from rpi_flasher.screens.flash_progress import FlashProgressScreen
from rpi_flasher.screens.overview import OverviewScreen
from rpi_flasher.state import DiskInfo, ImageEntry, UserConfig


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


def test_erase_button_disabled_when_image_larger_than_disk():
    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 100, ["boot"])
    app.state.image = _image(extract_size=1000)
    screen = OverviewScreen()
    app.push_screen(screen)

    assert screen._yes_button.disabled is True
    assert "larger than the card" in screen._warnings_label.value

    screen.erase_and_flash()  # should be a no-op since the button is disabled
    assert app.screen is screen


def test_no_is_the_default_confirmation_choice():
    app = RpiFlasherApp()
    app.state.disk = DiskInfo(
        "/dev/disk9", "/dev/rdisk9", 32_000_000_000, ["boot"]
    )
    app.state.image = _image(extract_size=1000)
    screen = OverviewScreen()
    app.push_screen(screen)

    assert screen._yes_button.disabled is False
    assert screen.window is not None
    assert screen.window.selected_index == 0
    assert screen.window.selected is screen._no_button
    assert screen._confirm_row.parent_align == CENTER_ALIGN


def test_yes_starts_flashing(monkeypatch):
    monkeypatch.setattr(
        "rpi_flasher.screens.flash_progress.flash", lambda *args: None
    )
    app = RpiFlasherApp()
    app.state.disk = DiskInfo(
        "/dev/disk9", "/dev/rdisk9", 32_000_000_000, ["boot"]
    )
    app.state.image = _image(extract_size=1000)
    screen = OverviewScreen()
    app.push_screen(screen)

    screen.erase_and_flash()

    assert isinstance(app.screen, FlashProgressScreen)


def test_suspiciously_large_disk_shows_warning_but_stays_enabled():
    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 1024**4, ["boot"])
    app.state.image = _image(extract_size=1000)
    screen = OverviewScreen()
    app.push_screen(screen)

    assert "unusually large" in screen._warnings_label.value
    assert screen._yes_button.disabled is False


def test_incompatible_user_provisioning_is_shown_as_warning():
    app = RpiFlasherApp()
    app.state.disk = DiskInfo("/dev/disk9", "/dev/rdisk9", 1000, [])
    app.state.image = _image(extract_size=100)
    app.state.image.category_path = ["Other general-purpose OS"]
    app.state.options.configure_user = True
    app.state.options.user = UserConfig("pi", "$6$salt$hash")

    screen = OverviewScreen()
    app.push_screen(screen)

    assert "only works with compatible" in screen._warnings_label.value
    assert screen._yes_button.disabled is False
