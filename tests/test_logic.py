"""Unit tests for bury_explain.logic, pure Python, no Anki required.

Run from the repo root:  python3 -m unittest discover tests
"""

import os
import sys
import unittest
from urllib.parse import quote

# Make the pure-logic module importable without installing Anki. We add the
# add-on package dir directly so ``import logic`` never touches __init__.py
# (which would try to import aqt).
_LOGIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
    "bury_explain",
)
sys.path.insert(0, _LOGIC_DIR)

import logic  # noqa: E402


class CleanCardTextTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(logic.clean_card_text(""), "")
        self.assertEqual(logic.clean_card_text(None), "")

    def test_strips_html_tags(self):
        self.assertEqual(
            logic.clean_card_text("<b>Bonjour</b> <i>monde</i>"), "Bonjour monde"
        )

    def test_image_marker(self):
        self.assertEqual(
            logic.clean_card_text('Look: <img src="x.png">'), "Look: [image]"
        )

    def test_cloze_basic(self):
        self.assertEqual(
            logic.clean_card_text("The capital is {{c1::Paris}}."),
            "The capital is Paris.",
        )

    def test_cloze_with_hint(self):
        self.assertEqual(
            logic.clean_card_text("{{c2::Paris::city}} is the capital"),
            "Paris is the capital",
        )

    def test_entities_and_whitespace(self):
        self.assertEqual(
            logic.clean_card_text("a&nbsp;&amp;&nbsp;b   c"), "a & b c"
        )


class SelectCardFieldsTests(unittest.TestCase):
    def test_front_and_back(self):
        pairs = logic.select_card_fields({"Front": "What is 2+2?", "Back": "4"})
        self.assertEqual(pairs, [("Front", "What is 2+2?"), ("Back", "4")])

    def test_front_back_and_context(self):
        pairs = logic.select_card_fields(
            {"Front": "q", "Back": "a", "Extra": "extra info"}
        )
        self.assertEqual(pairs, [("Front", "q"), ("Back", "a"), ("Context", "extra info")])

    def test_alternate_field_names(self):
        pairs = logic.select_card_fields(
            {"Question": "q", "Answer": "a", "Source": "textbook p. 3"}
        )
        self.assertEqual(
            pairs, [("Front", "q"), ("Back", "a"), ("Context", "textbook p. 3")]
        )

    def test_skips_empty_fields(self):
        pairs = logic.select_card_fields({"Front": "q", "Back": "  ", "Extra": ""})
        self.assertEqual(pairs, [("Front", "q")])

    def test_falls_back_to_first_nonempty_field(self):
        pairs = logic.select_card_fields({"Kanji": "", "Reading": "inu"})
        self.assertEqual(pairs, [("Front", "inu")])

    def test_all_empty_returns_nothing(self):
        self.assertEqual(logic.select_card_fields({"Front": "", "Back": ""}), [])


