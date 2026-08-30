"""Writes SSH/Wi-Fi customization files into the freshly-flashed boot partition."""

from __future__ import annotations

import json
from pathlib import Path

from rpi_flasher import images
from rpi_flasher.state import FlashOptions, ImageEntry, UserConfig, WlanConfig


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _yaml_string(value: str) -> str:
    """A YAML double-quoted scalar for `value`. JSON string literals are
    valid YAML flow scalars, so `json.dumps` gives correct YAML escaping
    (quotes, backslashes, control/unicode characters) for free, the same
    way `_toml_escape` above hand-rolls it for TOML."""
    return json.dumps(value)


def apply(
    boot_mountpoint: Path, image: ImageEntry, options: FlashOptions
) -> list[str]:
    """Write the requested customizations; returns non-fatal warnings
    about the choices made (e.g. an unverified format guess), separate
    from the exceptions this raises for actual I/O failures."""
    warnings: list[str] = []

    if options.enable_ssh:
        (boot_mountpoint / "ssh").touch()

    # userconf.txt (via the separate userconf-pi package) and the bare
    # `ssh` file above are unaffected by the custom.toml/cloud-init split
    # below -- both predate custom.toml and remain supported unchanged on
    # every Raspberry Pi OS release, including Trixie.
    if (
        options.configure_user
        and options.user is not None
        and images.os_category(image) == "Raspberry Pi OS"
    ):
        write_userconf(boot_mountpoint, options.user)

    if options.setup_wlan and options.wlan is not None:
        if image.init_format == "cloudinit-rpi":
            if images.uses_real_cloudinit(image):
                write_cloudinit_network_config(boot_mountpoint, options.wlan)
            else:
                write_cloudinit_custom_toml(
                    boot_mountpoint,
                    options.wlan,
                    enable_ssh=options.enable_ssh,
                )
                codename = images.unrecognized_cloudinit_codename(image)
                if codename is not None:
                    warnings.append(
                        f"Unrecognized OS codename {codename!r}; assumed "
                        "the legacy custom.toml format for WLAN setup. If "
                        "this OS actually uses real cloud-init instead, "
                        "Wi-Fi will not be configured."
                    )
        else:
            write_wpa_supplicant(boot_mountpoint, options.wlan)

    return warnings


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


def write_cloudinit_network_config(
    boot_mountpoint: Path, wlan: WlanConfig
) -> None:
    """Trixie+ Raspberry Pi OS uses real upstream cloud-init (a NoCloud
    datasource seeded from the boot partition, per RPi-Distro/
    rpi-cloud-init-mods) instead of the bespoke custom.toml format
    read by Bookworm's now-removed init_config script. cloud-init reads
    Wi-Fi from its own `network-config` (netplan v2 syntax), not
    custom.toml -- writing custom.toml here would just be ignored.
    `network-config` alone is sufficient: cloud-init's NoCloud file
    seed only requires `meta-data` to exist, and doesn't error when
    `network-config` is the only file present.
    """
    lines = [
        "network:",
        "  version: 2",
        "  renderer: NetworkManager",
        "  wifis:",
        # Raspberry Pi's onboard radio has always enumerated as wlan0;
        # unlike custom.toml there's no imaging-tool-facing API that
        # names it any other way.
        "    wlan0:",
        "      dhcp4: true",
        f"      regulatory-domain: {wlan.country}",
        "      access-points:",
        f"        {_yaml_string(wlan.ssid)}:",
        f"          password: {_yaml_string(wlan.password)}",
    ]
    (boot_mountpoint / "network-config").write_text("\n".join(lines) + "\n")


def write_userconf(boot_mountpoint: Path, user: UserConfig) -> None:
    """Provision a Pi OS user using a crypt-formatted password hash."""
    (boot_mountpoint / "userconf.txt").write_text(
        f"{user.username}:{user.password_hash}\n"
    )


def write_cloudinit_custom_toml(
    boot_mountpoint: Path, wlan: WlanConfig, enable_ssh: bool
) -> None:
    # raspberrypi-sys-mods' init_config defaults `password_encrypted` to
    # True for [wlan] (it assumes a pre-hashed value unless told
    # otherwise), so writing a plaintext password without explicitly
    # setting this to false makes it try to use the plaintext string as
    # if it were already a hash -- Wi-Fi silently never connects. Same
    # script's [ssh] section reads the key `enabled`, not `enable`.
    lines = [
        "[wlan]",
        f'ssid = "{_toml_escape(wlan.ssid)}"',
        f'password = "{_toml_escape(wlan.password)}"',
        "password_encrypted = false",
        f'country = "{_toml_escape(wlan.country)}"',
        "hidden = false",
    ]
    if enable_ssh:
        lines += ["", "[ssh]", "enabled = true"]
    (boot_mountpoint / "custom.toml").write_text("\n".join(lines) + "\n")
