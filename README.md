# rpi-flasher

`rpi-flasher` is a keyboard-driven macOS terminal application for writing
Raspberry Pi images to SD cards. It uses
[PyTermGUI](https://github.com/bczsalba/pytermgui) and the official Raspberry
Pi Imager OS feed.

The interface filters out internal disks and fixed external drives, verifies
downloaded images before writing, and defaults destructive confirmation to
**No**.

Disclaimer: this project is at early development stage, thus not all possible
combinations of options have been tested. There is no guarantee that this
will work for all edge cases.

## Requirements

- macOS
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- `diskutil`, included with macOS
- **Full Disk Access** for the terminal application running `rpi-flasher`

Enable Full Disk Access under **System Settings → Privacy & Security → Full
Disk Access**. macOS may otherwise reject raw disk writes even when the
process is running as root.

## Run

```sh
uv run rpi-flasher
```

Display the installed version without starting the TUI:

```sh
uv run rpi-flasher --version
```

Writing to a raw disk requires administrator access. Before opening the TUI,
the application explains why access is needed and re-runs itself through
`sudo`. The password prompt therefore appears once in the normal terminal,
before PyTermGUI takes over the screen.

## Wizard

1. **Select disk** — choose removable, writable media discovered through
   `diskutil`. Internal disks, virtual disks, read-only media, and fixed
   external drives are excluded.
2. **Select Pi model** — choose the Raspberry Pi that will use the card. The
   official OS feed loads in the background and falls back to the most recent
   cached feed when the network is unavailable.
3. **Select OS** — choose an OS family compatible with that Pi.
4. **Select image** — choose a specific image and see whether it is cached or
   needs downloading. OS and image steps are skipped when only one compatible
   choice remains.
5. **Options** — enable SSH, configure a Pi user, configure WLAN, or delete the
   downloaded image after a successful flash. User provisioning is enabled by
   default, but is only available for compatible Raspberry Pi OS images.
6. **User account** — enter the first-boot admin username and password. The
   password is hashed immediately and only the hash is written to
   `userconf.txt`. A saved account can be reused by leaving both password
   fields blank. Incompatible images skip this customization and show a
   warning on the confirmation screen.
7. **WLAN details** — enter the SSID, password, and two-letter country code.
   Remembering the Wi-Fi password is optional and disabled unless explicitly
   selected.
8. **Confirm** — review the disk, image, and customization choices, then
   answer **No, go back** or **Yes, erase and flash**. No is focused by default.
   Images larger than the selected card cannot be confirmed.
9. **Flashing** — download, decompress, verify, write, customize, and eject the
   card with live progress and a moving-window completion estimate. The final
   success screen offers only **Quit**; a failure offers **Retry** and
   **Quit**.

The downloaded, decompressed image cache is stored under
`~/.cache/rpi-flasher/`. The latest OS-list snapshot is stored alongside it so
the wizard can continue after a network failure.

When the application exits normally, through `q`, or through Ctrl+C, it saves
the current options and highlighted disk, Pi model, OS family, and image. On
the next launch, matching items are preselected. A remembered disk is restored
only when its device node, capacity, and volume names still match, preventing
the same `/dev/diskN` identifier from selecting a different card. Missing or
changed items safely fall back to the first available choice.

## Keyboard controls

- **Arrow keys** — move between controls and list entries
- **Enter** — activate the selected control
- **Tab** — jump directly to Next where available. On the User account screen,
  cycle through username, password, password confirmation, and Next. On the
  progress screen, cycle through the currently visible actions.
- **Escape** — return to the previous screen and restore its previous
  selection. Escape is disabled on the final flashing screen.
- **r** — rescan disks or retry loading the OS list on the relevant screen
- **d** — delete the highlighted cached image on the image screen
- **Left/Right** — choose No or Yes on the confirmation screen
- **q** — quit when not typing in a text field; during flashing it follows the
  same safe cancellation rules as Ctrl+C
- **Ctrl+C** — exit cleanly; during flashing, cancel first when safe or wait
  for an active raw write to finish. After the terminal is restored, a notice
  confirms that the interruption was handled and selections were saved.

During flashing, use the visible **Cancel** button to stop the operation.
Cancelling during download or verification is safe to retry. Cancelling after
raw writing begins leaves an incomplete card that must be reflashed before use.

## Stored settings and credentials

When remembering WLAN details is selected, they are stored in:

```text
~/.config/rpi-flasher/config.json
```

The file uses owner-only (`0600`) permissions, but a remembered WLAN password
is plaintext; there is currently no macOS Keychain integration. Remembering
the WLAN password is an explicit opt-in. SSH, WLAN, and user-provisioning
enablement are retained, while deleting an image after flashing remains a
per-run choice.

The Pi account username and salted password hash are also remembered so they
can be reused on later runs; the Pi account's plaintext password is never
stored. Current option values are saved on quit even if the summary screen has
not been reached.

## Flash pipeline

The application:

1. Unmounts the selected disk.
2. Downloads and decompresses `.xz`, `.zip`, or raw `.img` images.
3. Verifies the decompressed SHA-256 checksum.
4. Writes to the corresponding raw device with progress reporting.
5. Remounts and customizes the boot partition when requested.
6. Writes `userconf.txt` with the username and salted password hash for
   compatible Raspberry Pi OS images. This works unchanged on every
   Raspberry Pi OS release, including Trixie, via the separate
   `userconf-pi` package.
7. Writes WLAN configuration in the format the image actually reads (see
   "Wi-Fi configuration format" below): `wpa_supplicant.conf` for legacy
   images, `custom.toml` for Bookworm-era cloud-init-style images, or
   cloud-init's own `network-config` for Trixie and newer.
8. Ejects the card.

Non-fatal customization or eject problems remain visible on the completion
screen instead of being hidden by a generic success message.

## Wi-Fi configuration format

The OS feed's `init_format` field reports the same value
(`"cloudinit-rpi"`) for both Bookworm and Trixie+ Raspberry Pi OS builds,
even though the underlying mechanism is completely different between them:

- **Bookworm**: `custom.toml` is parsed by `raspberrypi-sys-mods`'
  `init_config` script during a special early boot.
- **Trixie and newer**: that script no longer exists. Raspberry Pi OS
  switched to genuine upstream cloud-init (`RPi-Distro/
  rpi-cloud-init-mods`, using a `NoCloud` datasource seeded from the boot
  partition), which has no knowledge of `custom.toml` at all — writing it
  there would be silently ignored.

Since the feed can't distinguish these, `rpi-flasher` reads the Debian
codename embedded in the image's download filename (e.g.
`...-raspios-trixie-arm64.img.xz`) against an explicit list of confirmed
codenames. An unrecognized or absent codename intentionally falls back to
the legacy `custom.toml` behavior rather than guessing it's the newer
format — a completion-screen warning calls this out so it's visible rather
than a silent guess. If a future Raspberry Pi OS release changes format
again, its codename needs to be added to `REAL_CLOUDINIT_CODENAMES` (or
`LEGACY_CUSTOM_TOML_CODENAMES`) in `images.py`.

On Trixie+ images, Wi-Fi may not come up after the very first boot even
though `network-config` was applied correctly -- a second reboot has been
observed to resolve this. If Wi-Fi isn't online after first boot, try
rebooting the Pi once more before assuming the configuration didn't take.

## Development

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The project targets a 79-character Python line length. The TUI test suite uses
mocked disks and downloads; it does not write to real block devices.
