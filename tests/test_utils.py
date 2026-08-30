from rpi_flasher.utils import human_bytes, valid_wifi_country


def test_human_bytes_units():
    assert human_bytes(0) == "0 B"
    assert human_bytes(512) == "512 B"
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(1024**3) == "1.0 GB"


def test_human_bytes_caps_at_tb():
    assert human_bytes(1024**5) == "1024.0 TB"


def test_valid_wifi_country_accepts_real_codes_case_insensitively():
    assert valid_wifi_country("DE")
    assert valid_wifi_country("us")
    assert valid_wifi_country("GB")


def test_valid_wifi_country_rejects_common_mistake_and_garbage():
    # "UK" is the common typo -- the real code for the United Kingdom is GB.
    assert not valid_wifi_country("UK")
    assert not valid_wifi_country("XX")
    assert not valid_wifi_country("")
