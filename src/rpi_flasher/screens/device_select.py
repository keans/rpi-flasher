"""Second wizard screen: pick a Pi model, then narrow to compatible images."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from rpi_flasher import images
from rpi_flasher.images import ImageListError
from rpi_flasher.state import ImageEntry, narrow_or_advance
from rpi_flasher.utils import STEP_DEVICE, step_title


class DeviceSelectScreen(Screen):
    BINDINGS: ClassVar = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "rescan", "Retry"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[ImageEntry] = []
        self._devices: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_DEVICE), id="title"),
            Static(
                "Choose the Raspberry Pi that will use this card.",
                classes="hint",
            ),
            Static("", id="status"),
            OptionList(id="device-list"),
            id="device-select-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        status = self.query_one("#status", Static)
        option_list = self.query_one("#device-list", OptionList)
        option_list.display = False
        status.update("Fetching available operating systems...")
        try:
            self._entries, message = await images.fetch_entries()
        except ImageListError as exc:
            status.update(
                f"Failed to fetch OS list: {exc}. Press 'r' to retry."
            )
            return

        self._devices = images.unique_devices(self._entries)
        option_list.clear_options()
        if not self._devices:
            status.update(
                "The OS list contains no supported Pi models. Press 'r' "
                "to fetch it again."
            )
            return
        for device in self._devices:
            option_list.add_option(Option(device))
        option_list.display = True
        option_list.highlighted = 0
        option_list.focus()
        status.update(message)

    def action_rescan(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        index = event.option_index
        if index is None or not (0 <= index < len(self._devices)):
            return
        device = self._devices[index]
        matching = [
            e for e in self._entries if images.matches_device(e, device)
        ]

        from rpi_flasher.screens.os_select import OsSelectScreen

        narrow_or_advance(self, matching, OsSelectScreen)
