"""Common base class shared by every wizard screen.

PyTermGUI has no Textual-style Screen stack, so `RpiFlasherApp` (in
app.py) implements a small stack of its own: each entry is one of these
`Screen` objects, holding the `pytermgui.Window` it built plus an
optional result callback for modal-style screens.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytermgui as ptg

if TYPE_CHECKING:
    from rpi_flasher.app import RpiFlasherApp


def set_button_disabled(
    button: ptg.Button,
    disabled: bool,
    *,
    handler: Callable[[ptg.Button], Any],
    disabled_label: str,
    enabled_label: str,
) -> None:
    """Toggle a button between clickable and inert, keeping its label and
    click handler consistent with that state.

    PyTermGUI's `Button` has no built-in disabled visual/behavioral
    state (unlike Textual's), so every screen that needed one had
    invented its own variant of "swap the label, neutralize onclick" --
    this is the one shared place doing it now. `onclick=None` is safe:
    `Button.handle_mouse`/`handle_key` both no-op when it's unset.
    """
    button.disabled = disabled
    button.label = disabled_label if disabled else enabled_label
    button.onclick = None if disabled else handler


class Screen:
    """Base for a single wizard step.

    Subclasses implement `build()` to construct the window (called once,
    the first time the screen is shown) and may override `on_mount()` for
    any setup that needs to run right after that first build (e.g.
    kicking off a background fetch).
    """

    app: RpiFlasherApp
    window: ptg.Window | None = None
    result_callback: Callable[[Any], None] | None = None
    modal: bool = False
    resume_selection: int | None = None
    """Selectable index to restore when this screen is revealed again.

    Screens do not need to manage this themselves; ``RpiFlasherApp`` records
    the active window selection before pushing another screen and restores it
    after a pop.  Keeping it on the screen also survives modal dialogs.
    """
    """Set True on small floating dialogs so the
    app centers them instead of stretching them to fill the terminal like
    a regular full-page wizard screen."""

    blocks_quit_shortcut: bool = False
    """Set True on screens with free-text input (e.g. WlanDetailsScreen)
    so the app suspends the global 'q'-quits-anywhere shortcut while
    they're showing -- otherwise typing a literal 'q' into a SSID or
    password field would quit the app instead of typing the letter."""

    def build(self) -> ptg.Window:
        raise NotImplementedError

    def on_mount(self) -> None:
        """Called once, right after `build()`. Override as needed."""

    def on_escape(self) -> None:
        """Called when Escape is pressed while this screen is showing.

        Defaults to going back a step. Override to change or block that
        (e.g. `FlashProgressScreen` ignores it entirely while a flash is still
        in progress, since back-navigation there is deliberately not
        offered mid-write).
        """
        self.app.pop_screen()

    def on_interrupt(self) -> None:
        """Terminate cleanly on Ctrl+C; destructive screens may override."""
        self.app.exit()

    def store_selection(self) -> None:
        """Copy this screen's highlighted choice into shared wizard state."""

    def set_error(self, label: ptg.Label, message: str) -> None:
        """Show a validation error in `label`, formatted consistently.

        Shared by every free-text "details" screen (WLAN, user
        provisioning) so the error markup/escaping lives in one place
        instead of being copy-pasted per screen. Callers still keep
        their own `self._validation_error` (used directly by tests) --
        this only owns the label's rendered value.
        """
        self._validation_error = message
        label.value = f"[error bold]{ptg.escape_markup(message)}[/]"

    def select_first(self) -> None:
        """Highlight the first selectable widget, if any.

        PyTermGUI does not focus anything by default -- list screens call
        this after populating their list (on mount, and again after any
        re-render, e.g. a background fetch finishing) so a default choice
        is visible immediately instead of requiring a keypress first.
        """
        if self.window is not None and self.window.selectables:
            self.window.select(0)

    def select_widget(self, target: ptg.Widget) -> None:
        """Move focus to a specific selectable widget in this screen."""
        if self.window is None:
            return
        for index, (widget, _) in enumerate(self.window.selectables):
            if widget is target:
                self.window.select(index)
                return

    def start_polling(
        self, tick: Callable[[], bool], interval: float = 0.2
    ) -> None:
        """Call `tick` repeatedly on a timer until it returns False.

        PyTermGUI has no worker/message-passing model like Textual's, so
        this self-rescheduling timer is the shared way any screen that
        runs work on a background thread (fetching the OS list, running
        the flash pipeline) gets a periodic redraw tick on the main
        thread to pick up that thread's progress.
        """

        generation = getattr(self, "_poll_generation", 0) + 1
        self._poll_generation = generation

        def run() -> None:
            if generation != self._poll_generation:
                return
            if tick():
                self.app.manager.call_later(interval, run)

        self.app.call_from_thread(run)

    def preferred_index(
        self,
        items: list[Any],
        preferred: Any,
        *,
        key: Callable[[Any], Any] | None = None,
    ) -> int:
        """Return a safe index for a remembered list choice."""
        if key is None:
            key = lambda item: item
        return next(
            (
                index
                for index, item in enumerate(items)
                if key(item) == preferred
            ),
            0,
        )

    def selected_item(self, items: list[Any]) -> Any | None:
        """Return the highlighted item, or None when the list has no choice."""
        if self.window is None or self.window.selected_index is None:
            return None
        index = self.window.selected_index
        return items[index] if 0 <= index < len(items) else None
