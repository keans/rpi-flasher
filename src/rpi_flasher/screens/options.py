"""SSH/WLAN/delete-after-flash checkboxes. WLAN details (SSID/password/
country) are collected on a separate follow-up screen only if requested,
so this screen stays a quick yes/no gate rather than a wall of fields."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Static

from rpi_flasher import config
from rpi_flasher.state import FlashOptions, finish_options
from rpi_flasher.utils import STEP_OPTIONS, step_title


class OptionsScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_OPTIONS), id="title"),
            Static("Customize the image before flashing.", classes="hint"),
            Checkbox("Enable SSH", id="enable-ssh", compact=True),
            Checkbox("Setup WLAN", id="setup-wlan", compact=True),
            Checkbox(
                "Delete downloaded image after successful flash",
                id="delete-after-flash",
                compact=True,
            ),
            Button("Next", id="next-button", variant="primary", compact=True),
            id="options-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        prefs = config.load_preferences()
        self.query_one("#enable-ssh", Checkbox).value = prefs.enable_ssh
        self.query_one("#setup-wlan", Checkbox).value = prefs.setup_wlan

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "next-button":
            return

        enable_ssh = self.query_one("#enable-ssh", Checkbox).value
        setup_wlan = self.query_one("#setup-wlan", Checkbox).value
        delete_after_flash = self.query_one(
            "#delete-after-flash", Checkbox
        ).value

        options = FlashOptions(
            enable_ssh=enable_ssh,
            setup_wlan=setup_wlan,
            wlan=None,
            delete_image_after_flash=delete_after_flash,
        )

        if setup_wlan:
            from rpi_flasher.screens.wlan_details import WlanDetailsScreen

            self.app.push_screen(WlanDetailsScreen(options))
            return

        finish_options(self, options)