class FormatCardFieldsTests(unittest.TestCase):
    def test_labels_front_and_back(self):
        text = logic.format_card_fields({"Front": "capital of France", "Back": "Paris"})
        self.assertEqual(text, "Front: capital of France\nBack: Paris")

    def test_empty_fields_returns_empty_string(self):
        self.assertEqual(logic.format_card_fields({}), "")

    def test_drops_lowest_priority_field_when_over_cap(self):
        text = logic.format_card_fields(
            {"Front": "q", "Back": "b" * 20, "Extra": "c" * 50}, max_chars=40
        )
        self.assertNotIn("Context:", text)
        self.assertIn("Back:", text)
        self.assertLessEqual(len(text), 40)

    def test_truncates_single_field_at_word_boundary(self):
        long_value = "word " * 100
        text = logic.format_card_fields({"Front": long_value}, max_chars=50)
        self.assertLessEqual(len(text), 50)
        self.assertFalse(text.endswith("wor"))

    def test_under_cap_untouched(self):
        text = logic.format_card_fields({"Front": "short", "Back": "answer"})
        self.assertEqual(text, "Front: short\nBack: answer")

    def test_cleans_html_before_capping(self):
        # A pasted base64 image dwarfs the cap in raw form, but cleans down
        # to a short "[image]" marker, so it should not push the answer out.
        heavy_front = (
            '<img src="data:image/png;base64,' + "A" * 3000 + '">'
            "What nerve innervates the diaphragm?"
        )
        text = logic.format_card_fields(
            {"Front": heavy_front, "Back": "Phrenic nerve, C3-C5", "Extra": "C3, 4, 5 keeps it alive"}
        )
        self.assertIn("Phrenic nerve, C3-C5", text)
        self.assertIn("What nerve innervates the diaphragm?", text)
        self.assertIn("C3, 4, 5 keeps it alive", text)
        self.assertNotIn("base64", text)
        self.assertLess(len(text), 300)

    def test_html_only_field_treated_as_empty(self):
        # A field that is pure non-image markup (no text, no image) cleans
        # down to nothing and should be skipped, not kept as an empty line.
        text = logic.format_card_fields(
            {"Front": "q", "Back": "  <br>  ", "Extra": "<div></div>"}
        )
        self.assertEqual(text, "Front: q")

    def test_preserves_newlines_between_labelled_lines(self):
        text = logic.format_card_fields({"Front": "q", "Back": "a", "Extra": "why"})
        self.assertEqual(text.count("\n"), 2)
        self.assertIn("Front: q\nBack: a\nContext: why", text)


class ShouldTriggerTests(unittest.TestCase):
    def cfg(self, **over):
        c = dict(logic.DEFAULT_CONFIG)
        c.update(over)
        return c

    def test_fires_at_threshold(self):
        self.assertTrue(
            logic.should_trigger(self.cfg(), ease=1, agains=3, card_type=2, model_name="Basic")
        )

    def test_below_threshold(self):
        self.assertFalse(
            logic.should_trigger(self.cfg(), ease=1, agains=2, card_type=2, model_name="Basic")
        )

    def test_above_threshold(self):
        self.assertTrue(
            logic.should_trigger(self.cfg(), ease=1, agains=9, card_type=2, model_name="Basic")
        )

    def test_disabled(self):
        self.assertFalse(
            logic.should_trigger(self.cfg(enabled=False), ease=1, agains=5, card_type=2, model_name="Basic")
        )

    def test_non_again_ease(self):
        for ease in (2, 3, 4):
            self.assertFalse(
                logic.should_trigger(self.cfg(), ease=ease, agains=9, card_type=2, model_name="Basic")
            )

    def test_ignore_new_cards(self):
        c = self.cfg(ignore_new_cards=True)
        self.assertFalse(
            logic.should_trigger(c, ease=1, agains=5, card_type=0, model_name="Basic")
        )
        self.assertFalse(
            logic.should_trigger(c, ease=1, agains=5, card_type=1, model_name="Basic")
        )
        # Review card still triggers.
        self.assertTrue(
            logic.should_trigger(c, ease=1, agains=5, card_type=2, model_name="Basic")
        )

    def test_ignore_new_off_allows_new(self):
        self.assertTrue(
            logic.should_trigger(self.cfg(ignore_new_cards=False), ease=1, agains=5, card_type=0, model_name="Basic")
        )

    def test_skip_image_cards(self):
        c = self.cfg(skip_image_cards=True)
        self.assertFalse(
            logic.should_trigger(c, ease=1, agains=5, card_type=2, model_name="Image Occlusion Enhanced")
        )
        self.assertFalse(
            logic.should_trigger(c, ease=1, agains=5, card_type=2, model_name="Basic image")
        )

    def test_skip_image_off(self):
        self.assertTrue(
            logic.should_trigger(self.cfg(skip_image_cards=False), ease=1, agains=5, card_type=2, model_name="Image Occlusion")
        )

    def test_custom_threshold(self):
        c = self.cfg(again_threshold=5)
        self.assertFalse(logic.should_trigger(c, ease=1, agains=4, card_type=2, model_name="Basic"))
        self.assertTrue(logic.should_trigger(c, ease=1, agains=5, card_type=2, model_name="Basic"))


