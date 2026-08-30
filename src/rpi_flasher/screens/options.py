"""SSH/WLAN/delete-after-flash checkboxes, pre-filled from saved prefs."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from rpi_flasher import config
from rpi_flasher.state import FlashOptions, WlanConfig, wizard_state


class OptionsScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Configure options", id="title"),
            Checkbox("Enable SSH", id="enable-ssh"),
            Checkbox("Setup WLAN", id="setup-wlan"),
            Vertical(
                Input(placeholder="SSID", id="wlan-ssid"),
                Input(
                    placeholder="Password", password=True, id="wlan-password"
                ),
                Input(
                    placeholder="Country code (e.g. US, DE)", id="wlan-country"
                ),
                id="wlan-fields",
            ),
            Checkbox(
                "Delete downloaded image after successful flash",
                id="delete-after-flash",
            ),
            Static("", id="validation-error"),
            Button("Next", id="next-button", variant="primary"),
            id="options-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        prefs = config.load_preferences()
        self.query_one("#enable-ssh", Checkbox).value = prefs.enable_ssh
        self.query_one("#setup-wlan", Checkbox).value = prefs.setup_wlan
        if prefs.wlan:
            self.query_one("#wlan-ssid", Input).value = prefs.wlan.ssid
            self.query_one("#wlan-password", Input).value = prefs.wlan.password
            self.query_one("#wlan-country", Input).value = prefs.wlan.country
        self._sync_wlan_visibility()

    def _sync_wlan_visibility(self) -> None:
        self.query_one("#wlan-fields", Vertical).display = self.query_one(
            "#setup-wlan", Checkbox
        ).value

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "setup-wlan":
            self._sync_wlan_visibility()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "next-button":
            return

        enable_ssh = self.query_one("#enable-ssh", Checkbox).value
        setup_wlan = self.query_one("#setup-wlan", Checkbox).value
        delete_after_flash = self.query_one(
            "#delete-after-flash", Checkbox
        ).value

        wlan = None
        if setup_wlan:
            ssid = self.query_one("#wlan-ssid", Input).value.strip()
            if not ssid:
                self.query_one("#validation-error", Static).update(
                    "SSID is required when WLAN setup is enabled."
                )
                return
            wlan = WlanConfig(
                ssid=ssid,
                password=self.query_one("#wlan-password", Input).value,
                country=self.query_one("#wlan-country", Input).value.strip()
                or "US",
            )

        options = FlashOptions(
            enable_ssh=enable_ssh,
            setup_wlan=setup_wlan,
            wlan=wlan,
            delete_image_after_flash=delete_after_flash,
        )
        wizard_state(self).options = options
        config.save_preferences(options)

        from rpi_flasher.screens.overview import OverviewScreen

        self.app.push_screen(OverviewScreen())
