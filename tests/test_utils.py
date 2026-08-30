from rpi_flasher.utils import human_bytes


def test_human_bytes_units():
    assert human_bytes(0) == "0 B"
    assert human_bytes(512) == "512 B"
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(1024**3) == "1.0 GB"


def test_human_bytes_caps_at_tb():
    assert human_bytes(1024**5) == "1024.0 TB"
