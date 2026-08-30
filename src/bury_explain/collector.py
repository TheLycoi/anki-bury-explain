"""Thin Anki-collection layer for Bury Explain.

These helpers touch the live collection / note objects. They are intentionally
tiny and free of UI so the interesting decision-making stays in ``logic.py``.
"""

import time

from . import logic


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
    """Extract labelled, markup-cleaned question, answer, and context text
    from a card's note.

    The field-name matching, HTML/cloze cleaning, and formatting live in
    ``logic.format_card_fields`` so they stay pure and testable; this
    function's only job is reading the real note object safely. The
    returned text is already clean and ready to drop into a prompt as-is.
    """
    try:
        note = card.note()
        fields = {name: note[name] for name in note.keys()}
        return logic.format_card_fields(fields)
    except Exception:
        return ""


def get_model_name(card):
    """Return the note type / model name, or "" if unavailable."""
    try:
        return (card.note().note_type() or {}).get("name", "") or ""
    except Exception:
        return ""
