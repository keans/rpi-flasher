"""Persisted user preferences (SSH/Wi-Fi) so the Options screen can be
pre-filled on subsequent runs.

Stored as JSON at ~/.config/rpi-flasher/config.json with 0600 permissions.
Wi-Fi credentials are only stored when the user explicitly opts in.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rpi_flasher.privilege import (
    ensure_user_owned_dir,
    invoking_user_home,
    write_user_owned_file,
)
from rpi_flasher.state import FlashOptions, UserConfig, WizardState, WlanConfig


@dataclass
class SelectionPreferences:
    disk_device_node: str | None = None
    disk_size_bytes: int | None = None
    disk_volume_names: tuple[str, ...] | None = None
    device: str | None = None
    os_category: str | None = None
    image_id: str | None = None


def config_dir() -> Path:
    return Path(invoking_user_home()) / ".config" / "rpi-flasher"


def config_path() -> Path:
    return config_dir() / "config.json"


def _load_data() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_preferences() -> FlashOptions:
    data = _load_data()

    def boolean(name: str, *, default: bool = False) -> bool:
        value = data.get(name, default)
        return value if isinstance(value, bool) else default

    wlan_data = data.get("wlan")
    wlan = None
    if isinstance(wlan_data, dict):
        ssid = wlan_data.get("ssid")
        password = wlan_data.get("password")
        country = wlan_data.get("country", "US")
        if (
            isinstance(ssid, str)
            and isinstance(password, str)
            and isinstance(country, str)
        ):
            wlan = WlanConfig(ssid=ssid, password=password, country=country)
    user_data = data.get("user")
    user = None
    if isinstance(user_data, dict):
        username = user_data.get("username")
        password_hash = user_data.get("password_hash")
        if (
            isinstance(username, str)
            and username
            and isinstance(password_hash, str)
            and password_hash.startswith("$6$")
        ):
            user = UserConfig(username, password_hash)
    return FlashOptions(
        enable_ssh=boolean("enable_ssh"),
        setup_wlan=boolean("setup_wlan"),
        wlan=wlan,
        configure_user=boolean("configure_user", default=True),
        user=user,
    )


def save_preferences(
    options: FlashOptions, *, remember_wlan: bool = False
) -> None:
    """Persist ssh/wifi preferences. Does not persist delete_image_after_flash,
    which is a per-run choice rather than a durable preference."""
    ensure_user_owned_dir(config_dir())

    data = _load_data()
    data.update(
        {
            "enable_ssh": options.enable_ssh,
            "setup_wlan": options.setup_wlan,
            "configure_user": options.configure_user,
            "user": asdict(options.user) if options.user else None,
            "wlan": asdict(options.wlan)
            if remember_wlan and options.wlan
            else None,
        }
    )
    write_user_owned_file(
        config_path(), json.dumps(data, indent=2), mode=0o600
    )


def load_selections() -> SelectionPreferences:
    raw = _load_data().get("selections", {})
    if not isinstance(raw, dict):
        return SelectionPreferences()

    def optional_string(name: str) -> str | None:
        value = raw.get(name)
        return value if isinstance(value, str) and value else None

    size = raw.get("disk_size_bytes")
    names = raw.get("disk_volume_names")
    return SelectionPreferences(
        disk_device_node=optional_string("disk_device_node"),
        disk_size_bytes=size if isinstance(size, int) and size >= 0 else None,
        disk_volume_names=(
            tuple(name for name in names if isinstance(name, str))
            if isinstance(names, list)
            else None
        ),
        device=optional_string("device"),
        os_category=optional_string("os_category"),
        image_id=optional_string("image_id"),
    )


def save_selections(state: WizardState) -> None:
    """Merge non-empty wizard selections into the durable config."""
    data = _load_data()
    selections = data.get("selections", {})
    if not isinstance(selections, dict):
        selections = {}
    values = {
        "disk_device_node": state.disk.device_node if state.disk else None,
        "disk_size_bytes": state.disk.size_bytes if state.disk else None,
        "disk_volume_names": state.disk.volume_names if state.disk else None,
        "device": state.device,
        "os_category": state.os_category,
        "image_id": (
            state.image.extract_sha256 or state.image.url
            if state.image
            else None
        ),
    }
    selections.update(
        {key: value for key, value in values.items() if value is not None}
    )
    data["selections"] = selections
    ensure_user_owned_dir(config_dir())
    write_user_owned_file(
        config_path(), json.dumps(data, indent=2), mode=0o600
    )
