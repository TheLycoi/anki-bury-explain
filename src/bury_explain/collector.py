"""Thin Anki-collection layer for Bury & Explain.

These helpers touch the live collection / note objects. They are intentionally
tiny and free of UI so the interesting decision-making stays in ``logic.py``.
"""

import time


def count_recent_agains(col, card_id, timeframe_hours):
    """Count "Again" (ease=1) reviews for a card within the timeframe.

    ``revlog.id`` is the review timestamp in milliseconds. By the time the
    reviewer_did_answer_card hook fires, the current answer is already logged,
    so the returned count includes the press that triggered this call.
    """
    threshold_ms = int((time.time() - timeframe_hours * 3600) * 1000)
    try:
        return (
            col.db.scalar(
                "select count(*) from revlog where cid = ? and ease = 1 and id > ?",
                card_id,
                threshold_ms,
            )
            or 0
        )
    except Exception:
        return 0


def get_card_text(card):
    """Extract the most relevant text from a card (front field, then fallbacks)."""
    note = card.note()
    for field_name in ("Front", "Text", "Question", "Expression"):
        if field_name in note:
            value = note[field_name]
            if value and value.strip():
                return value
    for field_value in note.fields:
        if field_value and field_value.strip():
            return field_value
    return ""


def get_model_name(card):
    """Return the note type / model name, or "" if unavailable."""
    try:
        return (card.note().note_type() or {}).get("name", "") or ""
    except Exception:
        return ""
