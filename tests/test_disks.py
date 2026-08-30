from rpi_flasher.disks import DiskError, _is_sd_card, best_effort


def test_is_sd_card_by_bus_protocol():
    assert _is_sd_card({"BusProtocol": "Secure Digital"}) is True


def test_is_sd_card_by_media_name():
    assert _is_sd_card({"MediaName": "SDXC Card Media"}) is True


def test_is_sd_card_rejects_usb_hard_drive():
    assert (
        _is_sd_card({"BusProtocol": "USB", "MediaName": "External USB SSD"})
        is False
    )


def test_is_sd_card_rejects_internal_ssd():
    assert (
        _is_sd_card({"BusProtocol": "PCI-Express", "MediaName": "APPLE SSD"})
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
