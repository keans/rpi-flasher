"""Root elevation handling.

Writing to a raw disk device (/dev/rdiskN) on macOS requires root. Textual
takes over the terminal (alt-screen, raw mode) once it starts, so an
interactive `sudo` prompt mid-run is not workable. Instead, if the process
is not already root, it re-execs itself once through `sudo` before Textual
ever starts, so the single password prompt happens in a plain terminal.
"""

from __future__ import annotations

import os
import pwd
import sys
from pathlib import Path


def is_root() -> bool:
    return os.geteuid() == 0


def ensure_root() -> None:
    """Re-exec the current process under sudo if not already root.

    Never returns if it re-execs (os.execvp replaces the process image).
    """
    if is_root():
        return
    print(
        "rpi-flasher needs administrator access to write the selected SD "
        "card. sudo will ask for your macOS password now. If writing is "
        "later denied, grant this terminal Full Disk Access in System "
        "Settings > Privacy & Security.",
        file=sys.stderr,
    )
    try:
        os.execvp(
            "sudo",
            [
                "sudo",
                "-E",
                sys.executable,
                "-m",
                "rpi_flasher.app",
                *sys.argv[1:],
            ],
        )
    except OSError as exc:
        print(
            f"error: could not re-run as root via sudo ({exc}). "
            "rpi-flasher needs root to write to a raw disk device -- "
            "try running it with: sudo uv run rpi-flasher",
            file=sys.stderr,
        )
        sys.exit(1)


def invoking_user_home() -> str:
    """Home directory of the user who ran `sudo`, falling back to the current user.

    Needed because once elevated, files created under `~/.cache` or
    `~/.config` would otherwise end up owned by root and unusable/duplicated
    when the tool is later run without sudo.
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return pwd.getpwnam(sudo_user).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


def chown_to_invoking_user(path: str) -> None:
    """Fix ownership of a path back to the invoking (non-root) user, if applicable."""
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or not is_root():
        return
    try:
        pw = pwd.getpwnam(sudo_user)
    except KeyError:
        return
    try:
        gid = pw.pw_gid
        os.chown(path, pw.pw_uid, gid)
    except OSError:
        pass


def ensure_user_owned_dir(path: Path) -> Path:
    """Create `path` (and parents) if needed, owned by the invoking user
    rather than root. Centralizes the mkdir+chown pattern needed by every
    cache/config directory this app writes to."""
    path.mkdir(parents=True, exist_ok=True)
    chown_to_invoking_user(str(path))
    return path


def write_user_owned_file(
    path: Path, data: str, mode: int | None = None
) -> None:
    """Write `data` to `path`, then fix permissions/ownership back to the
    invoking user. Centralizes the write+chmod+chown pattern used for
    config and cache-snapshot files."""
    path.write_text(data)
    if mode is not None:
        os.chmod(path, mode)
    chown_to_invoking_user(str(path))
