"""SSH/WLAN/delete-after-flash checkboxes. WLAN details (SSID/password/
country) are collected on a separate follow-up screen only if requested,
so this screen stays a quick yes/no gate rather than a wall of fields."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, config
from rpi_flasher.screens._widgets import (
    make_action_button,
    make_labeled_checkbox,
)
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import FlashOptions, finish_options
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_OPTIONS


class OptionsScreen(Screen):
    def __init__(self) -> None:
        prefs = config.load_preferences()
        self.enable_ssh = prefs.enable_ssh
        self.setup_wlan = prefs.setup_wlan
        self.delete_after_flash = False
        self._enable_ssh_box = make_labeled_checkbox(
            "Enable SSH",
            checked=self.enable_ssh,
            on_change=self._on_enable_ssh,
        )
        self._setup_wlan_box = make_labeled_checkbox(
            "Setup WLAN",
            checked=self.setup_wlan,
            on_change=self._on_setup_wlan,
        )
        self._delete_after_flash_box = make_labeled_checkbox(
            "Delete downloaded image after successful flash",
            checked=self.delete_after_flash,
            on_change=self._on_delete_after_flash,
        )
        self.next_button = make_action_button(
            "Next", onclick=lambda _: self.next()
        )

    def build(self) -> ptg.Window:
        window = ptg.Window(
            make_step_label(STEP_OPTIONS),
            ptg.Label(""),
            make_hint_label("Customize the image before flashing."),
            ptg.Label(""),
            self._enable_ssh_box,
            self._setup_wlan_box,
            self._delete_after_flash_box,
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

    def _on_enable_ssh(self, checked: bool) -> None:
        self.enable_ssh = checked

    def _on_setup_wlan(self, checked: bool) -> None:
        self.setup_wlan = checked

    def _on_delete_after_flash(self, checked: bool) -> None:
        self.delete_after_flash = checked

    def next(self) -> None:
        options = FlashOptions(
            enable_ssh=self.enable_ssh,
            setup_wlan=self.setup_wlan,
            wlan=None,
            delete_image_after_flash=self.delete_after_flash,
        )

        if self.setup_wlan:
            from rpi_flasher.screens.wlan_details import WlanDetailsScreen

            self.app.push_screen(WlanDetailsScreen(options))
            return

        finish_options(self, options)
