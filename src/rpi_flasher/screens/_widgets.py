"""Small shared widget helpers used across screens."""

from __future__ import annotations

from collections.abc import Callable

import pytermgui as ptg

CONTROL_ALIGN = 0
CENTER_ALIGN = 1
ACTION_ALIGN = 2


class MaskedInputField(ptg.InputField):
    """Password input adapter containing PyTermGUI's private API usage.

    Keeping this compatibility shim here prevents screens from depending on
    toolkit internals and gives upgrades one well-defined place to update.
    """

    def get_lines(self) -> list[str]:
        real_lines = self._lines
        self._lines = ["•" * len(line) for line in real_lines]
        self._styled_cache = None
        try:
            return super().get_lines()
        finally:
            self._lines = real_lines
            self._styled_cache = None

    def clear_secret(self) -> None:
        """Discard the underlying plaintext value after it has been used."""
        self._lines = [""]
        self._styled_cache = None


def align_prompts(labels: list[str]) -> list[str]:
    """Right-pad `"Label: "` prompts so a group of input fields' colons
    (and the fields after them) line up in a column.

    Both WLAN and user-details screens hand-counted spaces per label to
    get this effect (`"SSID:     "`, `"Password:         "`); this
    computes the padding from the labels themselves instead.
    """
    raw = [f"{label}: " for label in labels]
    width = max(len(prompt) for prompt in raw)
    return [prompt.ljust(width) for prompt in raw]


def make_action_button(
    text: str, *, onclick: Callable[[ptg.Button], object] | None = None
) -> ptg.Button:
    """Create a consistently right-aligned standalone action button."""
    return ptg.Button(text, onclick=onclick, parent_align=ACTION_ALIGN)


def make_action_row(
    *buttons: ptg.Button, align: int = ACTION_ALIGN
) -> ptg.Splitter:
    """Create a compact, right-aligned row of related actions.

    Splitter normally stretches every child to an equal share of the window,
    which leaves short buttons floating in large empty columns. Static sizing
    keeps each button at its natural width and makes the group read as one row.
    """
    for button in buttons:
        button.size_policy = ptg.SizePolicy.STATIC
    row = ptg.Splitter(*buttons, parent_align=align)
    row.chars = {**row.chars, "separator": "  "}
    return row


def make_list_container() -> ptg.Container:
    """Create the shared left-aligned container used by selection lists."""
    return ptg.Container(parent_align=CONTROL_ALIGN)


def make_labeled_checkbox(
    text: str,
    *,
    checked: bool = False,
    on_change: Callable[[bool], None] | None = None,
) -> ptg.Checkbox:
    """A Checkbox whose visible label is `"<glyph> <text>"`.

    Pairing a bare `Checkbox` with a separate `Label` via `Splitter` (the
    obvious first approach) looks broken: `Splitter` stretches its
    children evenly across the *whole* window width and joins them with
    a `" | "` separator, so the box and its text end up far apart with a
    stray vertical line between them instead of reading as one inline
    control. Folding the text into the checkbox's own label sidesteps
    that entirely.
    """
    box = ptg.Checkbox(checked=checked, parent_align=CONTROL_ALIGN)

    def _relabel() -> None:
        glyph = ptg.Checkbox.chars["checked" if box.checked else "unchecked"]
        box.label = f"{glyph} {text}"

    def _callback(is_checked: bool) -> None:
        _relabel()
        if on_change is not None:
            on_change(is_checked)

    box.callback = _callback
    _relabel()
    return box
