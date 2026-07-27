"""Bury Explain: AI help when you keep failing a card.

After N "Again" presses within a time window, the card is auto-buried (and
optionally tagged) and an AI sidebar opens with the question pre-searched. A
plain-text "AI" button on the top toolbar toggles the same sidebar manually.
Everything is driven by one minimalist options dialog.

Original code. Inspired by Anki Terminator and AJT Mortician (behaviour only),
building on the owner's own bury_explain_bridge.
"""

import sys
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


def _open_help(url, cfg):
    """Route the built URL to the sidebar or the system browser."""
    if cfg.get("open_in", "sidebar") == "sidebar":
        from . import sidebar

        label = logic.provider_display_name(cfg.get("provider", "chatgpt"))
        sidebar.open_url(url, label)
    else:
        openLink(url)


def _act_on_card(card, agains, cfg):
    """Bury + optionally tag the card, then open AI help.

    The whole trigger path is wrapped so it can never fail silently: any
    exception surfaces as a tooltip and a stderr print, and the AI still
    reaches the user via a system-browser fallback.
    """
    from . import collector

    # Build the URL first so it is always available for the browser fallback.
    card_text = logic.clean_card_text(collector.get_card_text(card))
    prompt = logic.build_prompt(cfg.get("prompt_template", ""), agains, card_text)
    url = logic.provider_url(cfg.get("provider", "chatgpt"), cfg.get("custom_url", ""), prompt)

    try:
        # Bury.
        if cfg.get("bury", True):
            try:
                mw.col.sched.bury_cards([card.id], manual=False)
            except TypeError:
                mw.col.sched.bury_cards([card.id])
            except Exception as exc:
                print(f"[bury_explain] bury failed: {exc}", file=sys.stderr)

        # Optional tag (only when enabled and a non-empty tag is set).
        tag = cfg.get("tag", "")
        if cfg.get("add_tag", True) and tag:
            try:
                note = card.note()
                if not note.has_tag(tag):
                    note.add_tag(tag)
                    mw.col.update_note(note)
            except Exception as exc:
                print(f"[bury_explain] tag failed: {exc}", file=sys.stderr)

        _open_help(url, cfg)

        if cfg.get("show_notification", True):
            tooltip(
                f"Bury Explain: buried after {agains} fails, asking AI",
                period=3000,
            )
    except Exception as exc:
        msg = f"Bury Explain error: {exc}"
        print(msg, file=sys.stderr)
        try:
            tooltip(msg, period=5000)
        except Exception:
            pass
        # The AI must reach the user one way or another.
        try:
            openLink(url)
        except Exception as exc2:  # pragma: no cover
            print(f"[bury_explain] browser fallback failed: {exc2}", file=sys.stderr)


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


def _toggle_sidebar():
    """Top-toolbar "AI" button: toggle the sidebar (open at provider home)."""
    try:
        from . import sidebar

        if sidebar.is_visible():
            sidebar.hide_dock()
            return

        cfg = _get_config()
        provider = cfg.get("provider", "chatgpt")
        url = logic.provider_home_url(provider, cfg.get("custom_url", ""))
        sidebar.open_url(url, logic.provider_display_name(provider))
    except Exception as exc:
        msg = f"Bury Explain error: {exc}"
        print(msg, file=sys.stderr)
        try:
            tooltip(msg, period=5000)
        except Exception:
            pass


def _on_top_toolbar_init(links, toolbar):
    """Add a plain-text (no image/icon) "AI" link to the top toolbar."""
    links.append(
        toolbar.create_link(
            "bury_explain_ai",
            "AI",
            _toggle_sidebar,
            tip="Toggle the Bury Explain AI sidebar",
            id="bury_explain_ai",
        )
    )


def open_options():
    from .options import open_options as _open

    _open()


def _init():
    gui_hooks.reviewer_did_answer_card.append(on_did_answer_card)
    gui_hooks.top_toolbar_did_init_links.append(_on_top_toolbar_init)

    # Custom config screen instead of the raw JSON editor.
    mw.addonManager.setConfigAction(__name__, open_options)

    # Tools-menu entry.
    action = QAction("Bury Explain Options…", mw)
    qconnect(action.triggered, open_options)
    mw.form.menuTools.addAction(action)


if _ANKI:
    _init()
