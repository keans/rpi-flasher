from rpi_flasher import disks
from rpi_flasher.app import RpiFlasherApp
from rpi_flasher.screens.disk_select import DiskSelectScreen
from rpi_flasher.state import DiskInfo


def test_r_binding_rescans(monkeypatch):
    calls = 0

    def fake_list():
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(disks, "list_external_disks", fake_list)
    monkeypatch.setattr(disks, "diagnose_disks", list)
    app = RpiFlasherApp()
    screen = DiskSelectScreen()
    app.push_screen(screen)
    assert screen.window is not None

    app.manager.handle_key("r")

    assert calls == 2


def test_quit_saves_highlighted_disk_for_next_launch(tmp_path, monkeypatch):
    from rpi_flasher import config

    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    found = [
        DiskInfo("/dev/disk4", "/dev/rdisk4", 100, []),
        DiskInfo("/dev/disk9", "/dev/rdisk9", 200, []),
    ]
    monkeypatch.setattr(disks, "list_external_disks", lambda: found)
    app = RpiFlasherApp()
    screen = DiskSelectScreen()
    app.push_screen(screen)
    assert screen.window is not None
    screen.window.select(1)

    app.exit()

    assert config.load_selections().disk_device_node == "/dev/disk9"


def test_saved_disk_is_preselected_when_still_available(tmp_path, monkeypatch):
    from rpi_flasher import config
    from rpi_flasher.state import WizardState

    monkeypatch.setattr(config, "invoking_user_home", lambda: str(tmp_path))
    config.save_selections(
        WizardState(disk=DiskInfo("/dev/disk9", "/dev/rdisk9", 200, []))
    )
    found = [
        DiskInfo("/dev/disk4", "/dev/rdisk4", 100, []),
        DiskInfo("/dev/disk9", "/dev/rdisk9", 200, []),
    ]
    monkeypatch.setattr(disks, "list_external_disks", lambda: found)

    app = RpiFlasherApp()
    screen = DiskSelectScreen()
    app.push_screen(screen)

    assert screen.window is not None
    assert screen.window.selected_index == 1
