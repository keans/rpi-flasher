"""Third wizard screen: pick an OS family, then narrow to compatible images."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, images
from rpi_flasher.screens._listbox import build_listbox
from rpi_flasher.screens._widgets import make_list_container
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import ImageEntry, narrow_or_advance, wizard_state
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_OS


class OsSelectScreen(Screen):
    def __init__(self, entries: list[ImageEntry]) -> None:
        self._entries = entries
        self._categories = images.unique_categories(entries)
        self._list_container = make_list_container()

    def build(self) -> ptg.Window:
        self._list_container.set_widgets(
            build_listbox(self._categories, self.select_category)
        )
        window = ptg.Window(
            make_step_label(STEP_OS),
            ptg.Label(""),
            make_hint_label("Choose an operating system family."),
            ptg.Label(""),
            self._list_container,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        return window

    def on_mount(self) -> None:
        preferred = self.app.saved_selections.os_category
        index = self.preferred_index(self._categories, preferred)
        if self.window is not None and self._categories:
            self.window.select(index)

    def store_selection(self) -> None:
        selected = self.selected_item(self._categories)
        if selected is not None:
            wizard_state(self).os_category = selected

    def select_category(self, index: int) -> None:
        if not (0 <= index < len(self._categories)):
            return
        category = self._categories[index]
        wizard_state(self).os_category = category
        matching = [
            e for e in self._entries if images.os_category(e) == category
        ]

        from rpi_flasher.screens.image_select import ImageSelectScreen

        narrow_or_advance(self, matching, ImageSelectScreen)
