"""Textual App wiring and CLI entry point."""

from __future__ import annotations

import shutil
import sys
from typing import ClassVar

from textual.app import App

from rpi_flasher import privilege
from rpi_flasher.screens.disk_select import DiskSelectScreen
from rpi_flasher.state import WizardState


class RpiFlasherApp(App):
    """Wizard: select SD card -> select image -> options -> confirm -> flash."""

    CSS_PATH = "app.tcss"
    TITLE = "Raspberry Pi Flasher"
    SUB_TITLE = "Safe, keyboard-driven SD card imaging"
    # Global quit shortcut, available on every screen; input widgets consume
    # "q" as text while focused, so this doesn't interfere with typing.
    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.state = WizardState()

    def on_mount(self) -> None:
        self.push_screen(DiskSelectScreen())


def main() -> None:
    if shutil.which("diskutil") is None:
        print(
            "error: 'diskutil' was not found on PATH. rpi-flasher only "
            "runs on macOS, where diskutil ships with the system.",
            file=sys.stderr,
        )
        sys.exit(1)
    privilege.ensure_root()
    RpiFlasherApp().run()


if __name__ == "__main__":
    main()
