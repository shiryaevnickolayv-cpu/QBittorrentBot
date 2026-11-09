from pathlib import Path

from babel.messages.pofile import read_po


LOCALES_DIR = Path(__file__).parent.parent / "src" / "locales"


def test_locales_have_no_empty_translations():
    paths = sorted(LOCALES_DIR.glob("*/LC_MESSAGES/messages.po"))
    assert {path.parent.parent.name for path in paths} == {"en", "es", "it", "pt", "ru", "uk"}
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            catalog = read_po(stream)
        assert all(message.string for message in catalog if message.id), path
        assert path.with_suffix(".mo").is_file(), path


def test_russian_locale_has_no_blacklisted_wording():
    with (LOCALES_DIR / "ru" / "LC_MESSAGES" / "messages.po").open(encoding="utf-8") as stream:
        catalog = read_po(stream)
    translations = "\n".join(message.string for message in catalog if message.id)
    for wording in ("Приветули", "инвалид", "хош", "Пж,", "файлики", "Запаузить"):
        assert wording not in translations
