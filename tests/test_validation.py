import pytest

from src.utils import parse_setting_value, validate_name


@pytest.mark.parametrize("name", ["", "   ", "bad/name", "bad\\name", "bad:name", "x" * 256, "bad\nname"])
def test_invalid_rename_names(name):
    assert not validate_name(name)


def test_valid_rename_name():
    assert validate_name("Нормальное имя 123")


@pytest.mark.parametrize(
    ("key", "text", "expected"),
    [
        ("max_ratio", "0", 0.0),
        ("max_ratio", "100", 100.0),
        ("max_ratio", "12.3", 12.3),
        ("max_seeding_time", "0", 0),
        ("max_seeding_time", "100000", 100000),
        ("max_inactive_seeding_time", "100000", 100000),
        ("max_active_downloads", "1", 1),
        ("max_active_uploads", "50", 50),
        ("max_active_torrents", "25", 25),
        ("dl_limit", "0", 0),
        ("up_limit", "1000", 1000 * 1024 * 1024),
        ("dl_limit", "12.5", 13107200),
    ],
)
def test_valid_numeric_settings(key, text, expected):
    assert parse_setting_value(key, text) == expected


@pytest.mark.parametrize(
    ("key", "text"),
    [
        ("max_ratio", "-0.1"),
        ("max_ratio", "100.1"),
        ("max_ratio", "1.01"),
        ("max_ratio", "not a number"),
        ("max_seeding_time", "-1"),
        ("max_seeding_time", "100001"),
        ("max_seeding_time", "1.5"),
        ("max_active_downloads", "0"),
        ("max_active_uploads", "51"),
        ("max_active_torrents", "2.5"),
        ("dl_limit", "-1"),
        ("up_limit", "1001"),
        ("up_limit", "NaN"),
    ],
)
def test_invalid_numeric_settings(key, text):
    with pytest.raises(ValueError):
        parse_setting_value(key, text)
