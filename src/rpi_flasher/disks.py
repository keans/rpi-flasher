"""macOS disk enumeration and lifecycle helpers, built around `diskutil`.

Only actual SD cards are surfaced (not USB hard drives/SSDs, internal
disks, or other removable media) -- identified via `diskutil info`'s
BusProtocol/MediaName/DeviceTreePath, which for a real SD card reader/slot
reports a "Secure Digital"/"SD"/card-reader bus protocol rather than "USB"
generically or "PCI-Express"/"SATA" for internal drives.
"""

from __future__ import annotations

import plistlib
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from rpi_flasher.state import DiskInfo

SD_BUS_PROTOCOL_HINTS = ("secure digital", "sd card", "sdio")
SD_MEDIA_NAME_HINTS = ("sd card", "sdhc", "sdxc", "sdsc")


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


def _is_sd_card(info: dict) -> bool:
    bus_protocol = str(info.get("BusProtocol", "")).lower()
    media_name = str(info.get("MediaName", "")).lower()
    device_tree_path = str(info.get("DeviceTreePath", "")).lower()

    if any(hint in bus_protocol for hint in SD_BUS_PROTOCOL_HINTS):
        return True
    if any(hint in media_name for hint in SD_MEDIA_NAME_HINTS):
        return True
    return "sdio" in device_tree_path or "sd-card" in device_tree_path


def list_external_disks() -> list[DiskInfo]:
    """Return SD cards only -- external, removable, writable, and identified
    as SD media by bus protocol / media name. Excludes internal disks and
    other USB mass-storage devices (external HDDs/SSDs/flash drives)."""
    listing = _run_plist(["diskutil", "list", "-plist"])
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
        if not _is_sd_card(info):
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
    """Explain, per whole disk, why it was or wasn't offered as an SD
    card. Only called when the SD-card list comes back empty, to help a
    user figure out why their card isn't showing up (e.g. an unsupported
    reader/bus protocol) without needing to run diskutil manually."""
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
        elif not _is_sd_card(info):
            bus = info.get("BusProtocol", "unknown")
            media = info.get("MediaName", "unknown")
            messages.append(
                f"{device_node}: excluded (not recognized as an SD card "
                f"-- bus={bus!r}, media={media!r})"
            )
        else:
            messages.append(f"{device_node}: recognized as an SD card")
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
