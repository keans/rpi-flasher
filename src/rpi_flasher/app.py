"""PyTermGUI wizard app wiring and CLI entry point.

PyTermGUI has no Textual-style Screen stack/App class, so this module
implements a minimal one: `RpiFlasherApp` owns the shared `WizardState`
and a list of `Screen` objects (see `screens/base.py`), each responsible
for building and tearing down its own `pytermgui.Window` via the shared
`pytermgui.WindowManager`.
"""

from __future__ import annotations

import heapq
import itertools
import shutil
import sys
import time
from collections.abc import Callable
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

import pytermgui as ptg
from pytermgui.input import getch_timeout
from pytermgui.win32console import enable_virtual_processing

from rpi_flasher import WINDOW_TITLE, config, privilege
from rpi_flasher.state import WizardState
from rpi_flasher.theme import configure_theme

if TYPE_CHECKING:
    from rpi_flasher.screens.base import Screen


class RpiFlasherWindowManager(ptg.WindowManager):
    """Window manager with a small main-thread callback queue.

    PyTermGUI's normal input loop blocks indefinitely in ``getch``. Polling
    with a short timeout lets background workers hand UI mutations back to
    this loop instead of touching widgets from worker/timer threads.
    """

    def __init__(self) -> None:
        super().__init__()
        self._ui_callbacks: Queue[Callable[[], None]] = Queue()
        self._scheduled: list[tuple[float, int, Callable[[], None]]] = []
        self._schedule_ids = itertools.count()
        self.interrupt_handler: Callable[[], None] = self.stop

    def call_soon_threadsafe(self, callback: Callable[[], None]) -> None:
        self._ui_callbacks.put(callback)

    def process_pending_callbacks(self) -> None:
        while True:
            try:
                callback = self._ui_callbacks.get_nowait()
            except Empty:
                return
            callback()

    def call_later(self, delay: float, callback: Callable[[], None]) -> None:
        """Schedule a callback on the UI thread without spawning a timer."""

        def schedule() -> None:
            heapq.heappush(
                self._scheduled,
                (time.monotonic() + delay, next(self._schedule_ids), callback),
            )

        self.call_soon_threadsafe(schedule)

    def _process_due_callbacks(self) -> None:
        now = time.monotonic()
        while self._scheduled and self._scheduled[0][0] <= now:
            _, _, callback = heapq.heappop(self._scheduled)
            callback()

    def _run_input_loop(self) -> None:
        with enable_virtual_processing():
            while self._is_running:
                self.process_pending_callbacks()
                self._process_due_callbacks()
                key = getch_timeout(0.05, default="", interrupts=False)
                if not key:
                    continue
                if key == chr(3):
                    self.interrupt_handler()
                    continue
                if self.handle_key(key):
                    continue
                self.process_mouse(key)


