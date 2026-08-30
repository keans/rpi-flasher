"""Shared dataclasses passed between wizard screens."""

from __future__ import annotations

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
