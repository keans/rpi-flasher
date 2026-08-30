import pytermgui as ptg

from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.base import Screen


class _ButtonScreen(Screen):
    def __init__(self, labels: list[str]) -> None:
        self.labels = labels

    def build(self) -> ptg.Window:
        return ptg.Window(*(ptg.Button(label) for label in self.labels))


def test_pop_restores_the_selection_from_before_push():
    app = RpiFlasherApp()
    first = _ButtonScreen(["one", "two", "three"])
    second = _ButtonScreen(["next"])
    app.push_screen(first)
    assert first.window is not None
    first.window.select(2)

    app.push_screen(second)
    app.pop_screen()

    assert app.screen is first
    assert first.window.selected_index == 2


def test_nested_dialogs_preserve_each_screens_own_selection():
    app = RpiFlasherApp()
    first = _ButtonScreen(["one", "two"])
    second = _ButtonScreen(["alpha", "beta", "gamma"])
    third = _ButtonScreen(["dialog"])
    app.push_screen(first)
    assert first.window is not None
    first.window.select(1)
    app.push_screen(second)
    assert second.window is not None
    second.window.select(2)
    app.push_screen(third)

    app.pop_screen()
    assert second.window.selected_index == 2

    app.pop_screen()
    assert first.window.selected_index == 1