class RpiFlasherApp:
    """Wizard: select SD card -> select image -> options -> confirm -> flash."""

    def __init__(self) -> None:
        configure_theme()
        preferences = config.load_preferences()
        self.state = WizardState(options=preferences)
        self.saved_selections = config.load_selections()
        self.remember_wlan = preferences.wlan is not None
        self._interrupted = False
        self.shutdown_trigger = "Quit"
        self.manager = RpiFlasherWindowManager()
        self.manager.interrupt_handler = self.handle_interrupt
        # A bare `WindowManager()` has an empty layout, so `manager.add()`
        # never actually sizes/positions a window -- it's left at its
        # small, shrink-wrapped default instead of filling the terminal.
        # A single full-terminal slot fixes that for every regular wizard
        # screen; modal dialogs (`Screen.modal = True`) opt out and
        # center themselves instead, since they're meant to float small
        # over whatever screen is beneath them.
        self.manager.layout.add_slot("Body")
        self._stack: list[Screen] = []

    @property
    def screen(self) -> Screen:
        """The currently visible screen (top of the navigation stack)."""
        return self._stack[-1]

    def push_screen(
        self,
        screen: Screen,
        callback: Callable[[Any], None] | None = None,
    ) -> None:
        """Show `screen`, on top of whatever is currently showing.

        `callback`, if given, is invoked with the value later passed to
        `pop_screen()` -- the equivalent of Textual's
        `push_screen(screen, callback)` dismiss-result pattern.
        """
        # Focusing the new window causes PyTermGUI to clear the selection in
        # the current one. Remember it first so Escape returns the user to the
        # exact row/control they used to advance, rather than the first item.
        if self._stack and self.screen.window is not None:
            self.screen.resume_selection = self.screen.window.selected_index

        screen.app = self
        screen.result_callback = callback
        self._stack.append(screen)
        self._show(screen)

    def pop_screen(self, result: Any = None) -> None:
        """Close the current screen and reveal the one beneath it."""
        if not self._stack:
            return
        popped = self._stack.pop()
        if popped.window is not None:
            self.manager.remove(popped.window, animate=False)
        if popped.result_callback is not None:
            popped.result_callback(result)
        if self._stack:
            self._show(self._stack[-1])

    def _show(self, screen: Screen) -> None:
        # `WindowManager.add()` never removes other windows, so a screen
        # further down the stack is still sitting in the manager (just
        # not focused) after something is pushed on top of it -- popping
        # back to it only needs to refocus that existing window, not
        # rebuild or re-add it (re-adding would insert a second, stale
        # copy alongside the live one).
        if screen.window is None:
            screen.window = screen.build()
            screen.window.bind(
                ptg.keys.ESC, lambda *_: screen.on_escape(), "Back"
            )
            # `animate=False` on both branches -- the default grow/shrink
            # animation plays out over ~300ms by drawing the window at
            # increasing heights, which for a full-terminal window reads
            # as visible "build up" rather than a clean switch.
            if screen.modal:
                self.manager.add(screen.window, assign=False, animate=False)
                screen.window.center()
            else:
                self.manager.add(screen.window, assign="body", animate=False)
            screen.on_mount()
        else:
            self.manager.focus(screen.window)
            if screen.resume_selection is not None:
                screen.window.select(screen.resume_selection)
        self._sync_quit_binding(screen)

    def _sync_quit_binding(self, screen: Screen) -> None:
        # `WindowManager.execute_binding` always treats a bound key as
        # "handled" once it's bound at all, regardless of what the
        # callback does -- so 'q' can't be bound unconditionally and
        # made to fall through to a focused text field on a per-keypress
        # basis. Instead, bind/unbind it wholesale as the active screen
        # changes.
        if screen.blocks_quit_shortcut:
            try:
                self.manager.unbind("q")
            except KeyError:
                pass
        else:
            self.manager.bind("q", lambda *_: self.request_shutdown(), "Quit")

    def request_shutdown(self, *, interrupted: bool = False) -> None:
        """Ask the active screen to stop using its safe shutdown policy."""
        self._interrupted = self._interrupted or interrupted
        self.shutdown_trigger = "Ctrl+C" if interrupted else "Quit"
        if not self._stack:
            self.exit()
            return
        self.screen.on_interrupt()

    def exit(self) -> None:
        try:
            for screen in self._stack:
                screen.store_selection()
            saves = (
                (
                    "settings",
                    lambda: config.save_preferences(
                        self.state.options, remember_wlan=self.remember_wlan
                    ),
                ),
                ("selections", lambda: config.save_selections(self.state)),
            )
            for label, save in saves:
                try:
                    save()
                except (OSError, TypeError, ValueError) as exc:
                    print(
                        f"warning: could not save {label}: {exc}",
                        file=sys.stderr,
                    )
        finally:
            self.manager.stop()

    def handle_interrupt(self) -> None:
        """Handle Ctrl+C through the active screen's safe shutdown policy."""
        self.request_shutdown(interrupted=True)

    def call_from_thread(self, callback: Callable[[], None]) -> None:
        """Schedule a widget update on the WindowManager input thread."""
        self.manager.call_soon_threadsafe(callback)

    def run(self) -> None:
        from rpi_flasher.screens.disk_select import DiskSelectScreen

        with self.manager as manager:
            self.push_screen(DiskSelectScreen())
            manager.run()
        if self._interrupted:
            self.show_interrupt_hint()

    def show_interrupt_hint(self) -> None:
        """Confirm graceful Ctrl+C handling after the terminal is restored."""
        print(
            "rpi-flasher was interrupted with Ctrl+C. "
            "Your selections were saved.",
            file=sys.stderr,
        )


def main() -> None:
    if "--version" in sys.argv[1:] or "-V" in sys.argv[1:]:
        print(WINDOW_TITLE)
        return
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
