import sys

from rpi_flasher import WINDOW_TITLE, __version__
from rpi_flasher.app import main


def test_window_title_contains_installed_version():
    assert __version__ != "0.0.0+unknown"
    assert WINDOW_TITLE == f"rpi-flasher v{__version__}"


def test_version_flag_prints_without_starting_tui(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rpi-flasher", "--version"])

    main()

    assert capsys.readouterr().out.strip() == WINDOW_TITLE
