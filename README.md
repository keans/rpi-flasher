# rpi-flasher

A macOS TUI (built with [Textual](https://textual.textualize.io/)) for
flashing Raspberry Pi OS images to SD cards, similar in spirit to
Raspberry Pi Imager but keyboard-driven.

## Wizard flow

1. **Select SD card** — lists SD cards detected via `diskutil` (internal
   disks and non-SD external drives like USB HDDs are filtered out).
2. **Select image** — browses the official Raspberry Pi Imager OS feed,
   showing which images are already cached locally vs. need downloading.
3. **Options** — toggle SSH, WLAN (SSID/password/country), and whether to
   delete the downloaded image after a successful flash. SSH/WLAN
   preferences are remembered for next time in
   `~/.config/rpi-flasher/config.json` (plaintext, `0600` permissions —
   there's no keychain integration in this version).
4. **Overview** — summarizes your choices; you must type the exact device
   path (e.g. `/dev/disk4`) to arm the flash button, since this is a
   destructive operation.
5. **Flash** — unmounts the card, downloads/verifies/decompresses the
   image on the fly (cached under `~/.cache/rpi-flasher/`), writes it to
   the raw device with live progress, applies SSH/WLAN customization to
   the boot partition (`wpa_supplicant.conf` for legacy images,
   `custom.toml` for Bookworm+ cloud-init images), then ejects.

## Requirements

- macOS, Python 3.12+, [uv](https://docs.astral.sh/uv/)
- `diskutil` on `PATH` — ships with macOS by default; the app checks for
  it on startup and exits with an error if it's missing.
- **Full Disk Access** for your terminal app (Terminal.app/iTerm2), under
  System Settings → Privacy & Security. macOS SIP can block raw disk
  writes even as root without this — it's not fixable in code.

## Usage

```sh
uv run rpi-flasher
```

Writing to a raw disk device requires root. If not already running as
root, the app re-execs itself once through `sudo` before the TUI starts,
so you'll see a single password prompt in your plain terminal.

## Development

```sh
uv run ruff check .    # lint
uv run ruff format .   # format (79-char line length)
uv run pytest          # unit tests
```
