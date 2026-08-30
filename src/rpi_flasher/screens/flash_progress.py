"""Final screen: runs the flash pipeline in a worker thread with live progress."""

from __future__ import annotations

import threading
import time
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, ProgressBar, Static

from rpi_flasher.flasher import FlashError, FlashProgress, flash
from rpi_flasher.state import wizard_state
from rpi_flasher.utils import human_bytes


class FlashPhaseMessage(Message):
    def __init__(self, progress: FlashProgress) -> None:
        self.progress = progress
        super().__init__()


class FlashDone(Message):
    pass


class FlashFailed(Message):
    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__()


class FlashProgressScreen(Screen):
    """Runs the flash pipeline in a worker thread; back-navigation is
    intentionally not bound here since the operation is destructive."""

    BINDINGS: ClassVar = [("c", "cancel", "Cancel")]

    def __init__(self) -> None:
        super().__init__()
        self._cancel_event = threading.Event()
        self._rate_phase: str | None = None
        self._rate_time = 0.0
        self._rate_bytes = 0
        self._smoothed_rate = 0.0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Flashing...", id="phase-label"),
            ProgressBar(id="progress-bar", total=100),
            Static("", id="speed"),
            Static("", id="result"),
            Button("Cancel", id="cancel-button", variant="warning"),
            Button("Quit", id="quit-button", disabled=True),
            id="flash-progress-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run_flash, thread=True, exclusive=True)

    def _run_flash(self) -> None:
        def progress_cb(progress: FlashProgress) -> None:
            self.post_message(FlashPhaseMessage(progress))

        try:
            flash(wizard_state(self), progress_cb, self._cancel_event)
        except FlashError as exc:
            # FlashCancelled is a FlashError subclass; its message already
            # explains whether the card is still safe to use.
            self.post_message(FlashFailed(str(exc)))
            return
        self.post_message(FlashDone())

    def _speed_text(self, progress: FlashProgress) -> str:
        now = time.monotonic()
        if progress.phase != self._rate_phase:
            self._rate_phase = progress.phase
            self._rate_time = now
            self._rate_bytes = progress.current
            self._smoothed_rate = 0.0
            return ""

        elapsed = now - self._rate_time
        if elapsed <= 0:
            return ""
        instantaneous = (progress.current - self._rate_bytes) / elapsed
        # Light smoothing so the readout doesn't jitter chunk to chunk.
        self._smoothed_rate = (
            instantaneous
            if self._smoothed_rate == 0.0
            else (0.3 * instantaneous + 0.7 * self._smoothed_rate)
        )
        self._rate_time = now
        self._rate_bytes = progress.current

        if self._smoothed_rate <= 0:
            return ""
        remaining = progress.total - progress.current
        eta_seconds = int(remaining / self._smoothed_rate)
        minutes, seconds = divmod(max(eta_seconds, 0), 60)
        return f"{human_bytes(int(self._smoothed_rate))}/s, ETA {minutes:02d}:{seconds:02d}"

    def on_flash_phase_message(self, message: FlashPhaseMessage) -> None:
        label = self.query_one("#phase-label", Static)
        bar = self.query_one("#progress-bar", ProgressBar)
        speed = self.query_one("#speed", Static)
        p = message.progress
        label.update(f"{p.phase}...")
        if p.total > 0:
            bar.update(total=p.total, progress=p.current)
            speed.update(self._speed_text(p))
        else:
            speed.update("")

        cancel_button = self.query_one("#cancel-button", Button)
        cancel_button.disabled = not p.cancellable

    def on_flash_done(self, message: FlashDone) -> None:
        self.query_one("#phase-label", Static).update("Done")
        self.query_one("#speed", Static).update("")
        self.query_one("#result", Static).update(
            "Flash complete -- you can now remove the SD card."
        )
        self.query_one("#cancel-button", Button).disabled = True
        self.query_one("#quit-button", Button).disabled = False

    def on_flash_failed(self, message: FlashFailed) -> None:
        self.query_one("#phase-label", Static).update("Error")
        self.query_one("#speed", Static).update("")
        self.query_one("#result", Static).update(message.error)
        self.query_one("#cancel-button", Button).disabled = True
        self.query_one("#quit-button", Button).disabled = False

    def action_cancel(self) -> None:
        cancel_button = self.query_one("#cancel-button", Button)
        if cancel_button.disabled:
            return
        self._cancel_event.set()
        cancel_button.disabled = True
        cancel_button.label = "Cancelling..."

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-button":
            self.app.exit()
        elif event.button.id == "cancel-button":
            self.action_cancel()
