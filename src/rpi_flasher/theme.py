"""Restrained color theme and shared presentation labels."""

from __future__ import annotations

import pytermgui as ptg

from rpi_flasher.utils import step_title


def configure_theme() -> None:
    """Apply a dark slate palette with clear, restrained focus color."""
    ptg.palette.regenerate(
        primary="#416783",
        secondary="#47777a",
        tertiary="#625c78",
        accent="#ae8546",
        success="#5f9168",
        warning="#b58b48",
        error="#ae5f62",
        surface="#15191e",
        surface2="#1a2027",
        surface3="#20252d",
    )

    ptg.Window.set_focus_styles(
        focused=("primary+1", "primary+1"),
        blurred=("surface", "surface"),
    )
    ptg.Button.styles.label = "[@surface2 #91a8b9]{item}"
    ptg.Button.styles.highlight = "[@primary+1 #ffffff bold]{item}"
    ptg.Checkbox.styles.label = "[secondary+1]{item}"
    ptg.Checkbox.styles.highlight = "[@primary #ffffff bold]{item}"
    ptg.InputField.styles.prompt = "[secondary+1 bold]{item}"
    ptg.InputField.styles.cursor = "[@primary+1 #ffffff]{item}"


def make_step_label(step: int) -> ptg.Label:
    """Return the consistently accented title used by wizard screens."""
    return ptg.Label(f"[primary+1 bold]{step_title(step)}[/]")


def make_hint_label(text: str) -> ptg.Label:
    """Return understated supporting copy below a screen title."""
    return ptg.Label(f"[secondary+1]{ptg.escape_markup(text)}[/]")
