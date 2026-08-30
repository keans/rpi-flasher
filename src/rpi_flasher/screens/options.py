"""Optional image customization choices."""

from __future__ import annotations

from dataclasses import replace

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, config
from rpi_flasher.screens._widgets import (
    make_action_button,
    make_labeled_checkbox,
)
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import finish_options
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_OPTIONS


class OptionsScreen(Screen):
    def __init__(self) -> None:
        prefs = config.load_preferences()
        self.enable_ssh = prefs.enable_ssh
        self.setup_wlan = prefs.setup_wlan
        self.configure_user = prefs.configure_user
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
        self._configure_user_box = make_labeled_checkbox(
            "Configure username and password",
            checked=self.configure_user,
            on_change=self._on_configure_user,
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
            self._configure_user_box,
            make_hint_label(
                "User provisioning only works with compatible Raspberry Pi "
                "OS images."
            ),
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

    def _on_configure_user(self, checked: bool) -> None:
        self.configure_user = checked

    def _on_delete_after_flash(self, checked: bool) -> None:
        self.delete_after_flash = checked

    def next(self) -> None:
        options = replace(
            self.app.state.options,
            enable_ssh=self.enable_ssh,
            setup_wlan=self.setup_wlan,
            wlan=None,
            configure_user=self.configure_user,
            delete_image_after_flash=self.delete_after_flash,
        )

        if self.configure_user:
            from rpi_flasher.screens.user_details import UserDetailsScreen

            self.app.push_screen(UserDetailsScreen(options))
            return

        if self.setup_wlan:
            from rpi_flasher.screens.wlan_details import WlanDetailsScreen

            self.app.push_screen(WlanDetailsScreen(options))
            return

        finish_options(self, options)

    def store_selection(self) -> None:
        self.app.state.options = replace(
            self.app.state.options,
            enable_ssh=self.enable_ssh,
            setup_wlan=self.setup_wlan,
            configure_user=self.configure_user,
            delete_image_after_flash=self.delete_after_flash,
        )
