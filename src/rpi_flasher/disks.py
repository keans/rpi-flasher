"""macOS disk enumeration and lifecycle helpers, built around `diskutil`.

Removable media only (not internal disks, and not "regular" external
HDDs/SSDs) is surfaced as a flash target. The reliable signal for this
turns out to be diskutil's own RemovableMedia flag rather than trying to
recognize "SD-ness" from bus protocol or product-name strings: real SD
cards report a "Secure Digital" bus protocol, but SD cards plugged in via
a generic USB card reader/adapter often report nothing SD-specific at all
(BusProtocol "USB", MediaName/IORegistryEntryName just "MassStorageClass")
-- indistinguishable from an SD card by name alone. External hard
drives/SSDs, even over USB, are normally reported as fixed media
(RemovableMedia false) rather than removable, so filtering on
RemovableMedia keeps the "no regular hard drives" guarantee without
needing to guess at SD-specific wording. Mounted disk images (.dmg) also
report RemovableMedia=True, so VirtualOrPhysical is checked too, to
exclude those virtual devices.
"""

from __future__ import annotations

import plistlib
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from rpi_flasher.state import DiskInfo


class DiskError(RuntimeError):
    pass


def best_effort(op: Callable[[], object]) -> str | None:
    """Run a disk operation that is allowed to fail without aborting the
    overall flash (e.g. eject, boot-partition customization after a
    successful write). Returns None on success, or the failure reason."""
    try:
        op()
    except (DiskError, OSError) as exc:
        return str(exc)
    return None


def _run_plist(args: list[str]) -> dict:
    result = subprocess.run(args, capture_output=True, check=True)
    return plistlib.loads(result.stdout)


def _is_removable(info: dict) -> bool:
    # Mounted disk images (.dmg) also report RemovableMedia=True, but
    # they're virtual, not a device you could ever flash -- diskutil's
    # own VirtualOrPhysical flag is what actually distinguishes them.
    if info.get("VirtualOrPhysical") == "Virtual":
        return False
    return bool(info.get("RemovableMedia", False))


def list_external_disks() -> list[DiskInfo]:
    """Return removable, writable, external disks -- the set of things it
    is plausible to flash. Excludes internal disks and "regular" external
    hard drives/SSDs (fixed media, even over USB)."""
    try:
        listing = _run_plist(["diskutil", "list", "-plist"])
    except (
        subprocess.CalledProcessError,
        OSError,
        plistlib.InvalidFileException,
    ) as exc:
        raise DiskError(f"Could not scan disks: {exc}") from exc
    whole_disks: list[str] = listing.get("WholeDisks", [])

    disks: list[DiskInfo] = []
    for device_id in whole_disks:
        device_node = f"/dev/{device_id}"
        try:
            info = _run_plist(["diskutil", "info", "-plist", device_node])
        except subprocess.CalledProcessError:
            continue

        if info.get("Internal", True):
            continue
        if not info.get("WritableMedia", False):
            continue
        if not _is_removable(info):
            continue

        volume_names = _volume_names_for(device_id, listing)

        disks.append(
            DiskInfo(
                device_node=device_node,
                raw_device_node=f"/dev/r{device_id}",
                size_bytes=int(info.get("TotalSize", 0)),
                volume_names=volume_names,
            )
        )
    return disks


def diagnose_disks() -> list[str]:
    """Explain, per whole disk, why it was or wasn't offered as a flash
    target. Only called when the list comes back empty, to help a user
    figure out why their card/reader isn't showing up without needing to
    run diskutil manually."""
    try:
        listing = _run_plist(["diskutil", "list", "-plist"])
    except subprocess.CalledProcessError as exc:
        return [f"Could not run diskutil: {exc}"]

    whole_disks: list[str] = listing.get("WholeDisks", [])
    if not whole_disks:
        return ["No disks of any kind were reported by diskutil."]

    messages = []
    for device_id in whole_disks:
        device_node = f"/dev/{device_id}"
        try:
            info = _run_plist(["diskutil", "info", "-plist", device_node])
        except subprocess.CalledProcessError as exc:
            messages.append(f"{device_node}: diskutil info failed ({exc})")
            continue

        if info.get("Internal", True):
            messages.append(f"{device_node}: excluded (internal disk)")
        elif not info.get("WritableMedia", False):
            messages.append(f"{device_node}: excluded (not writable)")
        elif info.get("VirtualOrPhysical") == "Virtual":
            messages.append(
                f"{device_node}: excluded (virtual disk image, not a "
                "physical device)"
            )
        elif not _is_removable(info):
            bus = info.get("BusProtocol", "unknown")
            media = info.get("MediaName", "unknown")
            messages.append(
                f"{device_node}: excluded (not removable media -- likely "
                f"a fixed external drive -- bus={bus!r}, media={media!r})"
            )
        else:
            messages.append(f"{device_node}: recognized as removable media")
    return messages


def _volume_names_for(device_id: str, listing: dict) -> list[str]:
    names: list[str] = []
    for disk_entry in listing.get("AllDisksAndPartitions", []):
        if disk_entry.get("DeviceIdentifier") != device_id:
            continue
        for partition in disk_entry.get("Partitions", []):
            name = partition.get("VolumeName")
            if name:
                names.append(name)
    return names


def _run_diskutil(
    verb: str, device_node: str, action_description: str
) -> None:
    try:
        subprocess.run(
            ["diskutil", verb, device_node], check=True, capture_output=True
        )
    except subprocess.CalledProcessError as exc:
        raise DiskError(
            f"Failed to {action_description} {device_node}: "
            f"{exc.stderr.decode(errors='replace')}"
        ) from exc


def unmount_disk(device_node: str) -> None:
    _run_diskutil("unmountDisk", device_node, "unmount")


def mount_disk(device_node: str) -> None:
    _run_diskutil("mountDisk", device_node, "mount")


def eject_disk(device_node: str) -> None:
    _run_diskutil("eject", device_node, "eject")


def find_boot_partition_mountpoint(
    device_node: str, timeout: float = 15.0
) -> Path:
    """Poll for the FAT32 boot partition's mount point after a raw write,
    since macOS auto-mounts partitions asynchronously."""
    deadline = time.monotonic() + timeout
    device_id = device_node.removeprefix("/dev/")

    while time.monotonic() < deadline:
        try:
            listing = _run_plist(["diskutil", "list", "-plist"])
        except subprocess.CalledProcessError:
            time.sleep(0.5)
            continue

        for disk_entry in listing.get("AllDisksAndPartitions", []):
            if disk_entry.get("DeviceIdentifier") != device_id:
                continue
            for partition in disk_entry.get("Partitions", []):
                content = str(partition.get("Content", ""))
                if "FAT" not in content.upper():
                    continue
                part_id = partition.get("DeviceIdentifier")
                if not part_id:
                    continue
                try:
                    part_info = _run_plist(
                        ["diskutil", "info", "-plist", f"/dev/{part_id}"]
                    )
                except subprocess.CalledProcessError:
                    continue
                mount_point = part_info.get("MountPoint")
                if mount_point:
                    return Path(mount_point)
        time.sleep(0.5)

    raise DiskError(
        f"Boot partition on {device_node} did not mount within {timeout}s"
    )
