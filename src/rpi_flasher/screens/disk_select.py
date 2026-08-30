"""First wizard screen: lists SD cards found via `diskutil`."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, LoadingIndicator, Static

from rpi_flasher import disks
from rpi_flasher.state import DiskInfo, wizard_state
from rpi_flasher.utils import STEP_DISK, human_bytes, step_title


class DiskSelectScreen(Screen):
    BINDINGS: ClassVar = [("r", "rescan", "Rescan")]

    def __init__(self) -> None:
        super().__init__()
        self._disks: list[DiskInfo] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(step_title(STEP_DISK), id="title"),
            Static(
                "Insert an SD card, then select it with the arrow keys and Enter.",
                classes="hint",
            ),
            LoadingIndicator(id="scanning"),
            DataTable(id="disk-table"),
            Static("", id="empty-state"),
            id="disk-select-body",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Device", "Size", "Volumes")
        table.cursor_type = "row"
        self.action_rescan()

    def action_rescan(self) -> None:
        self.run_worker(self._rescan(), exclusive=True)

    async def _rescan(self) -> None:
        table = self.query_one(DataTable)
        empty = self.query_one("#empty-state", Static)
        loading = self.query_one("#scanning", LoadingIndicator)

        loading.display = True
        table.display = False
        empty.display = False
        try:
            self._disks = await asyncio.to_thread(disks.list_external_disks)
        except disks.DiskError as exc:
            loading.display = False
            empty.display = True
            empty.update(f"{exc}\n\nPress 'r' to rescan.")
            return
        loading.display = False
        table.clear()

        if not self._disks:
            table.display = False
            empty.display = True
            diagnostics = "\n".join(disks.diagnose_disks())
            empty.update(
                "No SD cards found. Insert an SD card and press 'r' to "
                "rescan.\n\nDiagnostics:\n"
                + (diagnostics or "(no disks attached)")
            )
            return

        table.display = True
        empty.display = False
        for disk in self._disks:
            table.add_row(
                disk.device_node,
                human_bytes(disk.size_bytes),
                ", ".join(disk.volume_names) or "(unnamed)",
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        index = event.cursor_row
        if 0 <= index < len(self._disks):
            wizard_state(self).disk = self._disks[index]
            from rpi_flasher.screens.device_select import DeviceSelectScreen

            self.app.push_screen(DeviceSelectScreen())