class BuildPromptTests(unittest.TestCase):
    def test_good_template(self):
        out = logic.build_prompt("Failed {agains}x: {card}", 3, "photosynthesis")
        self.assertEqual(out, "Failed 3x: photosynthesis")

    def test_default_template(self):
        out = logic.build_prompt(logic.DEFAULT_PROMPT_TEMPLATE, 4, "mitochondria")
        self.assertIn("4 times", out)
        self.assertIn("mitochondria", out)

    def test_default_template_has_placeholders(self):
        self.assertIn("{agains}", logic.DEFAULT_PROMPT_TEMPLATE)
        self.assertIn("{card}", logic.DEFAULT_PROMPT_TEMPLATE)

    def test_default_template_audits_against_rules(self):
        self.assertIn("rule", logic.DEFAULT_PROMPT_TEMPLATE.lower())

    def test_default_template_grounds_and_hedges(self):
        lowered = logic.DEFAULT_PROMPT_TEMPLATE.lower()
        self.assertIn("card content below", lowered)
        self.assertIn("mark", lowered)
        self.assertIn("not sure", lowered)

    def test_default_template_under_length_ceiling(self):
        self.assertLess(len(logic.DEFAULT_PROMPT_TEMPLATE), 1800)

    def test_default_template_renders_rule_audit(self):
        out = logic.build_prompt(logic.DEFAULT_PROMPT_TEMPLATE, 3, "photosynthesis")
        self.assertIn("rule", out.lower())
        self.assertIn("photosynthesis", out)
        self.assertIn("3 times", out)

    def test_empty_card_text(self):
        out = logic.build_prompt("{card}", 3, "")
        self.assertIn("no extractable text", out)

    def test_malformed_unknown_placeholder(self):
        out = logic.build_prompt("Explain {nope} for {card}", 2, "x")
        self.assertIn("failed this card 2 times", out)
        self.assertIn("x", out)

    def test_malformed_stray_brace(self):
        out = logic.build_prompt("Broken { template {card}", 2, "x")
        self.assertIn("failed this card 2 times", out)

    def test_empty_template_falls_back_to_default(self):
        out = logic.build_prompt("", 5, "topic")
        self.assertIn("topic", out)
        self.assertIn("5 times", out)

    def test_html_heavy_card_survives_into_prompt(self):
        # Regression for the round-1 defect: a base64 <img> in Front used to
        # eat the whole length budget before cleaning ran, so Back and
        # Context got dropped and the model saw only "Front: <img". Cleaning
        # must happen before capping so the answer text reaches the prompt.
        heavy_front = (
            '<img src="data:image/png;base64,' + "A" * 3000 + '">'
            "What nerve innervates the diaphragm?"
        )
        card_text = logic.format_card_fields(
            {"Front": heavy_front, "Back": "Phrenic nerve, C3-C5", "Extra": "C3, 4, 5 keeps the diaphragm alive"}
        )
        out = logic.build_prompt(logic.DEFAULT_PROMPT_TEMPLATE, 3, card_text)
        self.assertIn("Phrenic nerve, C3-C5", out)
        self.assertIn("What nerve innervates the diaphragm?", out)
        self.assertNotIn("base64", out)


