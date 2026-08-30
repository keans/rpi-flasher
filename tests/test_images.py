from rpi_flasher.images import display_label, flatten_os_list, is_cached_at
from rpi_flasher.state import ImageEntry

RAW_OS_LIST = [
    {
        "name": "Raspberry Pi OS (64-bit)",
        "description": "desc",
        "icon": "icon.png",
        "url": "https://example.com/a.img.xz",
        "extract_size": 100,
        "extract_sha256": "aaa",
        "image_download_size": 50,
        "release_date": "2026-01-01",
        "init_format": "cloudinit-rpi",
        "devices": ["pi5-64bit"],
        "capabilities": [],
    },
    {
        "name": "Raspberry Pi OS (other)",
        "subitems": [
            {
                "name": "Raspberry Pi OS Lite",
                "url": "https://example.com/b.img.xz",
                "extract_size": 10,
                "extract_sha256": "bbb",
                "image_download_size": 5,
                "release_date": "2026-01-01",
            }
        ],
    },
    {
        # A category with no selectable leaves should contribute nothing.
        "name": "Empty category",
        "subitems": [],
    },
]


def test_flatten_os_list_expands_leaves_and_categories():
    entries = flatten_os_list(RAW_OS_LIST)
    names = [e.name for e in entries]
    assert names == ["Raspberry Pi OS (64-bit)", "Raspberry Pi OS Lite"]


def test_flatten_os_list_tracks_category_path():
    entries = flatten_os_list(RAW_OS_LIST)
    top_level, nested = entries
    assert top_level.category_path == []
    assert nested.category_path == ["Raspberry Pi OS (other)"]


def test_is_cached_at_requires_matching_size(tmp_path):
    path = tmp_path / "image.img"
    assert is_cached_at(path, 10) is False

    path.write_bytes(b"x" * 10)
    assert is_cached_at(path, 10) is True
    assert is_cached_at(path, 11) is False


def _entry(**overrides) -> ImageEntry:
    defaults = {
        "name": "Test OS",
        "description": "",
        "icon_url": "",
        "url": "https://example.com/x.img.xz",
        "extract_size": 100,
        "extract_sha256": "abc",
        "image_download_size": 2 * 1024 * 1024,
        "release_date": "2026-01-01",
        "init_format": None,
        "devices": [],
        "capabilities": [],
        "category_path": [],
    }
    defaults.update(overrides)
    return ImageEntry(**defaults)


def test_display_label_shows_cached_status():
    entry = _entry()
    assert display_label(entry, cached=True) == "[Cached] Test OS"


def test_display_label_shows_download_size_with_category():
    entry = _entry(category_path=["Media player OS"])
    label = display_label(entry, cached=False)
    assert label == "[Download 2.0 MB] [Media player OS] Test OS"
