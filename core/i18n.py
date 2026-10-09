"""Runtime translation support. Standard library only: no extra dependency.

Design
- English is the source language: the English text in the code *is* the
  message id, so a missing translation silently falls back to English.
- Catalogs are compiled GNU gettext files (`.mo`) under core/locales/,
  one folder per language (`es_419`, ...). They are committed, so running
  the app never needs a compiler or Babel. Babel is only needed to *edit*
  translations; see tools/i18n.py and docs/TRANSLATING.md.
- A language is "installed" simply by having its catalog present. Its name,
  in its own language, is read from the catalog itself, so adding a language
  needs no code change.
- The language is chosen once at startup (no live switching).

No Qt in here on purpose: hardware/ and core/ also produce user-visible
messages, and those layers must stay Qt-free.

Usage
    from core.i18n import _, ngettext, pgettext
    label = _("Start Stream")
    text = _("Saved {filename}").format(filename=name)      # named placeholders
    text = ngettext("{n} pass", "{n} passes", n).format(n=n)
    btn = pgettext("jog button: up", "U")                    # disambiguating context
    # Don't use `_` as a throwaway variable in a module that imports it.
    TABLE = {...: N_("Text")}   # N_ only *marks* a string defined at import time;
                                # translate it where it is used: _(TABLE[key])
"""

from __future__ import annotations

import gettext as _gettext
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DOMAIN = "ofm_webcam_gui"
SOURCE_LANGUAGE = "en"
LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@dataclass(frozen=True)
class Language:
    code: str
    name: str  # written in the language itself, e.g. "Español (Latinoamérica)"


_translation: _gettext.NullTranslations = _gettext.NullTranslations()
_active: str = SOURCE_LANGUAGE


# ------------------------------------------------------------ translating --
def gettext(message: str) -> str:
    return _translation.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    return _translation.pgettext(context, message)


def N_(message: str) -> str:
    """Marks a string for extraction without translating it (see module docstring)."""
    return message


_ = gettext


# ------------------------------------------------------------- languages ---
def _catalog_path(code: str) -> Path:
    return LOCALES_DIR / code / "LC_MESSAGES" / f"{DOMAIN}.mo"


def _native_name(code: str) -> str:
    """The language's own name, stored as a regular catalog entry."""
    try:
        with open(_catalog_path(code), "rb") as f:
            catalog = _gettext.GNUTranslations(f)
        # i18n: Name of THIS language, written in that language, shown in the language selector (e.g. "Español (Latinoamérica)"). Do not translate literally.
        name = catalog.pgettext("language name", "English")
        return name if name != "English" else code
    except Exception as exc:
        logger.warning("Could not read language name for %r: %s", code, exc)
        return code


def available_languages() -> list[Language]:
    """English plus every language that has a compiled catalog installed."""
    languages = [Language(SOURCE_LANGUAGE, "English")]
    if LOCALES_DIR.is_dir():
        for folder in sorted(LOCALES_DIR.iterdir()):
            if folder.is_dir() and _catalog_path(folder.name).is_file():
                languages.append(Language(folder.name, _native_name(folder.name)))
    return languages


def _normalize(code: str) -> str:
    """'es-419', 'ES_cl.UTF-8', 'es_CL@euro' -> 'es_419', 'es_CL', 'es_CL'."""
    code = code.split(".")[0].split("@")[0].replace("-", "_").strip()
    lang, _sep, region = code.partition("_")
    return lang.lower() + (f"_{region.upper()}" if region else "")


def match_language(requested: Optional[str]) -> Optional[str]:
    """Best installed language for a requested locale code, or None.

    Exact match first, then the bare language ('es_CL' -> 'es'), then any
    installed variant of the same language ('es_CL' -> 'es_419'), which is
    how a Chilean or Mexican system locale ends up on Latin American Spanish.
    """
    if not requested:
        return None
    installed = [lang.code for lang in available_languages()]
    code = _normalize(requested)
    if code in installed:
        return code
    base = code.split("_")[0]
    if base in installed:
        return base
    return next((c for c in installed if c.split("_")[0] == base), None)


def resolve_language(*candidates: Optional[str]) -> str:
    """First candidate that matches an installed language, else English.

    Pass candidates in priority order, e.g. (cli_flag, saved_preference, system_locale).
    """
    for candidate in candidates:
        matched = match_language(candidate)
        if matched:
            return matched
    return SOURCE_LANGUAGE


def set_language(code: Optional[str]) -> str:
    """Activate a language and return the code actually activated.

    Unknown or unreadable languages fall back to English; this never raises.
    """
    global _translation, _active
    matched = match_language(code) or SOURCE_LANGUAGE
    translation: _gettext.NullTranslations = _gettext.NullTranslations()
    if matched != SOURCE_LANGUAGE:
        chain = [matched] + ([matched.split("_")[0]] if "_" in matched else [])
        try:
            translation = _gettext.translation(DOMAIN, str(LOCALES_DIR), languages=chain, fallback=True)
        except Exception as exc:
            logger.warning("Could not load language %r, using English: %s", matched, exc)
            matched = SOURCE_LANGUAGE
    _translation = translation
    _active = matched
    return matched


def current_language() -> str:
    return _active
