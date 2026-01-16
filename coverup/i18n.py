"""
Internationalization (i18n) support for CoverUP PDF.

This module provides a simple dictionary-based translation system.
Translations are stored in translations.py, making them easy to
maintain and PyInstaller-friendly (no external resource files needed).

Usage:
    from coverup.i18n import _
    translated_text = _('key_name')
"""

import locale

from coverup.translations import TRANSLATIONS

# Current language (set once at startup)
_current_lang = 'en'


def get_system_locale():
    """
    Detect the system locale and return the language code.

    Returns:
        str: Two-letter language code (e.g., 'en', 'de', 'fr').
             Defaults to 'en' if detection fails.
    """
    try:
        # Try to get the system locale
        loc = locale.getdefaultlocale()[0]
        if loc:
            # Extract language code (first two characters)
            return loc[:2].lower()
    except Exception:
        pass
    return 'en'


def init_language(lang=None):
    """
    Initialize the translation system with the specified or detected language.

    Args:
        lang: Optional language code (e.g., 'en', 'de'). If None, auto-detects.
    """
    global _current_lang

    if lang is None:
        lang = get_system_locale()

    # Fall back to English if language not available
    if lang in TRANSLATIONS:
        _current_lang = lang
    else:
        _current_lang = 'en'


def get_current_language():
    """Return the current language code."""
    return _current_lang


def get_available_languages():
    """Return list of available language codes."""
    return list(TRANSLATIONS.keys())


def _(key, **kwargs):
    """
    Get translated string for the given key.

    Args:
        key: Translation key (e.g., 'tooltip_open').
        **kwargs: Format arguments for string interpolation.

    Returns:
        str: Translated string, or the key itself if not found.
    """
    translations = TRANSLATIONS.get(_current_lang, TRANSLATIONS['en'])
    text = translations.get(key)

    if text is None:
        # Fall back to English
        text = TRANSLATIONS['en'].get(key, key)

    # Apply format arguments if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


def _plural(key_singular, key_plural, count, **kwargs):
    """
    Get translated string with plural handling.

    Args:
        key_singular: Translation key for singular form.
        key_plural: Translation key for plural form.
        count: The count to determine singular/plural.
        **kwargs: Additional format arguments.

    Returns:
        str: Translated string with count applied.
    """
    key = key_singular if count == 1 else key_plural
    return _(key, count=count, **kwargs)


# Initialize with system locale on import
init_language()
