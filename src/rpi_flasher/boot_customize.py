"""Writes SSH/Wi-Fi customization files into the freshly-flashed boot partition."""

from __future__ import annotations

from pathlib import Path

from rpi_flasher.state import FlashOptions, ImageEntry, WlanConfig


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def apply(
    boot_mountpoint: Path, image: ImageEntry, options: FlashOptions
) -> None:
    if options.enable_ssh:
        (boot_mountpoint / "ssh").touch()

    if options.setup_wlan and options.wlan is not None:
        if image.init_format == "cloudinit-rpi":
            write_cloudinit_custom_toml(
                boot_mountpoint, options.wlan, enable_ssh=options.enable_ssh
            )
        else:
            write_wpa_supplicant(boot_mountpoint, options.wlan)


def write_wpa_supplicant(boot_mountpoint: Path, wlan: WlanConfig) -> None:
    content = (
        f"country={wlan.country}\n"
        "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
        "update_config=1\n\n"
        "network={\n"
        f'    ssid="{wlan.ssid}"\n'
        f'    psk="{wlan.password}"\n'
        "}\n"
    )
    (boot_mountpoint / "wpa_supplicant.conf").write_text(content)


def write_cloudinit_custom_toml(
    boot_mountpoint: Path, wlan: WlanConfig, enable_ssh: bool
) -> None:
    lines = [
        "[wlan]",
        f'ssid = "{_toml_escape(wlan.ssid)}"',
        f'password = "{_toml_escape(wlan.password)}"',
        f'country = "{_toml_escape(wlan.country)}"',
        "hidden = false",
    ]
    if enable_ssh:
        lines += ["", "[ssh]", "enable = true"]
    (boot_mountpoint / "custom.toml").write_text("\n".join(lines) + "\n")
