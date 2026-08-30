"""Modal confirmation dialog for the final, destructive flash decision --
kept separate from the Overview screen so the yes/no choice is always a
small, fully on-screen popup rather than something that can scroll off
the bottom of a long details page."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmFlashDialog(ModalScreen[bool]):
    """Dismisses with True if the user confirmed, False otherwise."""

    BINDINGS: ClassVar = [
        ("escape", "dismiss_no", "Cancel"),
        ("left", "focus_no", "Select No"),
        ("right", "focus_yes", "Select Yes"),
    ]

    def __init__(self, device_node: str) -> None:
        super().__init__()
        self._device_node = device_node

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                f"This will ERASE all data on {self._device_node}. Proceed?",
                id="dialog-prompt",
            ),
            Horizontal(
                # Not compact -- this is the one destructive decision in
                # the whole wizard; full-size buttons keep it visually
                # distinct from the compact controls everywhere else.
                Button("No, go back", id="no-button", variant="primary"),
                Button(
                    "Yes, erase and flash", id="yes-button", variant="error"
                ),
                id="dialog-buttons",
            ),
            id="confirm-dialog",
        )

    def on_mount(self) -> None:
        # Deferred so scroll-into-view/layout has settled before focusing,
        # same reasoning as the old Overview screen's default-focus fix.
        self.call_after_refresh(self.query_one("#no-button", Button).focus)

    def action_dismiss_no(self) -> None:
        self.dismiss(False)

    def action_focus_no(self) -> None:
        self.query_one("#no-button", Button).focus()

    def action_focus_yes(self) -> None:
        self.query_one("#yes-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "no-button":
            self.dismiss(False)
        elif event.button.id == "yes-button":
            self.dismiss(True)
