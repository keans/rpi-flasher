"""Second wizard screen: pick a Pi model, then narrow to compatible images."""

from __future__ import annotations

import asyncio
import threading

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, images
from rpi_flasher.images import ImageListError
from rpi_flasher.screens._listbox import build_listbox
from rpi_flasher.screens._widgets import make_list_container
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import ImageEntry, narrow_or_advance, wizard_state
from rpi_flasher.theme import make_step_label
from rpi_flasher.utils import STEP_DEVICE


class DeviceSelectScreen(Screen):
    def __init__(self) -> None:
        self._entries: list[ImageEntry] = []
        self._devices: list[str] = []
        self._status_label = ptg.Label(
            "Choose the Raspberry Pi that will use this card."
        )
        self._list_container = make_list_container()
        self._load_generation = 0

    def build(self) -> ptg.Window:
        window = ptg.Window(
            make_step_label(STEP_DEVICE),
            ptg.Label(""),
            self._status_label,
            ptg.Label(""),
            self._list_container,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind("r", lambda *_: self.load(), "Retry")
        return window

    def on_mount(self) -> None:
        self.load()

    def load(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self._status_label.value = "Fetching available operating systems..."
        self._list_container.set_widgets([])
        self._load_thread = threading.Thread(
            target=self._fetch, args=(generation,), daemon=True
        )
        self._load_thread.start()

    def _fetch(self, generation: int) -> None:
        try:
            entries, message = asyncio.run(images.fetch_entries())
        except ImageListError as exc:
            error = str(exc)
            self.app.call_from_thread(
                lambda: self._finish_load(
                    [], "", error=error, generation=generation
                )
            )
            return

        self.app.call_from_thread(
            lambda: self._finish_load(
                entries, message, error=None, generation=generation
            )
        )

    def _finish_load(
        self,
        entries: list[ImageEntry],
        message: str,
        *,
        error: str | None,
        generation: int | None = None,
    ) -> None:
        if generation is not None and generation != self._load_generation:
            return
        if error is not None:
            self._entries = []
            self._devices = []
            self._status_label.value = ptg.escape_markup(
                f"Failed to fetch OS list: {error}. Press 'r' to retry."
            )
            return

        self._entries = entries
        self._devices = images.unique_devices(self._entries)
        if not self._devices:
            self._status_label.value = (
                "The OS list contains no supported Pi models. Press 'r' "
                "to fetch it again."
            )
            self._list_container.set_widgets([])
            return

        self._status_label.value = ptg.escape_markup(message)
        self._list_container.set_widgets(
            build_listbox(self._devices, self.select_device)
        )
        preferred = self.app.saved_selections.device
        index = self.preferred_index(self._devices, preferred)
        if self.window is not None:
            self.window.select(index)

    def store_selection(self) -> None:
        selected = self.selected_item(self._devices)
        if selected is not None:
            wizard_state(self).device = selected

    def select_device(self, index: int) -> None:
        if not (0 <= index < len(self._devices)):
            return
        device = self._devices[index]
        wizard_state(self).device = device
        matching = [
            e for e in self._entries if images.matches_device(e, device)
        ]

        from rpi_flasher.screens.os_select import OsSelectScreen

        narrow_or_advance(self, matching, OsSelectScreen)
