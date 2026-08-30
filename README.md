# rpi-flasher

`rpi-flasher` is a keyboard-driven macOS terminal application for writing
Raspberry Pi images to SD cards. It uses
[PyTermGUI](https://github.com/bczsalba/pytermgui) and the official Raspberry
Pi Imager OS feed.

The interface filters out internal disks and fixed external drives, verifies
downloaded images before writing, and defaults destructive confirmation to
**No**.

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
5. **Options** — enable SSH, configure WLAN, or delete the downloaded image
   after a successful flash.
6. **WLAN details** — enter the SSID, password, and two-letter country code.
   Remembering the Wi-Fi password is optional and disabled unless explicitly
   selected.
7. **Confirm** — review the disk, image, and customization choices, then
   answer **No, go back** or **Yes, erase and flash**. No is focused by default.
   Images larger than the selected card cannot be confirmed.
8. **Flashing** — download, decompress, verify, write, customize, and eject the
   card with live progress and an estimated completion time.

The downloaded, decompressed image cache is stored under
`~/.cache/rpi-flasher/`. The latest OS-list snapshot is stored alongside it so
the wizard can continue after a network failure.

When the application exits, it remembers the highlighted disk, Pi model, OS
family, and image. On the next launch, matching items are preselected; if a
card or feed entry is no longer available, the corresponding screen safely
falls back to its first item.

## Keyboard controls

- **Arrow keys** — move between controls and list entries
- **Enter** — activate the selected control
- **Tab** — jump directly to Next where available, or cycle through the
  visible actions on the progress screen
- **Escape** — return to the previous screen and restore its previous
  selection
- **r** — rescan disks or retry loading the OS list on the relevant screen
- **d** — delete the highlighted cached image on the image screen
- **Left/Right** — choose No or Yes on the confirmation screen
- **q** — quit when not typing in a text field
- **Ctrl+C** — exit cleanly; during flashing, cancel first when safe or wait
  for an active raw write to finish. After the terminal is restored, a notice
  confirms that the interruption was handled and selections were saved.

During flashing, use the visible **Cancel** button to stop the operation.
Cancelling during download or verification is safe to retry. Cancelling after
raw writing begins leaves an incomplete card that must be reflashed before use.

## WLAN credentials

When remembering WLAN details is selected, they are stored in:

```text
~/.config/rpi-flasher/config.json
```

The file uses owner-only (`0600`) permissions, but the password is plaintext;
there is currently no macOS Keychain integration. SSH and WLAN enablement
preferences may be retained, while deleting an image after flashing remains a
per-run choice.

## Flash pipeline

The application:

1. Unmounts the selected disk.
2. Downloads and decompresses `.xz`, `.zip`, or raw `.img` images.
3. Verifies the decompressed SHA-256 checksum.
4. Writes to the corresponding raw device with progress reporting.
5. Remounts and customizes the boot partition when requested.
6. Writes `wpa_supplicant.conf` for legacy images or `custom.toml` for newer
   cloud-init images.
7. Ejects the card.

Non-fatal customization or eject problems remain visible on the completion
screen instead of being hidden by a generic success message.

## Development

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The project targets a 79-character Python line length. The TUI test suite uses
mocked disks and downloads; it does not write to real block devices.
