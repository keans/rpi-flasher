"""Small shared helpers used across screens and modules."""

from __future__ import annotations


def human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return (
                f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            )
        value /= 1024
    return f"{value:.1f} TB"
