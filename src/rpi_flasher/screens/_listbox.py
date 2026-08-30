"""Shared plain-list selection widget.

PyTermGUI has no OptionList/DataTable equivalent, so every "pick one of
these" screen (disk, device, OS family, image) builds its list out of
this helper: one `pytermgui.Button` per row, wired so pressing it (Enter
or click) invokes the screen's `on_select(index)` callback. The first
row ends up selected by default once the window is shown, since
PyTermGUI focuses the first selectable widget in a new window -- so
users see a highlighted default choice immediately, without pressing a
key first.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytermgui as ptg

from rpi_flasher.screens._widgets import CONTROL_ALIGN


def build_listbox(
    labels: Sequence[str],
    on_select: Callable[[int], None],
) -> list[ptg.Button]:
    """Return one compact Button per label, each calling `on_select(i)`."""
    buttons: list[ptg.Button] = []
    for index, label in enumerate(labels):
        button = ptg.Button(
            ptg.escape_markup(label), parent_align=CONTROL_ALIGN
        )
        button.onclick = _make_onclick(on_select, index)
        buttons.append(button)
    return buttons


def _make_onclick(
    on_select: Callable[[int], None], index: int
) -> Callable[[ptg.Button], None]:
    return lambda _button: on_select(index)
