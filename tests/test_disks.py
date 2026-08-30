from rpi_flasher.disks import DiskError, _is_removable, best_effort


def test_is_removable_true_for_sd_card():
    assert _is_removable({"RemovableMedia": True}) is True


def test_is_removable_true_for_generic_usb_card_reader():
    # Many USB SD readers report nothing SD-specific at all.
    assert (
        _is_removable(
            {
                "BusProtocol": "USB",
                "MediaName": "MassStorageClass",
                "RemovableMedia": True,
            }
        )
        is True
    )


def test_is_removable_rejects_fixed_usb_hard_drive():
    assert (
        _is_removable(
            {
                "BusProtocol": "USB",
                "MediaName": "External USB SSD",
                "RemovableMedia": False,
            }
        )
        is False
    )


def test_is_removable_rejects_mounted_disk_image():
    # Mounted .dmg files report RemovableMedia=True too, but they're
    # virtual -- not something you could ever flash.
    assert (
        _is_removable(
            {
                "BusProtocol": "Disk Image",
                "MediaName": "Disk Image",
                "RemovableMedia": True,
                "VirtualOrPhysical": "Virtual",
            }
        )
        is False
    )


def test_is_removable_rejects_internal_ssd():
    assert (
        _is_removable({"BusProtocol": "PCI-Express", "MediaName": "APPLE SSD"})
        is False
    )


def test_best_effort_returns_none_on_success():
    assert best_effort(lambda: None) is None


def test_best_effort_swallows_disk_error_and_returns_reason():
    def fail():
        raise DiskError("card removed")

    assert best_effort(fail) == "card removed"


def test_best_effort_swallows_os_error():
    def fail():
        raise OSError("no such device")

    assert best_effort(fail) == "no such device"
