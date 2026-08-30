"""Review screen: summarizes every choice with a plain Next button. The
actual destructive yes/no decision lives on a separate modal dialog
(ConfirmFlashDialog), so this screen can be as long as it needs to be
without the confirm/deny buttons ever scrolling out of view."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from rpi_flasher.state import wizard_state
from rpi_flasher.utils import STEP_CONFIRM, human_bytes, step_title

# SD cards top out well below this in practice; a "SD card" reporting more
# is a strong signal the wrong device was selected (e.g. a USB dock that
# slipped past the removable-media filter).
SUSPICIOUSLY_LARGE_BYTES = 512 * 1024**3


def _image_too_large(image, disk) -> bool:
    return image.extract_size > disk.size_bytes


class OverviewScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        state = wizard_state(self)
        disk = state.disk
        image = state.image
        options = state.options

        volumes = ", ".join(disk.volume_names) or "(unnamed)"
        disk_line = (
            f"Disk: {disk.device_node} "
            f"({human_bytes(disk.size_bytes)}, {volumes})"
        )
        lines = [
            disk_line,
            f"Image: {image.name}",
            f"SSH enabled: {'yes' if options.enable_ssh else 'no'}",
        ]
        if options.setup_wlan and options.wlan:
            lines.append(
                f"WLAN: ssid={options.wlan.ssid!r} "
                f"country={options.wlan.country} "
                "password=" + "•" * 8
            )
        else:
            lines.append("WLAN: not configured")
        if image.devices:
            lines.append(f"Compatible devices: {', '.join(image.devices)}")

        too_big = _image_too_large(image, disk)
        warnings = []
        if too_big:
            warnings.append(
                f"ERROR: the image ({human_bytes(image.extract_size)}) is "
                f"larger than the card ({human_bytes(disk.size_bytes)}) -- "
                "this would fail partway through. Pick a smaller image or "
                "a bigger card."
            )
        elif disk.size_bytes > SUSPICIOUSLY_LARGE_BYTES:
            warnings.append(
                f"WARNING: {human_bytes(disk.size_bytes)} is unusually "
                "large for an SD card -- double-check you selected the "
                "right device before continuing."
            )

        warnings_static = Static("\n".join(warnings), id="warnings")
        warnings_static.display = bool(warnings)

        yield Header()
        yield Container(
            Static(step_title(STEP_CONFIRM), id="title"),
            Static(
                "Review every choice carefully before erasing the card.",
                classes="hint",
            ),
            Static("\n".join(lines), id="summary"),
            warnings_static,
            Button(
                "Next",
                id="next-button",
                variant="primary",
                compact=True,
                disabled=too_big,
            ),
            id="overview-body",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "next-button":
            return

        state = wizard_state(self)

        def handle_result(confirmed: bool) -> None:
            if confirmed:
                from rpi_flasher.screens.flash_progress import (
                    FlashProgressScreen,
                )

                self.app.push_screen(FlashProgressScreen())

        from rpi_flasher.screens.confirm_dialog import ConfirmFlashDialog

        self.app.push_screen(
            ConfirmFlashDialog(state.disk.device_node), handle_result
        )
