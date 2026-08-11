"""Pure-Python core logic for the Bury Explain add-on.

This module deliberately imports nothing from ``anki`` or ``aqt`` so it can be
unit-tested with a plain ``python3 -m unittest`` run and reused anywhere.
"""

import re
from urllib.parse import quote, urlsplit

# Card queue/type constants (mirrors Anki's values without importing anki).
TYPE_NEW = 0
TYPE_LEARNING = 1

# Default prompt template (ported from the owner's bury_explain_bridge).
# Also audits the card against Wozniak's "Twenty rules of formulating
# knowledge" so failed cards get concrete rewrite suggestions in addition
# to an explanation. The rule list is embedded (compact, <=6 words each) so the
# AI is grounded even without web access. Also tells the model to ground its
# answer in the card content, mark anything it adds, and admit uncertainty
# rather than invent. Keep under ~1800 chars: this prompt travels
# URL-encoded in a query param.
DEFAULT_PROMPT_TEMPLATE = (
    "I just failed this Anki card {agains} times in a row. Help me actually "
    "understand it. Base your answer on the card content below, mark "
    "clearly anything you add beyond it, and say you are not sure rather "
    "than guess if the card is ambiguous or the answer is not derivable "
    "from what is given:\n\n"
    "1. Explain the core concept simply in 1-2 sentences.\n"
    "2. Give me one mnemonic or memory hook.\n"
    "3. Tell me what I'm most likely confusing this with.\n\n"
    "Then audit this card against Wozniak's 20 rules of formulating "
    "knowledge. For each rule it violates, output: failed rule #N (short "
    "rule name), fix: <concrete rewritten card text>. If it passes, say "
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

# Shipped defaults. build.py generates config.json from this dict, so the
# two never drift.
DEFAULT_CONFIG = {
    "enabled": True,
    "again_threshold": 3,
    "timeframe_hours": 24,
    "bury": True,
    "add_tag": True,
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
    "chatgpt": "https://chatgpt.com/?temporary-chat=true&q={q}",
    "claude": "https://claude.ai/new?q={q}",
    "perplexity": "https://www.perplexity.ai/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}&ia=chat",
    "gemini": "https://gemini.google.com/app?q={q}",
}

# Provider -> base/home page (no query) used by the manual "AI" toolbar toggle.
_PROVIDER_HOMES = {
    "chatgpt": "https://chatgpt.com/?temporary-chat=true",
    "claude": "https://claude.ai/new",
    "perplexity": "https://www.perplexity.ai",
    "duckduckgo": "https://duckduckgo.com",
    "gemini": "https://gemini.google.com/app",
}

# Provider -> human-readable name shown in the sidebar header.
_PROVIDER_NAMES = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "perplexity": "Perplexity",
    "duckduckgo": "DuckDuckGo",
    "gemini": "Gemini",
    "custom": "Custom",
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


# Field-name candidates, in priority order, for each side of the card.
QUESTION_FIELD_NAMES = ("Front", "Text", "Question", "Expression")
ANSWER_FIELD_NAMES = ("Back", "Answer", "Meaning")
CONTEXT_FIELD_NAMES = ("Extra", "Back Extra", "Notes", "Source")

# Total labelled card text is capped near this length so the URL-encoded
# prompt stays viable.
MAX_CARD_TEXT_CHARS = 1200


def _first_named_field(fields, names):
    """Return the first field, among the given names, that is non-empty once
    HTML/cloze markup is stripped, or None.

    The value is returned already cleaned via ``clean_card_text``, so markup
    weight never reaches the caller and never counts against the length cap.
    """
    for name in names:
        if name in fields:
            value = fields[name]
            if value:
                cleaned = clean_card_text(value)
                if cleaned:
                    return cleaned
    return None


def select_card_fields(fields):
    """Pick the question, answer, and context text out of a note's fields.

    ``fields`` is a plain dict of field name to field value (as stored, HTML
    and all). Each candidate value is cleaned with ``clean_card_text`` before
    it is judged empty or non-empty, so a field that is pure markup (a pasted
    image, a styled wrapper) is treated as empty rather than as content.
    Returns a list of ``(label, value)`` pairs, already cleaned, in priority
    order (Front, then Back, then Context), skipping any side with no match.
    When none of the known field names match anything, falls back to the
    first field that is non-empty after cleaning, labelled "Front", matching
    the add-on's original single-field behaviour.
    """
    front = _first_named_field(fields, QUESTION_FIELD_NAMES)
    back = _first_named_field(fields, ANSWER_FIELD_NAMES)
    context = _first_named_field(fields, CONTEXT_FIELD_NAMES)

    pairs = []
    if front:
        pairs.append(("Front", front))
    if back:
        pairs.append(("Back", back))
    if context:
        pairs.append(("Context", context))

    if not pairs:
        for value in fields.values():
            if value:
                cleaned = clean_card_text(value)
                if cleaned:
                    pairs.append(("Front", cleaned))
                    break

    return pairs


def format_card_fields(fields, max_chars=MAX_CARD_TEXT_CHARS):
    """Select and label a note's fields, capped at ``max_chars`` total.

    Produces lines like ``Front: ...`` then ``Back: ...`` then
    ``Context: ...`` so the model can tell the sides apart. Each field value
    is cleaned of HTML/cloze markup (via ``select_card_fields``) before the
    cap is applied, so the budget governs real content rather than markup
    weight, and the newlines between labelled lines are the last whitespace
    transform applied. No further whitespace collapsing happens after this
    function returns, so the line structure survives into the prompt. If the
    labelled text runs over the cap, the lowest-priority fields are dropped
    first (Context, then Back). If even the single remaining field is too
    long, it is truncated at the last word boundary within the budget rather
    than mid-word.
    """
    pairs = select_card_fields(fields)
    if not pairs:
        return ""

    def render(p):
        return "\n".join(f"{label}: {value}" for label, value in p)

    text = render(pairs)
    while len(text) > max_chars and len(pairs) > 1:
        pairs = pairs[:-1]
        text = render(pairs)

    if len(text) <= max_chars:
        return text

    # Still too long with a single field: truncate at a word boundary.
    label, value = pairs[0]
    prefix = f"{label}: "
    budget = max(max_chars - len(prefix), 0)
    truncated = value[:budget]
    if " " in truncated and len(truncated) < len(value):
        truncated = truncated.rsplit(" ", 1)[0]
    return f"{prefix}{truncated}"


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


def provider_home_url(provider, custom_template):
    """Return the provider's base/home page (no query) for the manual toggle.

    For ``custom`` the scheme+host of the user's template is used. Unknown or
    empty providers (and a custom template with no usable host) fall back to
    the ChatGPT home page.
    """
    key = (provider or "").strip().lower()

    if key == "custom":
        if custom_template:
            parts = urlsplit(custom_template.strip())
            if parts.scheme and parts.netloc:
                return f"{parts.scheme}://{parts.netloc}"
        return _PROVIDER_HOMES["chatgpt"]

    return _PROVIDER_HOMES.get(key, _PROVIDER_HOMES["chatgpt"])


def provider_display_name(provider):
    """Human-readable provider name for the sidebar header ("AI · <name>")."""
    key = (provider or "").strip().lower()
    if key in _PROVIDER_NAMES:
        return _PROVIDER_NAMES[key]
    if not key:
        return "AI"
    return provider.strip().title()
