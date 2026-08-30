from pytermgui.regex import strip_ansi

from rpi_flasher.screens._widgets import (
    ACTION_ALIGN,
    CONTROL_ALIGN,
    make_action_button,
    make_action_row,
    make_labeled_checkbox,
    make_list_container,
)
from rpi_flasher.screens.wlan_details import WlanDetailsScreen
from rpi_flasher.state import FlashOptions


def test_shared_controls_follow_alignment_convention():
    checkbox = make_labeled_checkbox("Option")
    list_container = make_list_container()
    action = make_action_button("Next")
    action_row = make_action_row(action)

    assert checkbox.parent_align == CONTROL_ALIGN
    assert list_container.parent_align == CONTROL_ALIGN
    assert action.parent_align == ACTION_ALIGN
    assert action_row.parent_align == ACTION_ALIGN


def test_action_rows_are_compact_without_a_column_separator():
    no = make_action_button("No, go back")
    yes = make_action_button("Yes, erase and flash")
    row = make_action_row(no, yes)
    row.width = 76

    rendered = strip_ansi(row.get_lines()[0])

    assert " | " not in rendered
    assert rendered == "  No, go back      Yes, erase and flash  "


def test_wlan_editable_values_start_in_the_same_column():
    screen = WlanDetailsScreen(FlashOptions(setup_wlan=True))

    prompts = [
        screen.ssid_field.prompt,
        screen.password_field.prompt,
        screen.country_field.prompt,
    ]
    assert len({len(prompt) for prompt in prompts}) == 1
    assert all(
        field.parent_align == CONTROL_ALIGN
        for field in (
            screen.ssid_field,
            screen.password_field,
            screen.country_field,
        )
    )
