"""Persisted user preferences (SSH/Wi-Fi) so the Options screen can be
pre-filled on subsequent runs.

Stored as plaintext JSON at ~/.config/rpi-flasher/config.json with 0600
permissions. The Wi-Fi password is stored in plaintext (not keychain-backed)
-- a deliberate v1 tradeoff, documented in the README.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from rpi_flasher.privilege import (
    ensure_user_owned_dir,
    invoking_user_home,
    write_user_owned_file,
)
from rpi_flasher.state import FlashOptions, WlanConfig


def config_dir() -> Path:
    return Path(invoking_user_home()) / ".config" / "rpi-flasher"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_preferences() -> FlashOptions:
    path = config_path()
    if not path.exists():
        return FlashOptions()
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return FlashOptions()

    wlan_data = data.get("wlan")
    wlan = WlanConfig(**wlan_data) if wlan_data else None
    return FlashOptions(
        enable_ssh=bool(data.get("enable_ssh", False)),
        setup_wlan=bool(data.get("setup_wlan", False)),
        wlan=wlan,
    )


def save_preferences(options: FlashOptions) -> None:
    """Persist ssh/wifi preferences. Does not persist delete_image_after_flash,
    which is a per-run choice rather than a durable preference."""
    ensure_user_owned_dir(config_dir())

    data = {
        "enable_ssh": options.enable_ssh,
        "setup_wlan": options.setup_wlan,
        "wlan": asdict(options.wlan) if options.wlan else None,
    }
    write_user_owned_file(
        config_path(), json.dumps(data, indent=2), mode=0o600
    )
