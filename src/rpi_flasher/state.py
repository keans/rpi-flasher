"""Shared dataclasses passed between wizard screens."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from textual.screen import Screen


@dataclass
class DiskInfo:
    device_node: str
    raw_device_node: str
    size_bytes: int
    volume_names: list[str]


@dataclass
class ImageEntry:
    name: str
    description: str
    icon_url: str
    url: str
    extract_size: int
    extract_sha256: str
    image_download_size: int
    release_date: str
    init_format: str | None
    devices: list[str]
    capabilities: list[str]
    category_path: list[str] = field(default_factory=list)


@dataclass
class WlanConfig:
    ssid: str
    password: str
    country: str = "US"


@dataclass
class FlashOptions:
    enable_ssh: bool = False
    setup_wlan: bool = False
    wlan: WlanConfig | None = None
    delete_image_after_flash: bool = False


@dataclass
class WizardState:
    disk: DiskInfo | None = None
    image: ImageEntry | None = None
    options: FlashOptions = field(default_factory=FlashOptions)


def wizard_state(screen: Screen) -> WizardState:
    """Typed access to the shared wizard state from a screen, so screens
    don't each need their own `# type: ignore[attr-defined]` on
    `self.app.state` (RpiFlasherApp sets this attribute dynamically)."""
    return cast("WizardState", screen.app.state)  # type: ignore[attr-defined]


def narrow_or_advance(
    screen: Screen,
    matching: list[ImageEntry],
    next_screen_factory: Callable[[list[ImageEntry]], Screen],
) -> None:
    """Shared by each narrowing step (device, then OS family): once a
    choice leaves exactly one compatible image, there's nothing left to
    pick, so skip straight to Options instead of pushing another
    single-item list; otherwise hand the narrowed list to the next
    narrowing/selection screen."""
    if len(matching) == 1:
        wizard_state(screen).image = matching[0]
        from rpi_flasher.screens.options import OptionsScreen

        screen.app.push_screen(OptionsScreen())
    else:
        screen.app.push_screen(next_screen_factory(matching))


def finish_options(
    screen: Screen, options: FlashOptions, *, remember_wlan: bool = True
) -> None:
    """Shared tail of the Options/WLAN-details screens: store the
    finalized options, persist the reusable (ssh/wlan) preferences, and
    move on to the confirmation screen. `remember_wlan` is only consulted
    when `options.wlan` is set; the plain Options path has nothing
    sensitive to opt in/out of, so it defaults to True."""
    wizard_state(screen).options = options

    from rpi_flasher.config import save_preferences

    save_preferences(options, remember_wlan=remember_wlan)

    from rpi_flasher.screens.overview import OverviewScreen

    screen.app.push_screen(OverviewScreen())
