"""Bury & Explain — AI help when you keep failing a card.

After N "Again" presses within a time window, the card is auto-buried (and
tagged) and an AI sidebar opens with the question pre-searched. Everything is
driven by one minimalist options dialog.

Original code. Inspired by Anki Terminator and AJT Mortician (behaviour only),
building on the owner's own bury_explain_bridge.
"""

import time

try:
    from anki.cards import Card
    from aqt import gui_hooks, mw
    from aqt.qt import QAction, qconnect
    from aqt.reviewer import Reviewer
    from aqt.utils import openLink, tooltip

    _ANKI = mw is not None
except Exception:  # pragma: no cover - not running inside Anki
    _ANKI = False

from . import logic

# De-dupe state: avoid firing twice for the same card in quick succession.
_last_card_id = None
_last_fired_at = 0.0


def _get_config():
    return {**logic.DEFAULT_CONFIG, **(mw.addonManager.getConfig(__name__) or {})}


def _act_on_card(card, agains, cfg):
    """Bury + tag the card, then open the AI help for it."""
    from . import collector

    # Bury + tag.
    if cfg.get("bury", True):
        try:
            mw.col.sched.bury_cards([card.id], manual=False)
        except TypeError:
            mw.col.sched.bury_cards([card.id])
        except Exception as exc:  # pragma: no cover
            print(f"[bury_explain] bury failed: {exc}")

    tag = cfg.get("tag", "")
    if tag:
        try:
            note = card.note()
            if not note.has_tag(tag):
                note.add_tag(tag)
                mw.col.update_note(note)
        except Exception as exc:  # pragma: no cover
            print(f"[bury_explain] tag failed: {exc}")

    # Build the prompt and provider URL.
    card_text = logic.clean_card_text(collector.get_card_text(card))
    prompt = logic.build_prompt(cfg.get("prompt_template", ""), agains, card_text)
    url = logic.provider_url(cfg.get("provider", "chatgpt"), cfg.get("custom_url", ""), prompt)

    if cfg.get("open_in", "sidebar") == "sidebar":
        try:
            from . import sidebar

            sidebar.open_url(url)
        except Exception as exc:  # pragma: no cover
            print(f"[bury_explain] sidebar failed, opening browser: {exc}")
            openLink(url)
    else:
        openLink(url)

    if cfg.get("show_notification", True):
        tooltip(
            f"Bury & Explain: buried after {agains} fails — asking AI",
            period=3000,
        )


def on_did_answer_card(reviewer, card, ease):
    global _last_card_id, _last_fired_at

    cfg = _get_config()
    if ease != 1:
        return

    from . import collector

    agains = collector.count_recent_agains(
        mw.col, card.id, int(cfg.get("timeframe_hours", 24))
    )
    model_name = collector.get_model_name(card)

    if not logic.should_trigger(cfg, ease, agains, card.type, model_name):
        return

    now = time.time()
    if card.id == _last_card_id and (now - _last_fired_at) < 5:
        return
    _last_card_id = card.id
    _last_fired_at = now

    _act_on_card(card, agains, cfg)


def open_options():
    from .options import open_options as _open

    _open()


def _init():
    gui_hooks.reviewer_did_answer_card.append(on_did_answer_card)

    # Custom config screen instead of the raw JSON editor.
    mw.addonManager.setConfigAction(__name__, open_options)

    # Tools-menu entry.
    action = QAction("Bury && Explain Options…", mw)
    qconnect(action.triggered, open_options)
    mw.form.menuTools.addAction(action)


if _ANKI:
    _init()
