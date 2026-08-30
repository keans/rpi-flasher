"""WLAN details screen: SSID/password/country, shown only when WLAN setup
was requested on the Options screen."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, config
from rpi_flasher.screens._widgets import (
    CONTROL_ALIGN,
    MaskedInputField,
    align_prompts,
    make_action_button,
    make_labeled_checkbox,
)
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import FlashOptions, WlanConfig, finish_options
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_WLAN_DETAILS

DEFAULT_COUNTRY = "DE"


class WlanDetailsScreen(Screen):
    blocks_quit_shortcut = True

    def __init__(self, pending_options: FlashOptions) -> None:
        self._pending_options = pending_options

        prefs = config.load_preferences()
        remember_default = prefs.wlan is not None
        ssid = prefs.wlan.ssid if prefs.wlan else ""
        password = prefs.wlan.password if prefs.wlan else ""
        country = prefs.wlan.country if prefs.wlan else DEFAULT_COUNTRY

        ssid_prompt, password_prompt, country_prompt = align_prompts(
            ["SSID", "Password", "Country"]
        )
        self.ssid_field = ptg.InputField(
            ssid, prompt=ssid_prompt, parent_align=CONTROL_ALIGN
        )
        self.password_field = MaskedInputField(
            password, prompt=password_prompt, parent_align=CONTROL_ALIGN
        )
        self.country_field = ptg.InputField(
            country, prompt=country_prompt, parent_align=CONTROL_ALIGN
        )
        self.remember_box = make_labeled_checkbox(
            "Remember Wi-Fi password on this Mac (stored in plaintext)",
            checked=remember_default,
        )
        self._validation_error = ""
        self._validation_label = ptg.Label("")
        self.next_button = make_action_button(
            "Next", onclick=lambda _: self.next()
        )

    def build(self) -> ptg.Window:
        window = ptg.Window(
            make_step_label(STEP_WLAN_DETAILS),
            ptg.Label(""),
            make_hint_label(
                "Enter the network this Pi should join on first boot."
            ),
            ptg.Label(""),
            self.ssid_field,
            self.password_field,
            self.country_field,
            self.remember_box,
            self._validation_label,
            ptg.Label(""),
            self.next_button,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind(
            ptg.keys.TAB,
            lambda *_: self.select_widget(self.next_button),
            "Jump to Next",
        )
        return window

    def next(self) -> None:
        ssid = self.ssid_field.value.strip()
        if not ssid:
            self.set_error(
                self._validation_label,
                "SSID is required when WLAN setup is enabled.",
            )
            return

        country = self.country_field.value.strip().upper()
        if len(country) != 2 or not country.isalpha():
            self.set_error(
                self._validation_label,
                "Country must be a 2-letter ISO code, such as DE, US, or GB.",
            )
            return

        options = self._pending_options
        options.wlan = WlanConfig(
            ssid=ssid,
            password=self.password_field.value,
            country=country,
        )
        finish_options(self, options, remember_wlan=self.remember_box.checked)

    def store_selection(self) -> None:
        ssid = self.ssid_field.value.strip()
        country = self.country_field.value.strip().upper()
        if not ssid or len(country) != 2 or not country.isalpha():
            return
        self._pending_options.wlan = WlanConfig(
            ssid=ssid,
            password=self.password_field.value,
            country=country,
        )
        self.app.remember_wlan = self.remember_box.checked
        self.app.state.options = self._pending_options
