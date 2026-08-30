"""Package metadata for rpi-flasher."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rpi-flasher")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

WINDOW_TITLE = f"rpi-flasher v{__version__}"
