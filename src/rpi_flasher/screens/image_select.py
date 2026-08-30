"""Third wizard screen: pick an image from the ones compatible with the
chosen Pi model and OS family -- already a short list by this point, so
it's a plain pick-from-a-list screen rather than a searchable one."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from rpi_flasher import images
from rpi_flasher.state import ImageEntry, wizard_state
from rpi_flasher.utils import STEP_IMAGE, human_bytes, step_title


class ImageSelectScreen(Screen):
    BINDINGS: ClassVar = [
        ("escape", "app.pop_screen", "Back"),
        ("d", "delete_cached", "Delete cached copy"),
    ]

    def __init__(self, entries: list[ImageEntry]) -> None:
        super().__init__()
        self._entries = entries

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_IMAGE), id="title"),
            Static(self._cache_usage_message(), id="status"),
            OptionList(id="image-list"),
            Static("", id="detail"),
            id="image-select-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_options()
        option_list = self.query_one("#image-list", OptionList)
        option_list.highlighted = 0
        option_list.focus()

    def _refresh_options(self) -> None:
        option_list = self.query_one("#image-list", OptionList)
        option_list.clear_options()
        for entry in self._entries:
            label = images.display_label(entry, cached=images.is_cached(entry))
            option_list.add_option(Option(label))

    def _cache_usage_message(self) -> str:
        size = images.cache_size_bytes()
        if not size:
            return ""
        return (
            f"Cached images use {human_bytes(size)} on disk. "
            "Highlight an entry and press 'd' to delete its cache."
        )

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        index = event.option_index
        detail = self.query_one("#detail", Static)
        if index is None or not (0 <= index < len(self._entries)):
            detail.update("")
            return
        detail.update(self._entries[index].description)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        index = event.option_index
        if 0 <= index < len(self._entries):
            wizard_state(self).image = self._entries[index]
            from rpi_flasher.screens.options import OptionsScreen

            self.app.push_screen(OptionsScreen())

    def action_delete_cached(self) -> None:
        option_list = self.query_one("#image-list", OptionList)
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        if not images.is_cached(entry):
            return
        images.delete_cached(entry)

        self._refresh_options()
        option_list.highlighted = index
        self.query_one("#status", Static).update(
            f"Deleted cached copy of {entry.name}."
        )
