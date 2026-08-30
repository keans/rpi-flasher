"""Review screen: summarizes every choice and asks for the final,
destructive yes/no decision in one place."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, images
from rpi_flasher.screens._widgets import (
    CENTER_ALIGN,
    make_action_button,
    make_action_row,
)
from rpi_flasher.screens.base import Screen, set_button_disabled
from rpi_flasher.state import DiskInfo, ImageEntry, wizard_state
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_CONFIRM, human_bytes

# SD cards top out well below this in practice; a "SD card" reporting more
# is a strong signal the wrong device was selected (e.g. a USB dock that
# slipped past the removable-media filter).
SUSPICIOUSLY_LARGE_BYTES = 512 * 1024**3


def _image_too_large(image: ImageEntry, disk: DiskInfo) -> bool:
    return image.extract_size > disk.size_bytes


class OverviewScreen(Screen):
    def build(self) -> ptg.Window:
        state = wizard_state(self)
        disk = state.disk
        image = state.image
        options = state.options
        assert disk is not None
        assert image is not None

        volumes = ", ".join(disk.volume_names) or "(unnamed)"
        lines = [
            (
                f"Disk: {disk.device_node} "
                f"({human_bytes(disk.size_bytes)}, {volumes})"
            ),
            f"Image: {image.name}",
            f"SSH enabled: {'yes' if options.enable_ssh else 'no'}",
        ]
        user_is_compatible = images.os_category(image) == "Raspberry Pi OS"
        if options.configure_user and options.user:
            status = (
                "will be configured"
                if user_is_compatible
                else "unsupported by this image"
            )
            lines.append(f"User: {options.user.username!r} ({status})")
        else:
            lines.append("User: not configured")
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
        warnings: list[str] = []
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
        if options.configure_user and options.user and not user_is_compatible:
            warnings.append(
                "WARNING: user provisioning only works with compatible "
                "Raspberry Pi OS images and will be skipped for this image."
            )

        self._no_button = make_action_button(
            "No, go back", onclick=lambda _: self.go_back()
        )
        self._yes_button = make_action_button("Yes, erase and flash")
        set_button_disabled(
            self._yes_button,
            too_big,
            handler=lambda _: self.erase_and_flash(),
            disabled_label="Erase unavailable (fix the error above first)",
            enabled_label="Yes, erase and flash",
        )
        warning_style = "error bold" if too_big else "warning"
        warning_text = ptg.escape_markup("\n".join(warnings))
        self._warnings_label = ptg.Label(
            f"[{warning_style}]{warning_text}[/]" if warnings else ""
        )
        self._confirm_row = make_action_row(
            self._no_button, self._yes_button, align=CENTER_ALIGN
        )

        window = ptg.Window(
            make_step_label(STEP_CONFIRM),
            ptg.Label(""),
            make_hint_label(
                "Review every choice carefully before erasing the card."
            ),
            ptg.Label(""),
            ptg.Label(ptg.escape_markup("\n".join(lines))),
            self._warnings_label,
            ptg.Label(""),
            ptg.Label(
                "[warning bold]"
                + ptg.escape_markup(
                    f"This will ERASE all data on {disk.device_node}. Proceed?"
                )
                + "[/]"
            ),
            ptg.Label(""),
            self._confirm_row,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind(ptg.keys.LEFT, lambda *_: window.select(0))
        window.bind(ptg.keys.RIGHT, lambda *_: window.select(1))
        return window

    def on_mount(self) -> None:
        # An accidental Enter must always choose the non-destructive answer.
        assert self.window is not None
        self.window.select(0)

    def go_back(self) -> None:
        self.app.pop_screen()

    def erase_and_flash(self) -> None:
        if self._yes_button.disabled:
            return
        from rpi_flasher.screens.flash_progress import FlashProgressScreen

        self.app.push_screen(FlashProgressScreen())
