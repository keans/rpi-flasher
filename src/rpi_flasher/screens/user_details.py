"""Username and password provisioning for compatible Raspberry Pi OS images."""

from __future__ import annotations

import re

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, config
from rpi_flasher.screens._widgets import (
    CONTROL_ALIGN,
    MaskedInputField,
    align_prompts,
    make_action_button,
)
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import FlashOptions, UserConfig, finish_options
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_USER_DETAILS

USERNAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")


def hash_password(password: str) -> str:
    """Return the SHA-512 crypt hash required by Pi OS userconf.txt."""
    from passlib.hash import sha512_crypt

    return sha512_crypt.hash(password)


class UserDetailsScreen(Screen):
    blocks_quit_shortcut = True

    def __init__(self, pending_options: FlashOptions) -> None:
        self._pending_options = pending_options
        saved_user = pending_options.user or config.load_preferences().user
        self._saved_password_hash = (
            saved_user.password_hash if saved_user is not None else None
        )
        username_prompt, password_prompt, confirm_prompt = align_prompts(
            ["Username", "Password", "Confirm password"]
        )
        self.username_field = ptg.InputField(
            saved_user.username if saved_user else "",
            prompt=username_prompt,
            parent_align=CONTROL_ALIGN,
        )
        self.password_field = MaskedInputField(
            "", prompt=password_prompt, parent_align=CONTROL_ALIGN
        )
        self.confirm_field = MaskedInputField(
            "", prompt=confirm_prompt, parent_align=CONTROL_ALIGN
        )
        self._validation_error = ""
        self._validation_label = ptg.Label("")
        self.next_button = make_action_button(
            "Next", onclick=lambda _: self.next()
        )

    def build(self) -> ptg.Window:
        window = ptg.Window(
            make_step_label(STEP_USER_DETAILS),
            ptg.Label(""),
            make_hint_label(
                "Creates the first admin user without first-boot questions. "
                "Only compatible Raspberry Pi OS images support this. Leave "
                "password blank to reuse the saved password."
            ),
            ptg.Label(""),
            self.username_field,
            self.password_field,
            self.confirm_field,
            self._validation_label,
            ptg.Label(""),
            self.next_button,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind(
            ptg.keys.TAB,
            lambda *_: self.focus_next_control(),
            "Next field",
        )
        return window

    def on_mount(self) -> None:
        self.select_widget(self.username_field)

    def focus_next_control(self) -> None:
        controls = [
            self.username_field,
            self.password_field,
            self.confirm_field,
            self.next_button,
        ]
        selected = self.window.selected if self.window is not None else None
        try:
            index = (controls.index(selected) + 1) % len(controls)
        except ValueError:
            index = 0
        self.select_widget(controls[index])

    def _resolve_password_hash(self) -> str | None:
        """Return the hash to save, or None if the current password/
        confirm fields don't resolve to one (blank with nothing saved
        to fall back on, or a mismatched confirmation) -- shared by
        `next()` (which reports *why* to the user) and `store_selection()`
        (which just skips the update on shutdown if it can't resolve)."""
        password = self.password_field.value
        confirmation = self.confirm_field.value
        if not password and not confirmation and self._saved_password_hash:
            return self._saved_password_hash
        if password and password == confirmation:
            return hash_password(password)
        return None

    def next(self) -> None:
        username = self.username_field.value.strip()
        if not USERNAME_RE.fullmatch(username):
            self.set_error(
                self._validation_label,
                "Username must start with a lowercase letter, contain only "
                "lowercase letters, digits, underscores or hyphens, and be "
                "at most 31 characters.",
            )
            return

        password_hash = self._resolve_password_hash()
        if password_hash is None:
            if not self.password_field.value:
                self.set_error(self._validation_label, "Password is required.")
            else:
                self.set_error(
                    self._validation_label, "Passwords do not match."
                )
            return

        self._pending_options.user = UserConfig(
            username=username,
            password_hash=password_hash,
        )
        self.password_field.clear_secret()
        self.confirm_field.clear_secret()

        if self._pending_options.setup_wlan:
            from rpi_flasher.screens.wlan_details import WlanDetailsScreen

            self.app.push_screen(WlanDetailsScreen(self._pending_options))
            return
        finish_options(self, self._pending_options)

    def store_selection(self) -> None:
        username = self.username_field.value.strip()
        if not USERNAME_RE.fullmatch(username):
            return
        password_hash = self._resolve_password_hash()
        if password_hash is None:
            return
        self._pending_options.user = UserConfig(username, password_hash)
        self.app.state.options = self._pending_options
        self.password_field.clear_secret()
        self.confirm_field.clear_secret()
