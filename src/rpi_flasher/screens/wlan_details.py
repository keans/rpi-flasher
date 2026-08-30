"""WLAN details dialog: SSID/password/country, shown only when WLAN setup
was requested on the Options screen."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from rpi_flasher import config
from rpi_flasher.state import FlashOptions, WlanConfig, finish_options
from rpi_flasher.utils import STEP_WLAN_DETAILS, step_title

DEFAULT_COUNTRY = "DE"


class WlanDetailsScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def __init__(self, pending_options: FlashOptions) -> None:
        super().__init__()
        self._pending_options = pending_options

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_WLAN_DETAILS), id="title"),
            Static(
                "Enter the network this Pi should join on first boot.",
                classes="hint",
            ),
            Input(placeholder="SSID", id="wlan-ssid", compact=True),
            Input(
                placeholder="Password",
                password=True,
                id="wlan-password",
                compact=True,
            ),
            Input(
                value=DEFAULT_COUNTRY,
                placeholder="2-letter country code (for example DE or US)",
                max_length=2,
                id="wlan-country",
                compact=True,
            ),
            Checkbox(
                "Remember Wi-Fi password on this Mac (stored in plaintext)",
                id="remember-wlan",
                compact=True,
            ),
            Static("", id="validation-error"),
            Button("Next", id="next-button", variant="primary", compact=True),
            id="wlan-details-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#validation-error", Static).display = False
        prefs = config.load_preferences()
        if prefs.wlan:
            self.query_one("#wlan-ssid", Input).value = prefs.wlan.ssid
            self.query_one("#wlan-password", Input).value = prefs.wlan.password
            self.query_one("#wlan-country", Input).value = prefs.wlan.country
            self.query_one("#remember-wlan", Checkbox).value = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "next-button":
            return

        ssid = self.query_one("#wlan-ssid", Input).value.strip()
        if not ssid:
            validation = self.query_one("#validation-error", Static)
            validation.display = True
            validation.update("SSID is required when WLAN setup is enabled.")
            return

        country = self.query_one("#wlan-country", Input).value.strip().upper()
        if len(country) != 2 or not country.isalpha():
            validation = self.query_one("#validation-error", Static)
            validation.display = True
            validation.update(
                "Country must be a 2-letter ISO code, such as DE, US, or GB."
            )
            return

        options = self._pending_options
        options.wlan = WlanConfig(
            ssid=ssid,
            password=self.query_one("#wlan-password", Input).value,
            country=country,
        )
        finish_options(
            self,
            options,
            remember_wlan=self.query_one("#remember-wlan", Checkbox).value,
        )
