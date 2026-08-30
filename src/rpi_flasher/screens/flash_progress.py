"""Final screen: runs the flash pipeline in a background thread, and
polls its shared state on the WindowManager's periodic layout tick to
render progress -- PyTermGUI has no worker/message-passing model like
Textual's, so the background thread only ever mutates plain attributes
on this screen; the main loop is the only thing that touches widgets."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE
from rpi_flasher.flasher import FlashError, FlashProgress, flash
from rpi_flasher.screens._widgets import make_action_button, make_action_row
from rpi_flasher.screens.base import Screen, set_button_disabled
from rpi_flasher.state import wizard_state
from rpi_flasher.theme import make_step_label
from rpi_flasher.utils import STEP_FLASHING, human_bytes

logger = logging.getLogger(__name__)

POLL_INTERVAL = 0.2
RATE_WINDOW_SECONDS = 8.0
RATE_WINDOW_SAMPLES = 30


class FlashProgressScreen(Screen):
    """Runs the flash pipeline; back-navigation is intentionally not
    offered here since the operation is destructive."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._latest: FlashProgress | None = None
        self._done = False
        self._error: str | None = None
        self._rate_phase: str | None = None
        self._rate_samples: deque[tuple[float, int]] = deque(
            maxlen=RATE_WINDOW_SAMPLES
        )
        self._warnings: list[str] = []
        self._exit_when_finished = False

    def build(self) -> ptg.Window:
        self._phase_label = ptg.Label("Flashing...")
        self._bar_label = ptg.Label("")
        self._speed_label = ptg.Label("")
        self._result_label = ptg.Label("")
        self.cancel_button = make_action_button(
            "Cancel", onclick=lambda _: self.cancel()
        )
        self.retry_button = make_action_button(
            "Retry", onclick=lambda _: self.retry()
        )
        self.quit_button = make_action_button(
            "Quit", onclick=lambda _: self.app.exit()
        )
        self._buttons_row = make_action_row(self.cancel_button)
        set_button_disabled(
            self.cancel_button,
            True,
            handler=self.cancel,
            disabled_label="Cancel",
            enabled_label="Cancel",
        )

        window = ptg.Window(
            make_step_label(STEP_FLASHING),
            ptg.Label(""),
            self._phase_label,
            self._bar_label,
            self._speed_label,
            self._result_label,
            ptg.Label(""),
            self._buttons_row,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind(
            ptg.keys.TAB,
            lambda *_: self.focus_next_action(),
            "Next action",
        )
        return window

    def on_mount(self) -> None:
        self._start_flash_thread()
        self.start_polling(self._render, POLL_INTERVAL)

    def on_escape(self) -> None:
        # The destructive final step never permits backward navigation.
        return

    def on_interrupt(self) -> None:
        """Exit after cancelling safely, or after an active write finishes."""
        with self._lock:
            progress = self._latest
            finished = self._done or self._error is not None

        if finished:
            self.app.exit()
            return

        self._exit_when_finished = True
        if (
            progress is None
            or progress.cancellable
            or progress.phase == "Unmounting"
        ):
            self.cancel()
            trigger = ptg.escape_markup(self.app.shutdown_trigger)
            self._result_label.value = (
                f"[warning]{trigger} requested — cancelling safely before "
                "exit...[/]"
            )
            return

        trigger = ptg.escape_markup(self.app.shutdown_trigger)
        self._result_label.value = (
            f"[warning]{trigger} requested — the current disk operation cannot "
            "be interrupted safely. The app will exit when it finishes.[/]"
        )

    def focus_next_action(self) -> None:
        """Cycle focus through the buttons currently shown below progress."""
        if self.window is None:
            return
        actions = [widget for widget, _ in self._buttons_row.selectables]
        if not actions:
            return
        selected = self.window.selected
        try:
            next_index = (actions.index(selected) + 1) % len(actions)
        except ValueError:
            next_index = 0
        self.select_widget(actions[next_index])

    def _start_flash_thread(self) -> None:
        threading.Thread(target=self._run_flash, daemon=True).start()

    def _run_flash(self) -> None:
        def progress_cb(progress: FlashProgress) -> None:
            with self._lock:
                self._latest = progress
                if progress.warning:
                    self._warnings.append(progress.phase)

        try:
            flash(wizard_state(self), progress_cb, self._cancel_event)
        except FlashError as exc:
            # FlashCancelled is a FlashError subclass; its message already
            # explains whether the card is still safe to use.
            with self._lock:
                self._error = str(exc)
            return
        except Exception:
            logger.exception("Unexpected failure in flash worker")
            with self._lock:
                self._error = (
                    "An unexpected error stopped the flash. The SD card may "
                    "need to be reflashed; see the log for details."
                )
            return
        with self._lock:
            self._done = True

    def _speed_text(self, progress: FlashProgress) -> str:
        now = time.monotonic()
        if progress.phase != self._rate_phase:
            self._rate_phase = progress.phase
            self._rate_samples.clear()
            self._rate_samples.append((now, progress.current))
            return ""

        # The UI redraws more frequently than some backends report bytes.
        # Duplicate byte counts are redraws, not zero-speed measurements.
        if self._rate_samples[-1][1] != progress.current:
            self._rate_samples.append((now, progress.current))

        while (
            len(self._rate_samples) > 2
            and now - self._rate_samples[0][0] > RATE_WINDOW_SECONDS
        ):
            self._rate_samples.popleft()

        if len(self._rate_samples) < 2:
            return ""

        first_time, first_bytes = self._rate_samples[0]
        last_time, last_bytes = self._rate_samples[-1]
        elapsed = last_time - first_time
        transferred = last_bytes - first_bytes
        if elapsed <= 0 or transferred <= 0:
            return ""
        rate = transferred / elapsed

        remaining = progress.total - progress.current
        eta_seconds = int(remaining / rate)
        minutes, seconds = divmod(max(eta_seconds, 0), 60)
        return f"{human_bytes(int(rate))}/s, ETA {minutes:02d}:{seconds:02d}"

    def _render(self) -> bool:
        """Update widgets from the latest state; return whether polling
        should continue (False once the flash has finished or failed)."""
        with self._lock:
            progress = self._latest
            done = self._done
            error = self._error
            warnings = list(self._warnings)

        if progress is not None:
            # Writing to the raw device is the point of no return. Keep it red
            # to distinguish cancellation that requires reflashing from a safe
            # pre-write cancellation.
            color = "error" if progress.phase == "Writing" else "success"
            self._phase_label.value = ptg.escape_markup(f"{progress.phase}...")
            if progress.total > 0:
                filled = int(30 * progress.current / progress.total)
                bar = "█" * filled + "░" * (30 - filled)
                pct = 100 * progress.current // progress.total
                self._bar_label.value = f"[{color}]{bar}[/] {pct}%"
                self._speed_label.value = self._speed_text(progress)
            else:
                self._bar_label.value = f"[{color}]working...[/]"
                self._speed_label.value = ""
            set_button_disabled(
                self.cancel_button,
                not progress.cancellable,
                handler=self.cancel,
                disabled_label="Cancel",
                enabled_label="Cancel",
            )

        if done:
            self._phase_label.value = "Done"
            self._speed_label.value = ""
            result = "Flash complete -- you can now remove the SD card."
            if warnings:
                result += "\n\nWarnings:\n- " + "\n- ".join(warnings)
            self._result_label.value = (
                f"[success]{ptg.escape_markup(result)}[/]"
            )
            self._buttons_row.set_widgets([self.quit_button])
            if self._exit_when_finished:
                self.app.exit()
            return False

        if error is not None:
            self._phase_label.value = "Error"
            self._speed_label.value = ""
            self._result_label.value = f"[error]{ptg.escape_markup(error)}[/]"
            self._buttons_row.set_widgets(
                [self.retry_button, self.quit_button]
            )
            if self._exit_when_finished:
                self.app.exit()
            return False

        return True

    def cancel(self, *_: object) -> None:
        self._cancel_event.set()
        self.cancel_button.label = "Cancelling..."
        self.cancel_button.onclick = None

    def retry(self) -> None:
        self._cancel_event = threading.Event()
        self._warnings.clear()
        self._rate_phase = None
        self._rate_samples.clear()
        self._done = False
        self._error = None
        self._latest = None
        self._exit_when_finished = False
        self._phase_label.value = "Flashing..."
        self._result_label.value = ""
        self._bar_label.value = ""
        set_button_disabled(
            self.cancel_button,
            False,
            handler=self.cancel,
            disabled_label="Cancel",
            enabled_label="Cancel",
        )
        self._buttons_row.set_widgets([self.cancel_button])
        self._start_flash_thread()
        self.start_polling(self._render, POLL_INTERVAL)
