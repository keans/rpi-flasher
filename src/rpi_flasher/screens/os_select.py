"""Third wizard screen: pick an OS family, then narrow to compatible images."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from rpi_flasher import images
from rpi_flasher.state import ImageEntry, narrow_or_advance
from rpi_flasher.utils import STEP_OS, step_title


class OsSelectScreen(Screen):
    BINDINGS: ClassVar = [("escape", "app.pop_screen", "Back")]

    def __init__(self, entries: list[ImageEntry]) -> None:
        super().__init__()
        self._entries = entries
        self._categories = images.unique_categories(entries)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_OS), id="title"),
            Static("Choose an operating system family.", classes="hint"),
            OptionList(*(Option(c) for c in self._categories), id="os-list"),
            id="os-select-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        option_list = self.query_one("#os-list", OptionList)
        option_list.highlighted = 0
        option_list.focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        index = event.option_index
        if index is None or not (0 <= index < len(self._categories)):
            return
        category = self._categories[index]
        matching = [
            e for e in self._entries if images.os_category(e) == category
        ]

        from rpi_flasher.screens.image_select import ImageSelectScreen

        narrow_or_advance(self, matching, ImageSelectScreen)
