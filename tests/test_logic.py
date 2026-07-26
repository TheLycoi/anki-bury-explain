"""Unit tests for bury_explain.logic — pure Python, no Anki required.

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


class ProviderUrlTests(unittest.TestCase):
    def test_chatgpt(self):
        self.assertEqual(
            logic.provider_url("chatgpt", "", "hello"),
            "https://chatgpt.com/?q=hello",
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

    def test_google_ai(self):
        self.assertEqual(
            logic.provider_url("google_ai", "", "hi"),
            "https://www.google.com/search?udm=50&q=hi",
        )

    def test_unknown_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_url("banana", "", "hi"),
            "https://chatgpt.com/?q=hi",
        )

    def test_empty_falls_back_to_chatgpt(self):
        self.assertEqual(
            logic.provider_url("", "", "hi"),
            "https://chatgpt.com/?q=hi",
        )

    def test_custom(self):
        self.assertEqual(
            logic.provider_url("custom", "https://x.com/s?query={q}", "hi there"),
            "https://x.com/s?query=hi%20there",
        )

    def test_custom_without_placeholder_falls_back(self):
        self.assertEqual(
            logic.provider_url("custom", "https://x.com/no-placeholder", "hi"),
            "https://chatgpt.com/?q=hi",
        )

    def test_encodes_ampersand_and_spaces(self):
        url = logic.provider_url("chatgpt", "", "a & b c")
        self.assertEqual(url, "https://chatgpt.com/?q=a%20%26%20b%20c")
        self.assertNotIn(" ", url)
        self.assertNotIn("q=a &", url)

    def test_encodes_unicode(self):
        url = logic.provider_url("chatgpt", "", "café ☕")
        self.assertEqual(url, "https://chatgpt.com/?q=" + quote("café ☕", safe=""))
        self.assertIn("%", url)


class ProviderHomeUrlTests(unittest.TestCase):
    def test_chatgpt(self):
        self.assertEqual(logic.provider_home_url("chatgpt", ""), "https://chatgpt.com")

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

    def test_google_ai(self):
        self.assertEqual(
            logic.provider_home_url("google_ai", ""), "https://www.google.com"
        )

    def test_unknown_falls_back_to_chatgpt(self):
        self.assertEqual(logic.provider_home_url("banana", ""), "https://chatgpt.com")

    def test_empty_falls_back_to_chatgpt(self):
        self.assertEqual(logic.provider_home_url("", ""), "https://chatgpt.com")

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
            logic.provider_home_url("custom", "not-a-url"), "https://chatgpt.com"
        )

    def test_custom_empty_template_falls_back(self):
        self.assertEqual(logic.provider_home_url("custom", ""), "https://chatgpt.com")

    def test_case_insensitive(self):
        self.assertEqual(
            logic.provider_home_url("ChatGPT", ""), "https://chatgpt.com"
        )


class ProviderDisplayNameTests(unittest.TestCase):
    def test_known_providers(self):
        self.assertEqual(logic.provider_display_name("chatgpt"), "ChatGPT")
        self.assertEqual(logic.provider_display_name("claude"), "Claude")
        self.assertEqual(logic.provider_display_name("google_ai"), "Google AI")
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
