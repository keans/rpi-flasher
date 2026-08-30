from rpi_flasher import disks


def test_diagnose_disks_reports_no_disks(monkeypatch):
    monkeypatch.setattr(disks, "_run_plist", lambda args: {"WholeDisks": []})
    messages = disks.diagnose_disks()
    assert messages == ["No disks of any kind were reported by diskutil."]


def test_diagnose_disks_explains_each_exclusion_reason(monkeypatch):
    def fake_run_plist(args):
        if args[:2] == ["diskutil", "list"]:
            return {"WholeDisks": ["disk0", "disk4"]}
        device_node = args[-1]
        if device_node == "/dev/disk0":
            return {"Internal": True, "WritableMedia": True}
        if device_node == "/dev/disk4":
            return {
                "Internal": False,
                "WritableMedia": True,
                "RemovableMedia": False,
                "BusProtocol": "USB",
                "MediaName": "External USB SSD",
            }
        raise AssertionError(f"unexpected device_node {device_node}")

    monkeypatch.setattr(disks, "_run_plist", fake_run_plist)
    messages = disks.diagnose_disks()

    assert any("disk0" in m and "internal disk" in m for m in messages)
    assert any("disk4" in m and "not removable media" in m for m in messages)


def test_diagnose_disks_reports_recognized_removable_disk(monkeypatch):
    def fake_run_plist(args):
        if args[:2] == ["diskutil", "list"]:
            return {"WholeDisks": ["disk5"]}
        return {
            "Internal": False,
            "WritableMedia": True,
            "RemovableMedia": True,
            "BusProtocol": "USB",
            "MediaName": "MassStorageClass",
        }

    monkeypatch.setattr(disks, "_run_plist", fake_run_plist)
    messages = disks.diagnose_disks()

    assert messages == ["/dev/disk5: recognized as removable media"]
