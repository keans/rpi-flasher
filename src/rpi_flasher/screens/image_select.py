"""Fourth wizard screen: pick an image from the ones compatible with the
chosen Pi model and OS family -- already a short list by this point, so
it's a plain pick-from-a-list screen rather than a searchable one."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, images
from rpi_flasher.screens._listbox import build_listbox
from rpi_flasher.screens._widgets import make_list_container
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import ImageEntry, wizard_state
from rpi_flasher.theme import make_step_label
from rpi_flasher.utils import STEP_IMAGE, human_bytes


class ImageSelectScreen(Screen):
    def __init__(self, entries: list[ImageEntry]) -> None:
        self._entries = entries
        self._status = self._cache_usage_message()
        self._status_label = ptg.Label(self._status)
        self._list_container = make_list_container()

    def build(self) -> ptg.Window:
        self._render()
        window = ptg.Window(
            make_step_label(STEP_IMAGE),
            ptg.Label(""),
            self._status_label,
            ptg.Label(""),
            self._list_container,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind("d", lambda *_: self.delete_selected(), "Delete cache")
        return window

    def on_mount(self) -> None:
        preferred = self.app.saved_selections.image_id
        index = self.preferred_index(
            self._entries,
            preferred,
            key=lambda entry: entry.extract_sha256 or entry.url,
        )
        if self.window is not None and self._entries:
            self.window.select(index)

    def store_selection(self) -> None:
        selected = self.selected_item(self._entries)
        if selected is not None:
            wizard_state(self).image = selected

    def _render(self) -> None:
        labels = [
            images.display_label(entry, cached=images.is_cached(entry))
            for entry in self._entries
        ]
        self._list_container.set_widgets(
            build_listbox(labels, self.select_image)
        )
        self.select_first()

    def _cache_usage_message(self) -> str:
        size = images.cache_size_bytes()
        if not size:
            return ""
        return (
            f"Cached images use {human_bytes(size)} on disk. "
            "Highlight an entry and press 'd' to delete its cache."
        )

    def select_image(self, index: int) -> None:
        if not (0 <= index < len(self._entries)):
            return
        wizard_state(self).image = self._entries[index]

        from rpi_flasher.screens.options import OptionsScreen

        self.app.push_screen(OptionsScreen())

    def delete_cached(self, index: int) -> None:
        if not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        if not images.is_cached(entry):
            return
        images.delete_cached(entry)

        self._render()
        self._status = f"Deleted cached copy of {entry.name}."
        self._status_label.value = ptg.escape_markup(self._status)

    def delete_selected(self) -> None:
        if self.window is None or self.window.selected_index is None:
            return
        self.delete_cached(self.window.selected_index)
