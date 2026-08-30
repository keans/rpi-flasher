"""Second wizard screen: browse/search the RPi OS feed, cached or not."""

from __future__ import annotations

import asyncio
from typing import ClassVar

import httpx
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from rpi_flasher import images
from rpi_flasher.state import ImageEntry, wizard_state
from rpi_flasher.utils import human_bytes


class ImageSelectScreen(Screen):
    BINDINGS: ClassVar = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "rescan", "Retry"),
        ("d", "delete_cached", "Delete cached copy"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # (entry, precomputed label) pairs -- cache-status is stat'd once
        # per load/rescan (or targeted delete) rather than on every
        # filter keystroke.
        self._entries: list[tuple[ImageEntry, str]] = []
        self._filtered: list[ImageEntry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Select an OS image to flash", id="title"),
            Static("", id="status"),
            Input(
                placeholder="Type to filter (name, category, device)...",
                id="filter",
            ),
            OptionList(id="image-list"),
            Static("", id="detail"),
            id="image-select-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        status = self.query_one("#status", Static)
        status_text = ""
        try:
            data = await images.fetch_os_list()
        except httpx.HTTPError as exc:
            snapshot = await asyncio.to_thread(images.load_snapshot)
            if snapshot is not None:
                status_text = (
                    f"Live fetch failed ({exc}); showing last cached list."
                )
                data = snapshot
            else:
                status.update(
                    f"Failed to fetch OS list: {exc}. Press 'r' to retry."
                )
                return

        entries = images.flatten_os_list(data.get("os_list", []))
        self._relabel_all(entries)
        self._apply_filter(self.query_one("#filter", Input).value)
        status.update(status_text or self._cache_usage_message())

    def _relabel_all(self, entries: list[ImageEntry]) -> None:
        self._entries = [
            (e, images.display_label(e, cached=images.is_cached(e)))
            for e in entries
        ]

    def _cache_usage_message(self) -> str:
        size = images.cache_size_bytes()
        if not size:
            return ""
        return (
            f"Cached images use {human_bytes(size)} on disk. "
            "Highlight an entry and press 'd' to delete its cache."
        )

    def _apply_filter(self, query: str) -> None:
        matches = [
            (e, label)
            for e, label in self._entries
            if images.matches_query(e, query)
        ]

        self._filtered = [e for e, _ in matches]
        option_list = self.query_one("#image-list", OptionList)
        option_list.clear_options()
        for _, label in matches:
            option_list.add_option(Option(label))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter":
            self._apply_filter(event.value)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        index = event.option_index
        detail = self.query_one("#detail", Static)
        if index is None or not (0 <= index < len(self._filtered)):
            detail.update("")
            return
        entry = self._filtered[index]
        parts = [entry.description] if entry.description else []
        if entry.devices:
            parts.append(f"Devices: {', '.join(entry.devices)}")
        if entry.release_date:
            parts.append(f"Released: {entry.release_date}")
        detail.update(" | ".join(parts))

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        index = event.option_index
        if 0 <= index < len(self._filtered):
            wizard_state(self).image = self._filtered[index]
            from rpi_flasher.screens.options import OptionsScreen

            self.app.push_screen(OptionsScreen())

    def action_rescan(self) -> None:
        self.run_worker(self._load(), exclusive=True)

    def action_delete_cached(self) -> None:
        option_list = self.query_one("#image-list", OptionList)
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self._filtered)):
            return
        entry = self._filtered[index]
        if not images.is_cached(entry):
            return
        images.delete_cached(entry)

        # Re-render just the affected row's label rather than a full reload.
        self._relabel_all([e for e, _ in self._entries])
        query = self.query_one("#filter", Input).value
        highlighted_entry = entry
        self._apply_filter(query)
        if highlighted_entry in self._filtered:
            option_list.highlighted = self._filtered.index(highlighted_entry)
        self.query_one("#status", Static).update(
            f"Deleted cached copy of {entry.name}."
        )
