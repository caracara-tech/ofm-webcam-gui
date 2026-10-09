#!/usr/bin/env python3
"""Translation maintenance tool.

Needs Babel (translators and maintainers only; running the app does not):
    pip install -r requirements/i18n.txt

Commands (run from the repository root):
    python tools/i18n.py extract        scan the source -> core/locales/ofm_webcam_gui.pot
    python tools/i18n.py update         extract, then merge new/changed strings into every language
    python tools/i18n.py new pt_BR      start a new language
    python tools/i18n.py compile        .po -> .mo (the files the app actually loads)
    python tools/i18n.py check          verify all catalogs (run before committing / in CI)
    python tools/i18n.py check --strict ...and fail on untranslated strings too
    python tools/i18n.py status         translation progress per language

Full workflow: docs/TRANSLATING.md
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from gettext import GNUTranslations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "core" / "locales"
DOMAIN = "ofm_webcam_gui"
POT = LOCALES / f"{DOMAIN}.pot"
PROJECT = "OFM Webcam Viewer"

# Where translatable strings live, and which calls mark them.
METHOD_MAP = [("app.py", "python"), ("core/**.py", "python"), ("hardware/**.py", "python"), ("ui/**.py", "python")]
KEYWORDS = {"_": None, "gettext": None, "N_": None, "ngettext": (1, 2), "pgettext": ((1, "c"), 2)}
COMMENT_TAGS = ["i18n:"]  # `# i18n: hint` above a call becomes a note for translators

# The entry that carries each language's own name (read by core/i18n.py).
NAME_ENTRY = ("language name", "English")

PLACEHOLDER = re.compile(r"\{[^{}]*\}")


# ------------------------------------------------------------------ setup --
def _babel():
    try:
        from babel.messages import catalog, extract, mofile, pofile
    except ImportError:
        sys.exit(
            "This tool needs Babel, which is only required for translation work.\n"
            "Install it with:\n    pip install -r requirements/i18n.txt"
        )
    return catalog, extract, mofile, pofile


def _version() -> str:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "core" / "version.py").read_text("utf-8"))
    return match.group(1) if match else "0"


def _po_files() -> list[Path]:
    return sorted(LOCALES.glob(f"*/LC_MESSAGES/{DOMAIN}.po"))


def _code(po: Path) -> str:
    return po.parent.parent.name


def _locale_or_none(code: str):
    from babel import Locale
    try:
        return Locale.parse(code)
    except Exception:
        return None


def _read_po(path: Path):
    _, _, _, pofile = _babel()
    with open(path, "rb") as f:
        return pofile.read_po(f, locale=_locale_or_none(_code(path)) if path.suffix == ".po" and path != POT else None)


def _write_po(path: Path, cat) -> None:
    _, _, _, pofile = _babel()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pofile.write_po(f, cat, width=100, include_lineno=False)


def _real(cat):
    """Catalog entries without the header pseudo-entry."""
    return [m for m in cat if m.id]


def _ids(cat) -> set:
    return {(m.context, m.id) for m in _real(cat)}


def _is_translated(msg) -> bool:
    return all(msg.string) if isinstance(msg.string, (tuple, list)) else bool(msg.string)


# --------------------------------------------------------------- commands --
def build_template():
    catalog, extract, _, _ = _babel()
    cat = catalog.Catalog(project=PROJECT, version=_version(), charset="utf-8", fuzzy=False)
    for filename, lineno, message, comments, context in extract.extract_from_dir(
        str(ROOT), method_map=METHOD_MAP, keywords=KEYWORDS,
        comment_tags=COMMENT_TAGS, strip_comment_tags=True,
    ):
        cat.add(message, locations=[(filename, lineno)], auto_comments=comments, context=context)
    return cat


def cmd_extract() -> int:
    _, _, _, pofile = _babel()
    template = build_template()
    buf = io.BytesIO()
    pofile.write_po(buf, template, width=100, include_lineno=False)
    new_text = buf.getvalue().decode("utf-8")

    def stable(text: str) -> str:  # ignore the timestamp so unchanged strings don't churn git
        return re.sub(r'"POT-Creation-Date:.*\n', "", text)

    if POT.exists() and stable(POT.read_text("utf-8")) == stable(new_text):
        print(f"{POT.relative_to(ROOT)}: unchanged ({len(_real(template))} strings)")
        return 0
    POT.parent.mkdir(parents=True, exist_ok=True)
    POT.write_text(new_text, "utf-8")
    print(f"{POT.relative_to(ROOT)}: written ({len(_real(template))} strings)")
    return 0


def cmd_update() -> int:
    cmd_extract()
    template = _read_po(POT)
    for po in _po_files():
        cat = _read_po(po)
        before = _ids(cat)
        cat.update(template, no_fuzzy_matching=False, update_header_comment=False, update_creation_date=False)
        removed = len(cat.obsolete)
        cat.obsolete.clear()  # strings no longer in the source are dropped, not kept as #~ leftovers
        _write_po(po, cat)
        added = len(_ids(cat) - before)
        todo = sum(1 for m in _real(cat) if not _is_translated(m) or m.fuzzy)
        print(f"{_code(po)}: {added} new, {removed} removed, {todo} still to translate or review")
    if not _po_files():
        print("No languages yet. Start one with: python tools/i18n.py new <code>   (e.g. es_419, pt_BR)")
    return 0


def cmd_new(code: str) -> int:
    catalog, _, _, _ = _babel()
    po = LOCALES / code / "LC_MESSAGES" / f"{DOMAIN}.po"
    if po.exists():
        print(f"{po.relative_to(ROOT)} already exists; use `update` instead.")
        return 1
    locale = _locale_or_none(code)
    if locale is None:
        print(f"Unknown locale code {code!r}. Use a form like es_419, pt_BR, fr.")
        return 1
    cmd_extract()
    cat = catalog.Catalog(locale=locale, project=PROJECT, version=_version(), charset="utf-8")
    cat.update(_read_po(POT), update_header_comment=False, update_creation_date=False)
    _write_po(po, cat)
    print(f"Created {po.relative_to(ROOT)}.")
    print('Remember the entry with context "language name": its translation is this language\'s own name '
          "in the selector, e.g. \"Español (Latinoamérica)\".")
    print("Then run: python tools/i18n.py compile && python tools/i18n.py check")
    return 0


def cmd_compile() -> int:
    _, _, mofile, _ = _babel()
    for po in _po_files():
        cat = _read_po(po)
        mo = po.with_suffix(".mo")
        with open(mo, "wb") as f:
            mofile.write_mo(f, cat, use_fuzzy=False)
        done = sum(1 for m in _real(cat) if _is_translated(m) and not m.fuzzy)
        print(f"{mo.relative_to(ROOT)}: {done}/{len(_real(cat))} strings")
    if not _po_files():
        print("No .po files found.")
    return 0


def _stats(cat) -> tuple[int, int, int]:
    entries = _real(cat)
    translated = sum(1 for m in entries if _is_translated(m) and not m.fuzzy)
    fuzzy = sum(1 for m in entries if m.fuzzy)
    return translated, len(entries), fuzzy


def cmd_status() -> int:
    for po in _po_files():
        done, total, fuzzy = _stats(_read_po(po))
        pct = 100 * done // total if total else 100
        print(f"{_code(po):8} {done:4}/{total:<4} {pct:3d}%" + (f"  ({fuzzy} fuzzy)" if fuzzy else ""))
    if not _po_files():
        print("No languages yet (English only).")
    return 0


def _placeholders(value) -> set[str]:
    texts = value if isinstance(value, (tuple, list)) else [value]
    return {tok for t in texts for tok in PLACEHOLDER.findall(t or "")}


def cmd_check(strict: bool) -> int:
    _, _, mofile, _ = _babel()
    errors: list[str] = []
    warnings: list[str] = []

    template = build_template()
    if not POT.exists():
        errors.append(f"{POT.relative_to(ROOT)} is missing: run `extract`")
    elif _ids(_read_po(POT)) != _ids(template):
        errors.append(f"{POT.relative_to(ROOT)} is out of date with the source: run `update`")

    for po in _po_files():
        code = _code(po)
        cat = _read_po(po)
        source_ids = _ids(template)

        missing = source_ids - _ids(cat)
        if missing:
            errors.append(f"{code}: {len(missing)} string(s) from the source are not in the catalog: run `update`")
        stale = _ids(cat) - source_ids
        if stale:
            warnings.append(f"{code}: {len(stale)} obsolete string(s) (removed from the source): run `update`")

        untranslated = 0
        for msg in _real(cat):
            label = f"{code}: {msg.id if isinstance(msg.id, str) else msg.id[0]!r}"
            if msg.fuzzy:
                errors.append(f"{label} is marked fuzzy: review it and remove the flag")
            if not _is_translated(msg):
                untranslated += 1
                continue
            source = _placeholders(msg.id)
            found = _placeholders(msg.string)
            plural = isinstance(msg.id, (tuple, list))
            if (found - source) or (not plural and source != found):
                errors.append(f"{label}: placeholders differ (source {sorted(source)}, translation {sorted(found)})")
        if untranslated:
            (errors if strict else warnings).append(f"{code}: {untranslated} untranslated string(s)")

        name = cat.get(NAME_ENTRY[1], context=NAME_ENTRY[0])
        if name is None or not name.string:
            errors.append(f'{code}: missing translation of "English" (context "language name"), the name shown in the selector')

        mo = po.with_suffix(".mo")
        if not mo.exists():
            errors.append(f"{code}: compiled catalog is missing: run `compile`")
        else:
            buf = io.BytesIO()
            mofile.write_mo(buf, cat, use_fuzzy=False)
            buf.seek(0)
            with open(mo, "rb") as f:
                if GNUTranslations(buf)._catalog != GNUTranslations(f)._catalog:
                    errors.append(f"{code}: the .mo is out of date with the .po: run `compile`")

        done, total, _ = _stats(cat)
        print(f"{code}: {done}/{total} translated")

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error:   {e}")
    print("OK" if not errors else f"{len(errors)} problem(s) found")
    return 1 if errors else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Translation maintenance tool.", epilog="Workflow: docs/TRANSLATING.md")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="scan the source into the .pot template")
    sub.add_parser("update", help="extract, then merge new strings into every language")
    new = sub.add_parser("new", help="start a new language")
    new.add_argument("code", help="locale code, e.g. es_419, pt_BR, fr")
    sub.add_parser("compile", help="compile .po to .mo")
    check = sub.add_parser("check", help="verify all catalogs")
    check.add_argument("--strict", action="store_true", help="treat untranslated strings as errors")
    sub.add_parser("status", help="translation progress per language")
    args = parser.parse_args(argv)

    return {
        "extract": cmd_extract,
        "update": cmd_update,
        "new": lambda: cmd_new(args.code),
        "compile": cmd_compile,
        "check": lambda: cmd_check(args.strict),
        "status": cmd_status,
    }[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
