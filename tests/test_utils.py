import pytest

from src.utils import MAX_NAME_LEN, convert_eta, convert_size, convert_speed, paginate, status_icon, truncate_name


@pytest.mark.parametrize(
    ("state", "icon"),
    [
        ("error", "⚠️"),
        ("missingFiles", "⚠️"),
        ("uploading", "⬆️"),
        ("stalledUP", "💤"),
        ("queuedUP", "⏳"),
        ("stoppedUP", "⏸"),
        ("checkingUP", "🔄"),
        ("forcedUP", "⬆️"),
        ("downloading", "⬇️"),
        ("metaDL", "⬇️"),
        ("stalledDL", "🔌"),
        ("queuedDL", "🕓"),
        ("stoppedDL", "⏸"),
        ("forcedDL", "⬇️"),
        ("checkingDL", "🔄"),
        ("checkingResumeData", "🔄"),
        ("moving", "🔄"),
        ("unknown", "❓"),
    ],
)
def test_status_icon(state, icon):
    assert status_icon(state) == icon


def test_pagination_first_and_last_pages():
    items = list(range(19))
    first, page, pages = paginate(items, 1, per_page=8)
    assert first == list(range(8))
    assert page == 1
    assert pages == 3

    last, page, pages = paginate(items, 3, per_page=8)
    assert last == [16, 17, 18]
    assert page == 3
    assert pages == 3


def test_pagination_empty_list():
    assert paginate([], 1) == ([], 1, 1)


@pytest.mark.parametrize(("requested", "expected_page", "expected_items"), [(0, 1, [0, 1]), (99, 2, [2])])
def test_pagination_out_of_range(requested, expected_page, expected_items):
    items, page, pages = paginate([0, 1, 2], requested, per_page=2)
    assert items == expected_items
    assert page == expected_page
    assert pages == 2


@pytest.mark.parametrize(
    ("size", "formatted"),
    [(0, "0 Б"), (1024, "1.0 КБ"), (12.3 * 1024**2, "12.3 МБ/с".removesuffix("/с")), (2.14 * 1024**4, "2.14 ТБ")],
)
def test_convert_size(size, formatted):
    assert convert_size(size) == formatted


@pytest.mark.parametrize(
    ("eta", "formatted"),
    [(45, "45 сек"), (8100, "2 ч 15 мин"), (97200, "1 д 3 ч"), (8640000, "∞"), (-1, "∞"), (None, "∞")],
)
def test_convert_eta(eta, formatted):
    assert convert_eta(eta) == formatted


def test_convert_speed():
    assert convert_speed(12.3 * 1024**2) == "12.3 МБ/с"
    assert convert_speed(0) == "0 Б/с"


def test_truncate_name():
    short = "short name"
    assert truncate_name(short) == short
    long_name = "x" * (MAX_NAME_LEN + 1)
    truncated = truncate_name(long_name)
    assert truncated == "x" * (MAX_NAME_LEN - 1) + "…"
    assert len(truncated) == MAX_NAME_LEN
