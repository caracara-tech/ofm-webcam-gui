# Translating the interface

The interface language is chosen at startup (selector in the startup dialog,
remembered for next time) or for one run with `--lang es_419`. Currently
installed: English (source) and Latin American Spanish (`es_419`).

Only text shown in the GUI is translated. Log output, `--help` and code
comments stay in English.

## Who needs what

| You want to... | You need | Extra install |
|---|---|---|
| Run the microscope | `requirements/<platform>.txt` | nothing for languages |
| Develop the application | the same | nothing for languages |
| Work on translations | Babel | `pip install -r requirements/i18n.txt` |

Running and developing never need Babel: the app uses Python's built-in
`gettext` and loads the compiled catalogs that are committed to the repo.

## How it works

- English text in the code is the message id (`_("Start Stream")`). A missing
  translation falls back to English, so a half-finished language never breaks
  the app.
- Catalogs live in `core/locales/<code>/LC_MESSAGES/`:
  `ofm_webcam_gui.po` (what translators edit) and `ofm_webcam_gui.mo`
  (compiled, what the app loads; commit both).
- `core/locales/ofm_webcam_gui.pot` is the template of all current strings.
- A language shows up in the selector as soon as its `.mo` exists. No code
  change is needed to add one.

## Updating an existing language

```bash
pip install -r requirements/i18n.txt        # once
python tools/i18n.py update                 # pick up new/changed strings
# edit core/locales/es_419/LC_MESSAGES/ofm_webcam_gui.po
#   (any text editor, or Poedit / Lokalize / Weblate)
python tools/i18n.py compile
python tools/i18n.py check                  # add --strict to fail on missing strings
```

`status` shows progress per language. Commit the `.po`, the `.mo` and the `.pot`.

## Adding a language

```bash
python tools/i18n.py new pt_BR
```

Then translate the file and `compile` / `check` as above. Two entries need
care:

- The entry with context **"language name"** (msgid `English`): its
  translation is the language's own name in the selector, for example
  `Español (Latinoamérica)`.
- The `jog button` entries: one or two letters on the stage buttons.

## Rules for translators

- Keep `{placeholders}` exactly as written (`{count}`, `{fps:.1f}`, ...). You
  may move them within the sentence. `check` rejects translations whose
  placeholders differ from the source.
- Keep `\n` line breaks and the technical text: `pip install ...`, `sudo
  usermod ...`, `PNG`, `.mp4`, `µm`, `fps`.
- Comments starting with "i18n:" in the source are shown to you as notes.
- Texts that mention a button (for example "click Start Stream") must use
  the translated name of that button.

## Style guide: Latin American Spanish (`es_419`)

- Neutral Latin American vocabulary; avoid Spain-only terms (`ordenador`).
- Buttons and menu items: infinitive ("Iniciar transmisión").
  Messages addressed to the user: formal imperative ("Revise el cable").
- Glossary, to keep wording consistent:

| English | Spanish |
|---|---|
| stage (microscope) | platina |
| stage board / board | placa |
| stream | transmisión |
| snapshot | captura |
| recording | grabación |
| frame | fotograma |
| auto-focus | enfoque automático |
| scale bar | barra de escala |
| grid | cuadrícula |
| timestamp | marca de tiempo |

## For developers: marking strings

```python
from core.i18n import _, ngettext, pgettext, N_

_("Start Stream")                                   # a plain string
_("Saved {filename}").format(filename=name)         # named placeholders, never f-strings or concatenation
ngettext("{n} pass", "{n} passes", n).format(n=n)   # anything with a count
pgettext("jog button: up", "U")                     # same text, different meaning: add a context
# i18n: a hint that translators will see          # comment directly above the call
```

- Never build a sentence from pieces; translators must be able to reorder it.
- Module-level tables are created before the language is chosen. Mark their
  entries with `N_("...")` and translate where they are used: `_(TABLE[key])`.
- Do not use `_` as a throwaway variable in a module that imports `_`; Python
  would treat it as a local name and the `_("...")` calls would fail.
- After adding or changing strings: `python tools/i18n.py update`, translate,
  `compile`, `check`.
