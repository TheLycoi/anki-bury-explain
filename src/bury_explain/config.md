# Bury & Explain — configuration

Prefer the **Tools → Bury & Explain Options…** dialog. The keys below are what
that dialog reads and writes.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | Master on/off switch. |
| `again_threshold` | int (1–10) | `3` | Number of recent "Again" presses that triggers the action. |
| `timeframe_hours` | int (1–168) | `24` | Rolling window, in hours, over which "Again" presses are counted. |
| `bury` | bool | `true` | Bury the card when triggered. |
| `tag` | string | `buryexplain-leech` | Tag added to the note when triggered (blank = no tag). |
| `ignore_new_cards` | bool | `false` | Skip new / learning cards. |
| `skip_image_cards` | bool | `true` | Skip note types whose name contains "image" or "occlusion" (text prompt would be useless). |
| `show_notification` | bool | `true` | Show a tooltip when the action fires. |
| `provider` | string | `chatgpt` | One of `chatgpt`, `claude`, `perplexity`, `duckduckgo`, `google_ai`, `custom`. |
| `custom_url` | string | `""` | Used only when `provider` is `custom`; must contain `{q}` where the URL-encoded prompt goes. |
| `open_in` | string | `sidebar` | `sidebar` (in-app dock) or `browser` (system browser). |
| `prompt_template` | string | see default | Prompt sent to the AI. Asks for a simple explanation, a mnemonic, likely confusions, and an audit of the card against Wozniak's 20 rules of formulating knowledge (with concrete rewrite suggestions for any rule it fails). Supports `{agains}` (fail count) and `{card}` (cleaned card text). |