class ProviderUrlTests(unittest.TestCase):
    def test_chatgpt(self):
        self.assertEqual(
            logic.provider_url("chatgpt", "", "hello"),
            "https://chatgpt.com/?temporary-chat=true&q=hello",
        )

    def test_claude(self):
        self.assertEqual(
            logic.provider_url("claude", "", "hello"),
            "https://claude.ai/new?q=hello",
        )

    def test_perplexity(self):
        self.assertEqual(
            logic.provider_url("perplexity", "", "hi"),
            "https://www.perplexity.ai/search?q=hi",
        )

    def test_duckduckgo(self):
        self.assertEqual(
            logic.provider_url("duckduckgo", "", "hi"),
            "https://duckduckgo.com/?q=hi&ia=chat",
        )

    def test_gemini(self):
        self.assertEqual(
            logic.provider_url("gemini", "", "hi"),
            "https://gemini.google.com/app?q=hi",
        )

    def test_unknown_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_url("banana", "", "hi"),
            "https://chatgpt.com/?temporary-chat=true&q=hi",
        )

    def test_empty_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_url("", "", "hi"),
            "https://chatgpt.com/?temporary-chat=true&q=hi",
        )

    def test_custom(self):
        self.assertEqual(
            logic.provider_url("custom", "https://x.com/s?query={q}", "hi there"),
            "https://x.com/s?query=hi%20there",
        )

    def test_custom_without_placeholder_falls_back(self):
        self.assertEqual(
            logic.provider_url("custom", "https://x.com/no-placeholder", "hi"),
            "https://chatgpt.com/?temporary-chat=true&q=hi",
        )

    def test_encodes_ampersand_and_spaces(self):
        url = logic.provider_url("chatgpt", "", "a & b c")
        self.assertEqual(
            url, "https://chatgpt.com/?temporary-chat=true&q=a%20%26%20b%20c"
        )
        self.assertNotIn(" ", url)
        self.assertNotIn("q=a &", url)

    def test_encodes_unicode(self):
        url = logic.provider_url("chatgpt", "", "café ☕")
        self.assertEqual(
            url,
            "https://chatgpt.com/?temporary-chat=true&q=" + quote("café ☕", safe=""),
        )
        self.assertIn("%", url)


class ProviderHomeUrlTests(unittest.TestCase):
    def test_chatgpt(self):
        self.assertEqual(
            logic.provider_home_url("chatgpt", ""),
            "https://chatgpt.com/?temporary-chat=true",
        )

    def test_claude(self):
        self.assertEqual(logic.provider_home_url("claude", ""), "https://claude.ai/new")

    def test_perplexity(self):
        self.assertEqual(
            logic.provider_home_url("perplexity", ""), "https://www.perplexity.ai"
        )

    def test_duckduckgo(self):
        self.assertEqual(
            logic.provider_home_url("duckduckgo", ""), "https://duckduckgo.com"
        )

    def test_gemini(self):
        self.assertEqual(
            logic.provider_home_url("gemini", ""), "https://gemini.google.com/app"
        )

    def test_unknown_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_home_url("banana", ""),
            "https://chatgpt.com/?temporary-chat=true",
        )

    def test_empty_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_home_url("", ""), "https://chatgpt.com/?temporary-chat=true"
        )

    def test_custom_uses_scheme_and_host(self):
        self.assertEqual(
            logic.provider_home_url("custom", "https://example.com/chat?q={q}"),
            "https://example.com",
        )

    def test_custom_with_port(self):
        self.assertEqual(
            logic.provider_home_url("custom", "http://localhost:8080/s?q={q}"),
            "http://localhost:8080",
        )

    def test_custom_without_host_falls_back(self):
        self.assertEqual(
            logic.provider_home_url("custom", "not-a-url"),
            "https://chatgpt.com/?temporary-chat=true",
        )

    def test_custom_empty_template_falls_back(self):
        self.assertEqual(
            logic.provider_home_url("custom", ""),
            "https://chatgpt.com/?temporary-chat=true",
        )

    def test_case_insensitive(self):
        self.assertEqual(
            logic.provider_home_url("ChatGPT", ""),
            "https://chatgpt.com/?temporary-chat=true",
        )


class ProviderDisplayNameTests(unittest.TestCase):
    def test_known_providers(self):
        self.assertEqual(logic.provider_display_name("chatgpt"), "ChatGPT")
        self.assertEqual(logic.provider_display_name("claude"), "Claude")
        self.assertEqual(logic.provider_display_name("gemini"), "Gemini")
        self.assertEqual(logic.provider_display_name("custom"), "Custom")

    def test_case_insensitive(self):
        self.assertEqual(logic.provider_display_name("DuckDuckGo"), "DuckDuckGo")

    def test_unknown_titlecased(self):
        self.assertEqual(logic.provider_display_name("banana"), "Banana")

    def test_empty_falls_back(self):
        self.assertEqual(logic.provider_display_name(""), "AI")


class DefaultConfigTests(unittest.TestCase):
    def test_add_tag_default_true(self):
        self.assertTrue(logic.DEFAULT_CONFIG["add_tag"])


if __name__ == "__main__":
    unittest.main()
