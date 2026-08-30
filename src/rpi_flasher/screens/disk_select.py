"""First wizard screen: lists SD cards found via `diskutil`."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher import WINDOW_TITLE, disks
from rpi_flasher.screens._listbox import build_listbox
from rpi_flasher.screens._widgets import make_list_container
from rpi_flasher.screens.base import Screen
from rpi_flasher.state import DiskInfo, wizard_state
from rpi_flasher.theme import make_hint_label, make_step_label
from rpi_flasher.utils import STEP_DISK, human_bytes


class DiskSelectScreen(Screen):
    def __init__(self) -> None:
        self._disks: list[DiskInfo] = []
        self._status_label = ptg.Label("")
        self._list_container = make_list_container()

    def build(self) -> ptg.Window:
        window = ptg.Window(
            make_step_label(STEP_DISK),
            ptg.Label(""),
            make_hint_label(
                "Insert an SD card, then select it and press Enter."
            ),
            ptg.Label(""),
            self._status_label,
            self._list_container,
            box="DOUBLE",
        )
        window.set_title(WINDOW_TITLE)
        window.bind("r", lambda *_: self.rescan(), "Rescan")
        return window

    def on_mount(self) -> None:
        self.rescan()

    def rescan(self) -> None:
        try:
            self._disks = disks.list_external_disks()
        except disks.DiskError as exc:
            self._disks = []
            self._render(f"{exc}\n\nPress 'r' to rescan.")
            return

        if not self._disks:
            diagnostics = "\n".join(disks.diagnose_disks())
            status = (
                "No SD cards found. Insert an SD card and press 'r' to "
                "rescan.\n\nDiagnostics:\n"
                + (diagnostics or "(no disks attached)")
            )
        else:
            status = ""
        self._render(status)

    def _render(self, status: str) -> None:
        self._status_label.value = ptg.escape_markup(status)
        labels = [
            f"{d.device_node}  {human_bytes(d.size_bytes)}  "
            f"{', '.join(d.volume_names) or '(unnamed)'}"
            for d in self._disks
        ]
        self._list_container.set_widgets(
            build_listbox(labels, self.select_disk)
        )
        preferred = self.app.saved_selections.disk_device_node
        preferred_size = self.app.saved_selections.disk_size_bytes
        preferred_names = self.app.saved_selections.disk_volume_names
        index = next(
            (
                i
                for i, disk in enumerate(self._disks)
                if disk.device_node == preferred
                and preferred_size is not None
                and disk.size_bytes == preferred_size
                and preferred_names is not None
                and tuple(disk.volume_names) == preferred_names
            ),
            0,
        )
        if self.window is not None and self._disks:
            self.window.select(index)

    def store_selection(self) -> None:
        selected = self.selected_item(self._disks)
        if selected is not None:
            wizard_state(self).disk = selected

    def select_disk(self, index: int) -> None:
        if not (0 <= index < len(self._disks)):
            return
        wizard_state(self).disk = self._disks[index]

        from rpi_flasher.screens.device_select import DeviceSelectScreen

        self.app.push_screen(DeviceSelectScreen())
