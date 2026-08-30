"""Confirmation screen: summarizes choices, gates on typing the device node."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from rpi_flasher.state import wizard_state
from rpi_flasher.utils import human_bytes

# SD cards top out well below this in practice; a "SD card" reporting more
# is a strong signal the wrong device was selected (e.g. a USB dock that
# slipped past the bus-protocol filter).
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
        lines.append(
            "Delete image after flash: "
            + ("yes" if options.delete_image_after_flash else "no")
        )
        if image.devices:
            lines.append(f"Compatible devices: {', '.join(image.devices)}")

        warnings = []
        if _image_too_large(image, disk):
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

        yield Header()
        yield Container(
            Static("Confirm and flash", id="title"),
            Static("\n".join(lines), id="summary"),
            Static("\n".join(warnings), id="warnings"),
            Static(
                "This will ERASE all data on "
                f"{disk.device_node}. Type the device path "
                "to confirm:",
                id="confirm-prompt",
            ),
            Input(placeholder=disk.device_node, id="confirm-input"),
            Button(
                "Flash Now",
                id="flash-button",
                variant="error",
                disabled=True,
            ),
            id="overview-body",
        )
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "confirm-input":
            return
        state = wizard_state(self)
        too_big = _image_too_large(state.image, state.disk)
        button = self.query_one("#flash-button", Button)
        button.disabled = too_big or event.value != state.disk.device_node

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "flash-button":
            return
        from rpi_flasher.screens.flash_progress import FlashProgressScreen

        self.app.push_screen(FlashProgressScreen())
