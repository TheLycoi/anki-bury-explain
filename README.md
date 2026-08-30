# Bury Explain

AI help when you keep failing a card: auto-bury plus instant AI explanation.

## What it does

Fail a card too many times in a short window and Bury Explain buries it,
optionally tags it, and opens your preferred AI chat provider with the card's
content pre-searched, so you get an explanation immediately instead of
grinding the same card into the ground.

## What it does not touch

Bury Explain only runs inside Anki's `reviewer_did_answer_card` hook, which
fires after Anki has already written the review to its log and updated the
card's scheduling state. So your fail is scored normally no matter what the
add-on does next, and burying only moves the card's due date; it does not
undo or backdate the grade. The add-on also never writes AI output into your
notes or fields. It sends the card's text to whichever provider you
configured and opens the reply in a sidebar or browser; nothing comes back
into your collection.

## Features

- Auto-bury: cards that cross a configurable fail threshold within a time
  window are buried automatically.
- 6 AI providers, including a custom URL, so you can point it at whatever
  chat tool you actually use.
- Sidebar with persistent login, so you are not re-authenticating every
  session.
- Top-toolbar "AI" button: a plain-text toggle to open or hide the sidebar
  at any time, no failure required.
- Optional tagging: turn the tag off if you only want the bury plus AI help.
- Minimalist single-dialog options: one screen, no nested settings maze.
- Works offline-safe: reviewing continues normally if the AI provider is
  unreachable.

## Install

From AnkiWeb: https://ankiweb.net/shared/info/1712717227, or in Anki go to
Tools > Add-ons > Get Add-ons and paste the code `1712717227`.

Manually: download the latest `bury_explain.ankiaddon` and double-click it
to install into Anki.

## Configuration

| Key | Description | Default |
|---|---|---|
| `enabled` | Turn the add-on on or off | `true` |
| `again_threshold` | Number of "Again" presses within the window before a card is buried | `3` |
| `timeframe_hours` | Rolling window (in hours) the threshold is counted over | `24` |
| `bury` | Whether matching cards are actually buried | `true` |
| `add_tag` | Whether the note is tagged when triggered | `true` |
| `tag` | Tag applied to buried cards (only when `add_tag` is on) | `buryexplain-leech` |
| `ignore_new_cards` | Skip cards still in the "new" queue | `false` |
| `skip_image_cards` | Don't trigger on image / occlusion note types | `true` |
| `show_notification` | Show an in-app notification when a card is buried | `true` |
| `provider` | Which AI provider to open | `ChatGPT` |
| `custom_url` | URL template used when `provider` is `custom` | _(empty)_ |
| `open_in` | Where the provider opens, sidebar or browser | `sidebar` |
| `prompt_template` | Template used to pre-fill the AI query with the card's content; asks for a simple explanation, a mnemonic, likely confusions, and an audit against Wozniak's 20 rules of formulating knowledge with concrete rewrite suggestions | built-in default |

## Building

Requires only the Python 3 standard library.

```
python3 build.py
```

Produces `dist/bury_explain.ankiaddon`, ready to upload to AnkiWeb or
install manually.

## Credits

Inspired by AJT Mortician (Ajatt-Tools, AGPL) and Anki Terminator by
Shigeyuki. No code from either is included; this is an independent
implementation. Not affiliated with either project.

## License

[GNU AGPL-3.0-or-later](LICENSE), required for Anki add-ons.
