from rpi_flasher.app import _split_keys


def test_splits_fast_typed_burst_into_individual_characters():
    # PyTermGUI's low-level reader drains everything the OS has buffered
    # in one read; typing at normal speed between polls reliably
    # produces a multi-character burst like this instead of one key at
    # a time, and previously the whole burst was silently dropped.
    assert _split_keys("MySecretPass123") == list("MySecretPass123")


def test_keeps_csi_escape_sequence_intact():
    assert _split_keys("\x1b[A") == ["\x1b[A"]
    assert _split_keys("\x1b[1;2A") == ["\x1b[1;2A"]
    assert _split_keys("\x1b[15~") == ["\x1b[15~"]


def test_keeps_ss3_escape_sequence_intact():
    assert _split_keys("\x1bOP") == ["\x1bOP"]


def test_splits_burst_containing_an_escape_sequence():
    assert _split_keys("ab\x1b[Acd") == ["a", "b", "\x1b[A", "c", "d"]


def test_bare_escape_or_alt_combo():
    assert _split_keys("\x1b") == ["\x1b"]
    assert _split_keys("\x1bq") == ["\x1bq"]


def test_empty_input_splits_to_no_keys():
    assert _split_keys("") == []
