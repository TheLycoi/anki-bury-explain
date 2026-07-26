"""Pure-Python core logic for the Bury & Explain add-on.

This module deliberately imports nothing from ``anki`` or ``aqt`` so it can be
unit-tested with a plain ``python3 -m unittest`` run and reused anywhere.
"""

import re
from urllib.parse import quote

# Card queue/type constants (mirrors Anki's values without importing anki).
TYPE_NEW = 0
TYPE_LEARNING = 1

# Default prompt template (ported from the owner's bury_explain_bridge).
# Also audits the card against Wozniak's "Twenty rules of formulating
# knowledge" so failed cards get concrete rewrite suggestions, not just an
# explanation. The rule list is embedded (compact, <=6 words each) so the
# AI is grounded even without web access. Keep under ~1500 chars: this
# prompt travels URL-encoded in a query param.
DEFAULT_PROMPT_TEMPLATE = (
    "I just failed this Anki card {agains} times in a row. Help me actually "
    "understand it:\n\n"
    "1. Explain the core concept simply in 1-2 sentences.\n"
    "2. Give me one mnemonic or memory hook.\n"
    "3. Tell me what I'm most likely confusing this with.\n\n"
    "Then audit this card against Wozniak's 20 rules of formulating "
    "knowledge. For each rule it violates, output: failed rule #N (short "
    "rule name) — fix: <concrete rewritten card text>. If it passes, say "
    "'card formulation OK'. Rules: "
    "1 do not learn what you don't understand, 2 learn before you memorize, "
    "3 build upon basics, 4 minimum information principle, 5 cloze deletion "
    "is easy, 6 use imagery, 7 use mnemonics, 8 graphic deletion, 9 avoid "
    "sets, 10 avoid enumerations, 11 combat interference, 12 optimize "
    "wording, 13 refer to other memories, 14 personalize with examples, "
    "15 rely on emotional states, 16 context cues simplify wording, "
    "17 redundancy can help, 18 provide sources, 19 provide date stamping, "
    "20 prioritize.\n\n"
    "Card content: {card}"
)

# Shipped defaults. config.json is generated to match this dict.
DEFAULT_CONFIG = {
    "enabled": True,
    "again_threshold": 3,
    "timeframe_hours": 24,
    "bury": True,
    "tag": "buryexplain-leech",
    "ignore_new_cards": False,
    "skip_image_cards": True,
    "show_notification": True,
    "provider": "chatgpt",
    "custom_url": "",
    "open_in": "sidebar",
    "prompt_template": DEFAULT_PROMPT_TEMPLATE,
}

# Provider -> URL template. ``{q}`` is replaced with the URL-encoded prompt.
_PROVIDER_TEMPLATES = {
    "chatgpt": "https://chatgpt.com/?q={q}",
    "claude": "https://claude.ai/new?q={q}",
    "perplexity": "https://www.perplexity.ai/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}&ia=chat",
    "google_ai": "https://www.google.com/search?udm=50&q={q}",
}


def clean_card_text(text):
    """Strip HTML, image refs, and cloze syntax for a cleaner prompt."""
    if not text:
        return ""
    # Replace images with a marker so the prompt notes an image was present.
    text = re.sub(r"<img[^>]*>", "[image]", text)
    # Reveal cloze answers: {{c1::answer::hint}} -> answer
    text = re.sub(r"\{\{c\d+::([^:}]*?)(?:::[^}]*)?\}\}", r"\1", text)
    # Strip remaining HTML tags.
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode a handful of common HTML entities.
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def should_trigger(cfg, ease, agains, card_type, model_name):
    """Decide whether the bury + explain action should fire for this answer.

    Args:
        cfg: the merged add-on config dict.
        ease: 1-4 (Again/Hard/Good/Easy). Only ease == 1 can trigger.
        agains: count of recent "Again" presses (already includes this one).
        card_type: Anki card.type (0 new, 1 learning, 2 review, 3 relearning).
        model_name: the note type / model name (for image-card skipping).
    """
    if not cfg.get("enabled", True):
        return False

    # Only ever act on a failed ("Again") answer.
    if ease != 1:
        return False

    if cfg.get("ignore_new_cards", False) and card_type <= TYPE_LEARNING:
        return False

    if cfg.get("skip_image_cards", True):
        lowered = (model_name or "").lower()
        if "image" in lowered or "occlusion" in lowered:
            return False

    threshold = int(cfg.get("again_threshold", 3))
    return agains >= threshold


def build_prompt(template, agains, card_text):
    """Format the prompt template, falling back safely on a bad template."""
    if not card_text:
        card_text = "(card has no extractable text)"
    if not template:
        template = DEFAULT_PROMPT_TEMPLATE
    try:
        return template.format(agains=agains, card=card_text)
    except (KeyError, IndexError, ValueError):
        # A user-broken template (unknown placeholder, stray brace, etc.)
        # should never stop the add-on from asking for help.
        return (
            f"I just failed this card {agains} times. Explain it simply and "
            f"give me a memory hook.\n\nCard: {card_text}"
        )


def provider_url(provider, custom_template, prompt):
    """Build the destination URL for the given provider and prompt.

    Unknown/empty providers fall back to ChatGPT. ``custom`` requires the
    user's template to contain a ``{q}`` placeholder; otherwise it falls back
    to ChatGPT too.
    """
    encoded = quote(prompt or "", safe="")

    key = (provider or "").strip().lower()

    if key == "custom":
        if custom_template and "{q}" in custom_template:
            return custom_template.replace("{q}", encoded)
        key = "chatgpt"

    template = _PROVIDER_TEMPLATES.get(key, _PROVIDER_TEMPLATES["chatgpt"])
    return template.replace("{q}", encoded)
