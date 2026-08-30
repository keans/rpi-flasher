# rpi-flasher

A macOS TUI (built with [Textual](https://textual.textualize.io/)) for
flashing Raspberry Pi OS images to SD cards, similar in spirit to
Raspberry Pi Imager but keyboard-driven.

## Wizard flow

1. **Select disk** — lists removable media detected via `diskutil`
   (internal disks and fixed external drives like USB HDDs are filtered
   out).
2. **Select Pi model** — lists every Raspberry Pi model referenced by the
   official OS feed; picking one narrows down to images built for it.
3. **Select OS** — lists the OS families available for that model (e.g.
   "Raspberry Pi OS", "Media player OS", "Other general-purpose OS").
4. **Select image** — browses/searches the images in the chosen family,
   showing which are already cached locally vs. need downloading. Steps 3
   and 4 are skipped automatically whenever a narrowing choice leaves only
   one possible image — straight to Options in that case.
5. **Options** — toggle SSH, WLAN, and whether to delete the downloaded
   image after a successful flash.
6. **WLAN details** — (only shown if WLAN setup was checked) SSID,
   password, and a two-letter country code. SSH/WLAN preferences can
   optionally be remembered in `~/.config/rpi-flasher/config.json`
   (plaintext with `0600` permissions; saving the password is opt-in).
7. **Overview** — summarizes your choices behind a Yes/No confirmation
   (defaulting to "No") before arming the flash, since this is a
   destructive operation.
8. **Flash** — unmounts the card, downloads/verifies/decompresses the
   image on the fly (cached under `~/.cache/rpi-flasher/`), writes it to
   the raw device with live progress, applies SSH/WLAN customization to
   the boot partition (`wpa_supplicant.conf` for legacy images,
   `custom.toml` for Bookworm+ cloud-init images), then ejects.

Press `q` on any screen to quit.

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
