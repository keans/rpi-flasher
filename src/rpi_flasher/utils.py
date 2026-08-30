"""Small shared helpers used across screens and modules."""

from __future__ import annotations

# Fixed wizard step labels, used for the "Step N/M: ..." breadcrumb shown
# in each screen's title. Steps 3 (OS) and 4 (image) are sometimes
# auto-skipped when a narrower choice leaves only one match, but the
# ordinal numbering stays stable so the breadcrumb still reads as
# progress rather than resetting.
STEP_LABELS = (
    "Select disk",
    "Select Pi model",
    "Select OS",
    "Select image",
    "Options",
    "User account",
    "WLAN details",
    "Confirm",
    "Flashing",
)

# Named ordinals for the STEP_LABELS entries above, so each screen passes
# a self-documenting name to step_title() instead of a bare integer --
# reordering/inserting a step only needs updating this block plus
# STEP_LABELS, rather than hunting down every step_title(N) call site.
(
    STEP_DISK,
    STEP_DEVICE,
    STEP_OS,
    STEP_IMAGE,
    STEP_OPTIONS,
    STEP_USER_DETAILS,
    STEP_WLAN_DETAILS,
    STEP_CONFIRM,
    STEP_FLASHING,
) = range(1, len(STEP_LABELS) + 1)


def step_title(step: int) -> str:
    return f"Step {step}/{len(STEP_LABELS)}: {STEP_LABELS[step - 1]}"


def human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return (
                f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            )
        value /= 1024
    return f"{value:.1f} TB"
