#!/usr/bin/env python3
"""Exact behavior tests for Voiceprint's deterministic Unicode hygiene."""

import io
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest
from unittest import mock

import scripts.text_hygiene as text_hygiene
from scripts.text_hygiene import clean_text, inspect_text


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "text_hygiene.py"
EXPECTED_INPUT_CAP = 4 * 1024 * 1024
UNICODE_DATA_DIR = os.environ.get("VOICEPRINT_UNICODE_DATA_DIR")
VARIATION_REASON = "{}-presentation selector in a pinned Emoji 17 variation sequence"
TAG_REASON = "part of a pinned Emoji 17 tag sequence"
NUMBER_SPACE_REASON = "no-break space inside a number"
UNIT_SPACE_REASON = "no-break space between a number and a unit or symbol"
FRENCH_SPACE_REASON = "no-break space at French punctuation or quotation marks"
CJK_SPACE_REASON = "ideographic space beside CJK text"
SETS_DIRECTION_REASON = "directional mark that sets its paragraph's direction"
CHANGES_DISPLAY_REASON = (
    "directional mark that changes the order or mirroring of nearby characters"
)
HEBREW_SHALOM = "\u05e9\u05dc\u05d5\u05dd"
HEBREW_OLAM = "\u05e2\u05d5\u05dc\u05dd"


def finding(manifest, code_point, action):
    """Return one exact finding from a manifest."""
    return next(
        item
        for item in manifest["findings"]
        if item["code_point"] == code_point and item["action"] == action
    )


def hex_sequence(text):
    """Render text as space-separated code points for readable failures."""
    return " ".join(f"{ord(character):04X}" for character in text)


def kept_marks(manifest):
    """Offsets of the directional marks a manifest keeps."""
    return sorted(
        offset
        for item in manifest["findings"]
        if item["action"] == "preserve"
        and item["code_point"] in ("U+200E", "U+200F", "U+061C")
        for offset in item["offsets"]
    )


def bracket_pairs(text):
    """The bracket pairs of text by offset, in order of their opening brackets."""
    positions, partners = text_hygiene._bracket_structure(text, 0, len(text))
    return [
        (positions[index], positions[partner])
        for index, partner in enumerate(partners)
        if partner > index
    ]


class TextHygieneApiTests(unittest.TestCase):
    def test_removes_each_hidden_control_family(self):
        source = (
            "a\u00adb\u200bc\u202ed\U000e0067e\ufff9f\u2060g\u200dh"
            "\ufe0fi\U000e0100j"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "abcdefghij")
        self.assertEqual(
            [(item["code_point"], item["action"]) for item in manifest["findings"]],
            [
                ("U+00AD", "remove"),
                ("U+200B", "remove"),
                ("U+202E", "remove"),
                ("U+E0067", "remove"),
                ("U+FFF9", "remove"),
                ("U+2060", "remove"),
                ("U+200D", "remove"),
                ("U+FE0F", "remove"),
                ("U+E0100", "remove"),
            ],
        )
        self.assertEqual(
            manifest["summary"],
            {
                "detected": 9,
                "removed": 9,
                "normalized": 0,
                "preserved": 0,
                "actionable": 9,
            },
        )

    def test_normalizes_unicode_spaces_only(self):
        source = "a\u00a0b\u2007c\u202fd\u3000e\tf\r\ng\nh"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "a b c d e\tf\r\ng\nh")
        self.assertEqual(manifest["summary"]["normalized"], 4)
        self.assertEqual(manifest["summary"]["removed"], 0)
        self.assertNotIn("U+0009", [item["code_point"] for item in manifest["findings"]])
        self.assertNotIn("U+000A", [item["code_point"] for item in manifest["findings"]])
        self.assertNotIn("U+000D", [item["code_point"] for item in manifest["findings"]])

    def test_aggregates_stable_offsets_in_first_seen_order(self):
        source = "\u00adA\u200bB\u00adC\u200b" + ("x\u00ad" * 10)

        first = inspect_text(source)
        second = inspect_text(source)

        self.assertEqual(first, second)
        self.assertEqual(
            [item["code_point"] for item in first["findings"]],
            ["U+00AD", "U+200B"],
        )
        self.assertEqual(
            finding(first, "U+00AD", "remove"),
            {
                "code_point": "U+00AD",
                "name": "SOFT HYPHEN",
                "action": "remove",
                "count": 12,
                "offsets": [0, 4, 8, 10, 12, 14, 16, 18, 20, 22],
            },
        )
        self.assertEqual(finding(first, "U+200B", "remove")["offsets"], [2, 6])

    def test_preserves_complex_script_joiners_with_reason(self):
        source = (
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 "
            "\u0915\u094d\u200d\u0937"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["summary"]["actionable"], 0)
        self.assertEqual(manifest["summary"]["preserved"], 2)
        self.assertEqual(
            finding(manifest, "U+200C", "preserve")["reason"],
            "required by surrounding complex-script orthography",
        )
        self.assertEqual(
            finding(manifest, "U+200D", "preserve")["reason"],
            "required by surrounding complex-script orthography",
        )

    def test_preserves_mongolian_variation_selector(self):
        source = "\u1820\u180b"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+180B", "preserve")["reason"],
            "Mongolian selector after Mongolian base",
        )

    def test_preserves_mongolian_vowel_separator_between_mongolian_letters(self):
        source = "\u182c\u180e\u1820"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["summary"]["actionable"], 0)
        self.assertEqual(
            finding(manifest, "U+180E", "preserve")["reason"],
            "Mongolian vowel separator between Mongolian letters",
        )

    def test_removes_mongolian_vowel_separator_outside_mongolian_words(self):
        source = "a\u180eb \u182c\u180e"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "ab \u182c")
        self.assertEqual(finding(manifest, "U+180E", "remove")["count"], 2)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_removes_repeated_mongolian_variation_selectors(self):
        source = "\u1820\u180b\u180c\u180d"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\u1820\u180b")
        self.assertEqual(finding(manifest, "U+180B", "preserve")["offsets"], [1])
        self.assertEqual(manifest["summary"]["removed"], 2)

    def test_removes_unassigned_default_ignorable_code_points(self):
        source = (
            "a\u2065b\U000e0000c\U000e0002d\U000e0080e"
            "\ufff0f\U000e0fffg"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "abcdefg")
        self.assertEqual(manifest["summary"]["removed"], 6)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_reports_invisible_default_ignorable_letters_and_marks(self):
        source = "a\u034fb\u115fc\u1160d\u17b4e\u17b5f\u3164g\uffa0h"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["summary"]["preserved"], 7)
        self.assertEqual(manifest["summary"]["actionable"], 0)
        self.assertEqual(
            {item["reason"] for item in manifest["findings"]},
            {"invisible default-ignorable character preserved conservatively"},
        )

    def test_removes_supplementary_selector_after_arabic(self):
        source = "\u0627\U000e0100"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\u0627")
        self.assertEqual(finding(manifest, "U+E0100", "remove")["count"], 1)

    def test_preserves_valid_emoji_sequences_written_as_escapes(self):
        source = "\U0001f469\u200d\U0001f4bb and \u2764\ufe0f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["summary"]["actionable"], 0)
        self.assertEqual(
            finding(manifest, "U+200D", "preserve")["reason"],
            "matches a pinned Emoji 17 pair",
        )
        self.assertEqual(
            finding(manifest, "U+FE0F", "preserve")["reason"],
            VARIATION_REASON.format("emoji"),
        )

    def test_preserves_person_profession_with_skin_tone_modifier(self):
        source = "\U0001f469\U0001f3fd\u200d\U0001f4bb"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+200D", "preserve")["reason"],
            "matches a pinned Emoji 17 pair",
        )

    def test_preserves_standardized_family_sequence(self):
        source = "\U0001f468\u200d\U0001f469\u200d\U0001f467"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        zwj_findings = [
            item
            for item in manifest["findings"]
            if item["code_point"] == "U+200D" and item["action"] == "preserve"
        ]
        self.assertEqual(len(zwj_findings), 1)
        self.assertEqual(zwj_findings[0]["count"], 2)

    def test_preserves_standardized_rainbow_flag_sequence(self):
        source = "\U0001f3f3\ufe0f\u200d\U0001f308"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+200D", "preserve")["reason"],
            "matches a pinned Emoji 17 pair",
        )

    def test_preserves_official_unicode_17_wrestling_sequence(self):
        source = (
            "\U0001f468\U0001f3fb\u200d\U0001faef\u200d"
            "\U0001f468\U0001f3fc"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(finding(manifest, "U+200D", "preserve")["count"], 2)

    def test_preserves_head_shaking_sequences_with_trailing_selector(self):
        source = "\U0001f642\u200d\u2194\ufe0f \U0001f642\u200d\u2195\ufe0f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["summary"]["actionable"], 0)
        self.assertEqual(finding(manifest, "U+200D", "preserve")["count"], 2)
        self.assertEqual(finding(manifest, "U+FE0F", "preserve")["count"], 2)

    def test_every_pinned_emoji_pair_preserves_zwj(self):
        for previous_base, next_base in sorted(text_hygiene._EMOJI_ZWJ_PAIRS):
            with self.subTest(previous_base=previous_base, next_base=next_base):
                source = chr(previous_base) + "\u200d" + chr(next_base)

                cleaned, manifest = clean_text(source)

                self.assertEqual(cleaned, source)
                self.assertEqual(
                    finding(manifest, "U+200D", "preserve")["count"],
                    1,
                )

    def test_reports_text_and_emoji_presentation_selectors(self):
        text_manifest = inspect_text("\u2764\ufe0e")
        emoji_manifest = inspect_text("\u2764\ufe0f")

        self.assertEqual(
            finding(text_manifest, "U+FE0E", "preserve")["reason"],
            VARIATION_REASON.format("text"),
        )
        self.assertEqual(
            finding(emoji_manifest, "U+FE0F", "preserve")["reason"],
            VARIATION_REASON.format("emoji"),
        )

    def test_preserves_presentation_sequences_outside_the_emoji_blocks(self):
        source = "\u00a9\ufe0f \u2122\ufe0f \u2b05\ufe0f \u25b6\ufe0e \u3297\ufe0f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(finding(manifest, "U+FE0F", "preserve")["count"], 4)
        self.assertEqual(finding(manifest, "U+FE0E", "preserve")["count"], 1)
        self.assertEqual(manifest["summary"]["actionable"], 0)

    def test_preserves_keycap_sequences(self):
        source = "#\ufe0f\u20e3 *\ufe0f\u20e3 0\ufe0f\u20e3 9\ufe0f\u20e3"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+FE0F", "preserve"),
            {
                "code_point": "U+FE0F",
                "name": "VARIATION SELECTOR-16",
                "action": "preserve",
                "count": 4,
                "offsets": [1, 5, 9, 13],
                "reason": VARIATION_REASON.format("emoji"),
            },
        )

    def test_removes_selector_after_keycap_base_without_keycap(self):
        source = "call 5\ufe0f55 or #\ufe0f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "call 555 or #")
        self.assertEqual(finding(manifest, "U+FE0F", "remove")["offsets"], [6, 14])
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_every_pinned_variation_sequence_preserves_its_selector(self):
        for base in sorted(text_hygiene._EMOJI_VARIATION_BASES):
            for selector in ("\ufe0e", "\ufe0f"):
                source = chr(base) + selector
                if base in text_hygiene._KEYCAP_BASES:
                    source += "\u20e3"
                with self.subTest(sequence=hex_sequence(source)):
                    cleaned, manifest = clean_text(source)

                    self.assertEqual(cleaned, source)
                    self.assertEqual(manifest["summary"]["actionable"], 0)

    def test_removes_selector_after_base_without_variation_sequence(self):
        source = "\U0001f680\ufe0f \U0001f600\ufe0e"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\U0001f680 \U0001f600")
        self.assertEqual(manifest["summary"]["removed"], 2)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_removes_repeated_presentation_selector(self):
        source = "\u2764\ufe0f\ufe0f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\u2764\ufe0f")
        self.assertEqual(finding(manifest, "U+FE0F", "preserve")["offsets"], [1])
        self.assertEqual(finding(manifest, "U+FE0F", "remove")["offsets"], [2])

    def test_preserves_every_pinned_emoji_tag_sequence(self):
        for sequence in text_hygiene._EMOJI_TAG_SEQUENCES:
            with self.subTest(sequence=hex_sequence(sequence)):
                cleaned, manifest = clean_text("flag " + sequence + ".")

                self.assertEqual(cleaned, "flag " + sequence + ".")
                self.assertEqual(manifest["summary"]["actionable"], 0)
                self.assertEqual(manifest["summary"]["preserved"], 6)
                self.assertEqual(
                    {item["reason"] for item in manifest["findings"]},
                    {TAG_REASON},
                )

    def test_removes_tag_characters_outside_pinned_tag_sequences(self):
        unpinned_flag = (
            "\U0001f3f4\U000e0075\U000e0073\U000e0063\U000e0061\U000e007f"
        )
        source = "a\U000e0067\U000e0062b " + unpinned_flag

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "ab \U0001f3f4")
        self.assertEqual(manifest["summary"]["removed"], 7)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_recombined_man_chain_reports_pairwise_evidence_only(self):
        source = (
            "\U0001f468\u200d\U0001f468\u200d\U0001f468\u200d"
            "\U0001f468\u200d\U0001f468"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        item = finding(manifest, "U+200D", "preserve")
        self.assertEqual(item["count"], 4)
        self.assertEqual(item["reason"], "matches a pinned Emoji 17 pair")
        self.assertNotIn("valid", item["reason"])

    def test_does_not_join_bases_across_spacing_or_punctuation(self):
        source = "\U0001f469 \u200d \U0001f4bb \u0645,\u200c,\u062e"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\U0001f469  \U0001f4bb \u0645,,\u062e")
        self.assertEqual(manifest["summary"]["removed"], 2)
        self.assertNotIn("preserve", [item["action"] for item in manifest["findings"]])

    def test_never_preserves_zero_width_non_joiner_as_emoji_glue(self):
        source = "\U0001f469\u200c\U0001f4bb"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\U0001f469\U0001f4bb")
        self.assertEqual(finding(manifest, "U+200C", "remove")["count"], 1)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_removes_unknown_adjacent_emoji_zwj_pair(self):
        source = "\U0001f600\u200d\U0001f680"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\U0001f600\U0001f680")
        self.assertEqual(finding(manifest, "U+200D", "remove")["count"], 1)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_removes_cross_script_joiner(self):
        source = "\u0645\u200d\u0915"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\u0645\u0915")
        self.assertEqual(finding(manifest, "U+200D", "remove")["count"], 1)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_preserves_unclassified_format_control_conservatively(self):
        source = "a\u06ddb"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+06DD", "preserve")["reason"],
            "unclassified format control preserved conservatively",
        )

    def test_groups_same_joiner_by_action_and_reason(self):
        source = (
            "\u0915\u094d\u200d\u0937 "
            "\U0001f469\u200d\U0001f4bb"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        zwj_findings = [
            item
            for item in manifest["findings"]
            if item["code_point"] == "U+200D" and item["action"] == "preserve"
        ]
        self.assertEqual(len(zwj_findings), 2)
        self.assertEqual(
            {item["reason"] for item in zwj_findings},
            {
                "required by surrounding complex-script orthography",
                "matches a pinned Emoji 17 pair",
            },
        )

    def test_leaves_fullwidth_and_cyrillic_letters_unchanged(self):
        source = "\uff21\uff22\uff23 \u0410\u0412\u0421"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(manifest["findings"], [])
        self.assertEqual(
            manifest["summary"],
            {
                "detected": 0,
                "removed": 0,
                "normalized": 0,
                "preserved": 0,
                "actionable": 0,
            },
        )
        self.assertEqual(manifest["policy_version"], 3)
        self.assertEqual(manifest["unicode_version"], text_hygiene.unicodedata.unidata_version)
        self.assertEqual(manifest["emoji_zwj_version"], "17.0")

    @unittest.skipUnless(
        os.environ.get("VOICEPRINT_RELEASE_BENCHMARK") == "1",
        "release benchmark is opt-in",
    )
    def test_p95_is_within_budget_for_one_hundred_thousand_code_points(self):
        source = ("a\u200b" * 50_000)

        for _ in range(2):
            clean_text(source)
        durations = []
        for _ in range(20):
            started = time.perf_counter()
            cleaned, manifest = clean_text(source)
            durations.append(time.perf_counter() - started)
        p95 = sorted(durations)[math.ceil(len(durations) * 0.95) - 1]

        self.assertEqual(cleaned, "a" * 50_000)
        self.assertEqual(manifest["summary"]["removed"], 50_000)
        self.assertEqual(finding(manifest, "U+200B", "remove")["count"], 50_000)
        self.assertEqual(len(finding(manifest, "U+200B", "remove")["offsets"]), 10)
        print(f"release benchmark p95: {p95 * 1000:.1f} ms")
        self.assertLessEqual(
            p95,
            0.200,
            f"100,000-code-point p95 was {p95:.3f}s, expected at most 0.200s",
        )


class TypographyAndDirectionTests(unittest.TestCase):
    """Hygiene policy 3: typographic spaces and directional marks."""

    def assert_mark(self, source, code_point, action, reason=None):
        """Assert the single directional mark in source gets action and reason."""
        item = next(
            item
            for item in clean_text(source)[1]["findings"]
            if item["code_point"] == code_point
        )
        self.assertEqual((item["action"], item.get("reason")), (action, reason))

    def test_preserves_no_break_spaces_inside_numbers(self):
        source = "10\u00a0000, 2\u202f500 and 7\u2007000"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        for code_point in ("U+00A0", "U+202F", "U+2007"):
            self.assertEqual(
                finding(manifest, code_point, "preserve")["reason"],
                NUMBER_SPACE_REASON,
            )
        self.assertEqual(manifest["summary"]["preserved"], 3)
        self.assertEqual(manifest["summary"]["actionable"], 0)

    def test_preserves_no_break_space_between_number_and_unit(self):
        source = "5\u00a0km, 12\u202f%, 30\u00a0\u20ac, 3\u00a0kg."

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+00A0", "preserve"),
            {
                "code_point": "U+00A0",
                "name": "NO-BREAK SPACE",
                "action": "preserve",
                "count": 3,
                "offsets": [1, 14, 19],
                "reason": UNIT_SPACE_REASON,
            },
        )
        self.assertEqual(
            finding(manifest, "U+202F", "preserve")["reason"], UNIT_SPACE_REASON
        )
        # A word longer than a unit symbol, and a figure space outside a
        # number, are ordinary gaps.
        self.assertEqual(clean_text("3\u00a0pommes")[0], "3 pommes")
        self.assertEqual(clean_text("3\u00a0four")[0], "3 four")
        self.assertEqual(clean_text("3\u00a0four apples")[0], "3 four apples")
        self.assertEqual(clean_text("3\u00a0for")[0], "3\u00a0for")
        self.assertEqual(clean_text("3\u00a0kWh used")[0], "3\u00a0kWh used")
        self.assertEqual(clean_text("5\u2007km")[0], "5 km")

    def test_preserves_no_break_spaces_at_french_punctuation(self):
        source = (
            "\u00ab\u00a0Bonjour\u202f!\u00a0\u00bb Vraiment\u202f? "
            "Oui\u00a0: non\u202f;"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        nbsp = finding(manifest, "U+00A0", "preserve")
        narrow = finding(manifest, "U+202F", "preserve")
        self.assertEqual(nbsp["offsets"], [1, 11, 28])
        self.assertEqual(narrow["offsets"], [9, 22, 34])
        self.assertEqual({nbsp["reason"], narrow["reason"]}, {FRENCH_SPACE_REASON})

    def test_normalizes_no_break_spaces_outside_typographic_contexts(self):
        source = (
            "here\u00a0today, word\u00a0\u00a0! and 5\u00a0\u00a0km or "
            "\u00a0x on page\u00a05"
        )

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "here today, word  ! and 5  km or  x on page 5")
        self.assertEqual(finding(manifest, "U+00A0", "normalize")["count"], 7)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_judges_spaces_by_neighbors_that_take_space(self):
        # A zero-width character beside the space never decides the context,
        # so cleaning the cleaned copy changes nothing.
        for source, expected in (
            ("Oui \u200b\u00a0!", "Oui  !"),
            ("5\u200b\u00a0km", "5\u00a0km"),
            ("\u65e5\u200b\u3000x", "\u65e5\u3000x"),
        ):
            with self.subTest(source=hex_sequence(source)):
                cleaned = clean_text(source)[0]

                self.assertEqual(cleaned, expected)
                self.assertEqual(clean_text(cleaned)[0], cleaned)

    def test_preserves_ideographic_space_beside_cjk_text(self):
        source = "\u3000\u65e5\u672c\u8a9e\u3000\u3000\u6587\u7ae0"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(
            finding(manifest, "U+3000", "preserve"),
            {
                "code_point": "U+3000",
                "name": "IDEOGRAPHIC SPACE",
                "action": "preserve",
                "count": 3,
                "offsets": [0, 4, 5],
                "reason": CJK_SPACE_REASON,
            },
        )
        # An invisible Hangul filler is not CJK text.
        self.assertEqual(clean_text("a\u3000\u3164")[0], "a \u3164")

    def test_paragraph_separators_match_bidi_class_b(self):
        separators = {
            chr(code_point)
            for code_point in range(0x110000)
            if unicodedata.bidirectional(chr(code_point)) == "B"
        }

        self.assertEqual(set(text_hygiene._PARAGRAPH_SEPARATORS), separators)

    def test_pairs_brackets_as_definition_bd16_describes(self):
        self.assertEqual(bracket_pairs("a(b[c]d)e"), [(1, 7), (3, 5)])
        # Canonically equivalent angle brackets pair with each other.
        self.assertEqual(
            bracket_pairs("\u2329x\u3009 \u3008y\u232a"), [(0, 2), (4, 6)]
        )
        # A closing bracket with no opening partner is skipped, and a
        # mismatched one closes the nearest opening it does match.
        self.assertEqual(bracket_pairs(")(a]b)"), [(1, 5)])
        # The search stops when 63 opening brackets are waiting.
        self.assertEqual(len(bracket_pairs("(" * 63 + ")" * 63)), 63)
        self.assertEqual(bracket_pairs("(" * 64 + ")" * 64), [])

    def test_resolver_follows_each_bidi_rule(self):
        # Expected levels agree with ICU and GNU FriBidi, except the combining
        # mark after a resolved bracket, where the rule N0 text decides.
        cases = (
            ("W1", "a \u05d0\u05b8 b", [0, 0, 1, 1, 0, 0]),
            ("W2 and W4", "\u0627 1+2", [1, 1, 2, 1, 2]),
            ("W4", "\u05d0 1+2", [1, 1, 2, 2, 2]),
            ("W5", "\u05d0 5%", [1, 1, 2, 2]),
            ("W6", "\u05d0 %", [1, 1, 1]),
            ("W7", "a \u05d0 b 12", [0, 0, 1, 0, 0, 0, 0, 0]),
            ("N0 b", "a (\u05d0 b) c", [0, 0, 0, 1, 0, 0, 0, 0, 0]),
            ("N0 c.1", "\u05d0 b(c)d \u05d3", [1, 1, 2, 2, 2, 2, 2, 1, 1]),
            ("N0 c.2", "\u05d0 (b) \u05d3", [1, 1, 1, 2, 1, 1, 1]),
            ("N0 mark", "a \u05d0(\u05d1)\u0301 b", [0, 0, 1, 1, 1, 1, 1, 0, 0]),
            ("N0 empty", "\u05d0 ( ) b", [1, 1, 1, 1, 1, 1, 2]),
            ("N1", "a \u05d0 . 1", [0, 0, 1, 1, 1, 1, 2]),
            ("I2", "\u05d0 abc", [1, 1, 2, 2, 2]),
            ("L1 end", "\u05d0 abc   ", [1, 1, 2, 2, 2, 1, 1, 1]),
            ("L1 tab", "a\t\u05d0", [0, 0, 1]),
        )
        for rule, text, expected in cases:
            with self.subTest(rule=rule):
                classes = [text_hygiene._bidi_class(character) for character in text]
                base_level = int(
                    next(value for value in classes if value in ("L", "R", "AL")) != "L"
                )
                levels = text_hygiene._resolve_levels(
                    classes, base_level, True, bracket_pairs(text)
                )

                self.assertEqual(levels, expected)

    def test_bracket_pairs_are_mirrored_open_and_close_punctuation(self):
        for opening, closing in text_hygiene._BRACKET_PAIRS:
            with self.subTest(pair=f"U+{opening:04X} U+{closing:04X}"):
                self.assertEqual(unicodedata.category(chr(opening)), "Ps")
                self.assertEqual(unicodedata.category(chr(closing)), "Pe")
                self.assertTrue(unicodedata.mirrored(chr(opening)))
                self.assertTrue(unicodedata.mirrored(chr(closing)))

    def test_removes_marks_from_paragraphs_without_right_to_left_letters(self):
        source = "Hello\u200e world\u200f! \u061c(1)\n\u200fHello!\u061c"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "Hello world! (1)\nHello!")
        self.assertEqual(manifest["summary"]["removed"], 5)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_keeps_mark_that_sets_paragraph_direction(self):
        source = "\u200fPython \u05d4\u05d9\u05d0 \u05e9\u05e4\u05d4"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        kept = finding(manifest, "U+200F", "preserve")
        self.assertEqual(kept["offsets"], [0])
        self.assertEqual(kept["reason"], SETS_DIRECTION_REASON)
        # The paragraph is already right to left without it.
        self.assertEqual(clean_text("\u200f" + HEBREW_SHALOM)[0], HEBREW_SHALOM)

    def test_keeps_mark_that_moves_neighboring_punctuation(self):
        source = HEBREW_SHALOM + " Hello!\u200e"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, source)
        kept = finding(manifest, "U+200E", "preserve")
        self.assertEqual(kept["offsets"], [11])
        self.assertEqual(kept["reason"], CHANGES_DISPLAY_REASON)
        # The "!" already takes the paragraph's direction without this one.
        self.assert_mark(HEBREW_SHALOM + " Hello!\u200f", "U+200F", "remove")

    def test_keeps_mark_that_splits_a_run_of_opposite_direction_letters(self):
        self.assert_mark(
            "Hello \u05d0\u05d1\u200e\u05d2\u05d3",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )
        # Letters keep their own direction, so between two letters of the
        # paragraph's direction a mark changes nothing.
        self.assert_mark("\u05d0\u05d1\u200f\u05d2\u05d3", "U+200F", "remove")

    def test_judges_a_mark_between_words_by_the_paragraph_direction(self):
        self.assert_mark(
            HEBREW_SHALOM + "\u200e " + HEBREW_OLAM, "U+200E", "remove"
        )
        self.assert_mark(
            "Hello " + HEBREW_SHALOM + "\u200e " + HEBREW_OLAM,
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )

    def test_judges_marks_near_numbers_exactly(self):
        # A left-to-right mark keeps a minus sign with its number; a
        # right-to-left mark there changes nothing.
        self.assert_mark(
            HEBREW_SHALOM + " \u200e-5", "U+200E", "preserve", CHANGES_DISPLAY_REASON
        )
        self.assert_mark(HEBREW_SHALOM + " \u200f-5", "U+200F", "remove")
        self.assert_mark(
            HEBREW_SHALOM + " \u200e(12)", "U+200E", "preserve", CHANGES_DISPLAY_REASON
        )
        self.assert_mark(HEBREW_SHALOM + " \u200f(12)", "U+200F", "remove")
        # The hyphen joins the two numbers either way.
        self.assert_mark(HEBREW_SHALOM + " \u200e1-2", "U+200E", "remove")

    def test_judges_marks_beside_tabs_exactly(self):
        self.assert_mark(HEBREW_SHALOM + "\t\u200e\u05d0", "U+200E", "remove")
        self.assert_mark(HEBREW_SHALOM + " a\t\u200fb", "U+200F", "remove")

    def test_judges_marks_beside_resolved_brackets_exactly(self):
        # Hebrew inside the brackets fixes them to the paragraph's direction.
        for mark, code_point in (("\u200f", "U+200F"), ("\u200e", "U+200E")):
            with self.subTest(code_point=code_point):
                source = HEBREW_SHALOM + " (" + HEBREW_OLAM + ")" + mark
                self.assert_mark(source, code_point, "remove")

    def test_judges_marks_beside_opposite_direction_parentheticals(self):
        # A left-to-right mark before the bracket makes the pair take the
        # direction of the English inside it; elsewhere a mark changes nothing.
        self.assert_mark(
            HEBREW_SHALOM + " \u200e(Hello)",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )
        self.assert_mark(HEBREW_SHALOM + " \u200f(Hello)", "U+200F", "remove")
        self.assert_mark(HEBREW_SHALOM + " (Hello)\u200e", "U+200E", "remove")

    def test_keeps_mark_that_decides_a_bracket_pair_around_its_window(self):
        # The mark is the pair's only left-to-right character, so without it
        # the parentheses take the Hebrew direction, though the tab keeps the
        # text right around the mark the same.
        self.assert_mark(
            "a \u05d2(\u05d0\u05d1\u200e\t\u05d2\u05d3)",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )

    def test_keeps_only_the_first_mark_of_a_run(self):
        source = HEBREW_SHALOM + " Hello!\u200e\u200e\u200b\u200f"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, HEBREW_SHALOM + " Hello!\u200e")
        self.assertEqual(finding(manifest, "U+200E", "preserve")["offsets"], [11])
        self.assertEqual(finding(manifest, "U+200E", "remove")["offsets"], [12])
        self.assertEqual(finding(manifest, "U+200F", "remove")["offsets"], [14])

    def test_rejudges_a_mark_after_a_later_mark_is_removed(self):
        # Judged while the left-to-right mark is still in place, the Arabic
        # letter mark seems to set the paragraph direction. Once that mark is
        # removed the letter already does, so it goes too.
        cleaned, manifest = clean_text("\u061c-\u200e\u05d1")

        self.assertEqual(cleaned, "-\u05d1")
        self.assertEqual(manifest["summary"]["removed"], 2)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_removes_mark_between_a_letter_and_its_combining_mark(self):
        source = "Hello \u05d0\u200e\u05b8\u05d1"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "Hello \u05d0\u05b8\u05d1")
        self.assertEqual(finding(manifest, "U+200E", "remove")["offsets"], [7])

    def test_judges_a_mark_after_a_combining_mark_by_its_base(self):
        self.assert_mark(
            "Hello \u05d0\u05b8\u200e\u05d1",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )

    def test_judges_marks_as_if_removed_characters_were_gone(self):
        # The stray selector goes, so the mark sits between two letters.
        self.assert_mark(
            "Hello \u05d0\u200e\ufe0f\u05d1",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )

    def test_gives_unassigned_code_points_their_default_direction(self):
        # U+05FF is unassigned, and right to left by default in the Hebrew block.
        self.assert_mark(
            "Hello \u05ff\u200e \u05ff", "U+200E", "preserve", CHANGES_DISPLAY_REASON
        )
        self.assertEqual(text_hygiene._bidi_class("\u0378"), "L")
        self.assertEqual(text_hygiene._bidi_class("\ufdd0"), "BN")

    def test_keeps_exactly_the_marks_that_change_the_display(self):
        # Inputs that once told apart a correct resolver from a subtly wrong
        # one; the kept offsets agree with ICU and GNU FriBidi.
        cases = (
            ("numbers count as R for neutrals", "061C 0030 002C 200E 05FF", []),
            ("Arabic letters count as R", "200E 05D0 061C 05FF", [0]),
            ("a comma between numbers joins them", "062B 0039 00A0 061C 0032", [3]),
            ("a pair holding the paragraph direction", "005B 05DC 200E 005D 0063", []),
            ("the same, right to left", "200F 0028 0025 200E 0628 0029", []),
            (
                "marks kept so far shape later ones",
                "200E 0026 061C 002B 0026 200F 0061 05D0",
                [0, 2, 5],
            ),
            ("in a widened window too", "0068 2329 200F 0032 200E 05FF 232A", []),
            ("equal windows differ by mark position", "05DC 200E 0020 200E 0063", [1]),
            (
                "an empty pair resolves by its neighbors",
                "0628 200E 3008 3009 200E",
                [1, 4],
            ),
            ("mirroring alone is a change", "0063 05D3 0062 061C 2329 200F", [3, 5]),
        )
        for name, code_points, expected in cases:
            with self.subTest(name=name):
                source = "".join(chr(int(value, 16)) for value in code_points.split())
                manifest = clean_text(source)[1]
                kept = sorted(
                    offset
                    for item in manifest["findings"]
                    if item["action"] == "preserve"
                    and item["code_point"] in ("U+200E", "U+200F", "U+061C")
                    for offset in item["offsets"]
                )

                self.assertEqual(kept, expected)

    def test_pins_rules_that_once_slipped_past_the_suite(self):
        # Inputs on which a resolver with one rule subtly wrong kept different
        # marks; the kept offsets agree with ICU and GNU FriBidi.
        cases = (
            (
                "W4 joins only numbers of one type",
                (
                    "0028 0022 200E 0028 200B 200F 0025 00A0 0661 2030 200B 3009 "
                    "064E 200B 05FF 2329 002B 0661 200F 002C 0032 061C 0063"
                ),
                [2, 5],
            ),
            (
                "N0 counts numbers as R",
                (
                    "200E 05E6 200E 05E1 05D2 0020 0020 002A 3000 0646 0591 062A "
                    "0646 062A 200E 2007 0628 0645 0646 200F 062B 0628 00A0 0030 "
                    "2030 2329 2030 0661 0666 232A 061C 061C 0020 0020"
                ),
                [0, 2, 14],
            ),
            (
                "N0 takes pairs in opening order",
                (
                    "2329 005B 0026 0009 0020 005D 002D 0035 0031 002C 007B 200E "
                    "05D4 200E 200F 05E6 061C 05D2 05B8 0023 3000 007D 0020 0020 "
                    "061C 0028 0031 0034 0038 202F 0033 3000 0029 05E9 05E3 05D9 "
                    "0020 232A 2007"
                ),
                [11, 13, 24],
            ),
            (
                "combining-mark attachment counts",
                (
                    "0591 0030 002F 0063 0660 200E 05D1 000B 0028 0323 0031 2329 "
                    "0031 0009 200F 05B8 002F FEFF 001F 061C 0062 002D 0301 05D3 "
                    "002C 0031"
                ),
                [5, 19],
            ),
            (
                "BD16 drops openers above a match",
                (
                    "0028 061C 200F 202F 007B 0064 3000 0661 200F 0063 0064 0301 "
                    "2329 200F 0031 00A0 0029 05FF 232A 232A 0029 002E 0020 002E "
                    "200F 061C 200B"
                ),
                [1, 8, 13],
            ),
            (
                "a pair counts only letters for L",
                (
                    "0063 0063 064E 2019 061C 3000 0028 0038 202F 0033 002D 0026 "
                    "0020 05E2 0591 05DA 05E6 05DA 05E9 FEFF 3000 0029 2007 061C "
                    "200E 007C 2007"
                ),
                [4, 23],
            ),
            (
                "a pair counts only letters and AN for R",
                (
                    "05E4 05D2 0020 2329 0061 005B 0065 0066 0068 0065 0068 05DD "
                    "05E6 05E9 05DD 200E 200E 005D 0645 0628 0065 0062 061C 200E "
                    "0063 064E 0066 200F 007B 000B 0020 0027 3000 0061 0067 0039 "
                    "0031 0031 2060 0020"
                ),
                [22, 27],
            ),
            (
                "judging repeats until stable",
                "FE0F 200E 00A0 200F 0660 007B 200E 061C 05D3 00A0",
                [6],
            ),
            (
                "paragraph direction is part of the shape",
                (
                    "0663 0667 0664 0660 002C 05D9 05D3 200F 0591 0020 0020 0665 "
                    "202F 2007 007C 05D6 200E 05DF 05E7 05D1 05D7 3000 061C 000A "
                    "002E 0030 003F 2007 0030 005B 002B 0062 001F 200B 05D3 05FF "
                    "200F 0323 002E 2030"
                ),
                [],
            ),
            (
                "normalized spaces are WS",
                (
                    "2007 200E 05B8 002A 002E 3008 001F 200E 0022 2007 3000 2007 "
                    "0064 0627 002A 002C 00A0 200F 001F 05D3 007B 0628 0031 05D0"
                ),
                [17],
            ),
        )
        for name, code_points, expected in cases:
            with self.subTest(name=name):
                source = "".join(chr(int(value, 16)) for value in code_points.split())
                manifest = clean_text(source)[1]
                kept = sorted(
                    offset
                    for item in manifest["findings"]
                    if item["action"] == "preserve"
                    and item["code_point"] in ("U+200E", "U+200F", "U+061C")
                    for offset in item["offsets"]
                )

                self.assertEqual(kept, expected)

    def test_removes_marks_whose_bracket_window_is_too_wide(self):
        # The mark decides the pair, but judging it means reading the pair.
        self.assert_mark(
            HEBREW_SHALOM + " \u200e(" + "a" * 5000 + ")", "U+200E", "remove"
        )

    def test_removes_marks_far_from_any_letter(self):
        # Judged within 64 characters of a letter, removed beyond.
        self.assert_mark(
            "\u05d0" + " ." * 30 + "\u200e! b",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )
        self.assert_mark("\u05d0" + " ." * 32 + "\u200e! b", "U+200E", "remove")

    def test_removes_marks_left_unjudged_when_the_budget_runs_out(self):
        source = HEBREW_SHALOM + " Hello!\u200e"
        with mock.patch.object(text_hygiene, "_MARK_BUDGET", 1):
            self.assert_mark(source, "U+200E", "remove")
        self.assert_mark(source, "U+200E", "preserve", CHANGES_DISPLAY_REASON)

    def test_keeps_no_marks_in_a_paragraph_the_budget_cannot_finish(self):
        # Removing only the unjudged marks here would take the mark that sets
        # the paragraph direction and leave the others judged under the old
        # direction, so the paragraph keeps none of its marks.
        source = "\u200e \u200f\u05d0 " + "\u05d2 \u200e \u05d3 " * 10
        with mock.patch.object(text_hygiene, "_MARK_BUDGET", 30):
            cleaned, manifest = clean_text(source)

        self.assertEqual(manifest["summary"]["preserved"], 0)
        self.assertEqual(clean_text(cleaned)[0], cleaned)

    def test_removes_marks_whose_verdict_the_budget_left_stale(self):
        # Each Arabic letter mark is kept while the left-to-right mark after
        # it is in place; once that one goes, the budget is gone, so the
        # first verdict cannot be trusted and the mark goes too.
        source = "\u061c-\u200e\u05d0 " * 50
        with mock.patch.object(text_hygiene, "_MARK_BUDGET", 400):
            cleaned = clean_text(source)[0]

        self.assertEqual(clean_text(cleaned)[0], cleaned)

    def test_keeps_no_marks_when_the_pass_limit_runs_out(self):
        # The right-to-left mark sets the paragraph direction and is judged
        # again once the left-to-right mark goes. With one pass that second
        # judgment never happens, so the paragraph keeps none of its marks.
        source = "\u200f-\u200eb \u05d0"
        self.assert_mark(source, "U+200F", "preserve", SETS_DIRECTION_REASON)
        with mock.patch.object(text_hygiene, "_MARK_PASSES", 1):
            cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "-b \u05d0")
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_keeps_only_marks_judged_in_full_at_every_budget(self):
        # Wherever the budget runs out, including inside a window widened
        # over brackets, a mark stays only if the full budget keeps it too,
        # and cleaning the cleaned copy changes nothing.
        source = (
            HEBREW_SHALOM
            + " \u200e(Hello) "
            + HEBREW_OLAM
            + " (b)\u200e(c) \u05d2(\u05d0\u05d1\u200e\t\u05d2\u05d3) Hello!\u200e"
        )
        full = kept_marks(clean_text(source)[1])
        self.assertEqual(full, [5, 22, 43])
        for budget in range(1, 80):
            with self.subTest(budget=budget):
                with mock.patch.object(text_hygiene, "_MARK_BUDGET", budget):
                    cleaned, manifest = clean_text(source)

                self.assertLessEqual(set(kept_marks(manifest)), set(full))
                self.assertEqual(clean_text(cleaned)[0], cleaned)

    def test_checks_each_bracket_once_per_judgment(self):
        # Each pair resolves by the one before it, so judging any mark here
        # widens over the whole row. Checking every bracket again at each
        # step once made a single judgment quadratic in the number of pairs.
        source = "\u05d0" + "(b)\u200e" * 200 + "\u05d0"
        checked = []
        judge = text_hygiene._ParagraphMarks._judge
        unheld_pairs = text_hygiene._ParagraphMarks._unheld_pairs

        def counting_judge(marks, item):
            checked.append(0)
            return judge(marks, item)

        def counting_unheld_pairs(marks, indices, *rest):
            indices = list(indices)
            checked[-1] += len(indices)
            return unheld_pairs(marks, indices, *rest)

        with mock.patch.object(
            text_hygiene._ParagraphMarks, "_judge", counting_judge
        ), mock.patch.object(
            text_hygiene._ParagraphMarks, "_unheld_pairs", counting_unheld_pairs
        ):
            manifest = clean_text(source)[1]

        self.assertEqual(kept_marks(manifest), [4])
        self.assertLessEqual(max(checked), 400)

    def test_removes_marks_in_paragraphs_with_explicit_controls(self):
        # The isolate goes, and a mark that worked inside it could reorder the
        # paragraph without it.
        source = HEBREW_SHALOM + " Hello!\u200e " + HEBREW_OLAM + "\u2066x\u2069"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, HEBREW_SHALOM + " Hello! " + HEBREW_OLAM + "x")
        self.assertEqual(manifest["summary"]["preserved"], 0)
        # Without the isolate the same mark changes the display and stays.
        self.assert_mark(
            HEBREW_SHALOM + " Hello!\u200e " + HEBREW_OLAM + "x",
            "U+200E",
            "preserve",
            CHANGES_DISPLAY_REASON,
        )

    def test_judges_right_to_left_text_per_paragraph(self):
        source = "Hello!\u200e\r\n" + HEBREW_SHALOM + " Hello!\u200e\u2029Hello!\u200e"

        cleaned, manifest = clean_text(source)

        self.assertEqual(
            cleaned, "Hello!\r\n" + HEBREW_SHALOM + " Hello!\u200e\u2029Hello!"
        )
        self.assertEqual(finding(manifest, "U+200E", "preserve")["offsets"], [20])
        self.assertEqual(finding(manifest, "U+200E", "remove")["offsets"], [6, 28])

    def test_still_removes_embeddings_overrides_and_isolates(self):
        source = "\u05e9\u202bx\u202c\u202ey\u2066z\u2069"

        cleaned, manifest = clean_text(source)

        self.assertEqual(cleaned, "\u05e9xyz")
        self.assertEqual(manifest["summary"]["removed"], 5)
        self.assertEqual(manifest["summary"]["preserved"], 0)

    def test_cleaning_the_cleaned_copy_changes_nothing(self):
        alphabet = (
            "\u05d0\u05d1\u0627\u0628ab12\u0661 .,!-%()[]:\t"
            "\u05b8\u064e\u200b\u00a0\u202f\u3000\u65e5\ufe0f"
            "\u2066\u2069\u202e"
        )
        marks = "\u200e\u200f\u061c"
        generator = random.Random(3)
        unstable = []
        for _ in range(3000):
            characters = [
                generator.choice(alphabet) for _ in range(generator.randint(1, 20))
            ]
            for _ in range(generator.randint(0, 4)):
                characters.insert(
                    generator.randint(0, len(characters)), generator.choice(marks)
                )
            source = "".join(characters)
            cleaned = clean_text(source)[0]
            if clean_text(cleaned)[0] != cleaned:
                unstable.append(hex_sequence(source))

        self.assertEqual(unstable, [])


@unittest.skipUnless(
    os.environ.get("VOICEPRINT_FRIBIDI") == "1" and shutil.which("fribidi"),
    "set VOICEPRINT_FRIBIDI=1 with GNU FriBidi installed to run the bidi check",
)
class BidiReferenceTests(unittest.TestCase):
    """Check directional-mark decisions against GNU FriBidi's bidi algorithm."""

    MARKS = ("\u200e", "\u200f", "\u061c")
    CONTROLS = tuple(chr(code_point) for code_point in (0x202A, 0x202E, 0x2066, 0x2069))
    HIDDEN = frozenset(MARKS + CONTROLS + ("\u200b", "\ufe0f"))
    ALPHABET = (
        "\u05d0\u05d1\u05d2\u05d3\u0627\u0628\u062a\u062b"
        "abcd12\u0661\u0662  .,!-+%()[]:/$\t\u05b8\u064e\u200b"
    )
    EXTRA = "\u00a0\u202f\ufe0f\u05ff5%" + "".join(CONTROLS)

    def displays(self, lines):
        """Base direction, order of base characters, combining marks staying at
        their base's level, and mirroring, for each line."""
        output = subprocess.run(
            [
                "fribidi",
                "--nopad",
                "--nobreak",
                "--basedir",
                "--vtol",
                "--levels",
                "--novisual",
            ],
            input=("\n".join(lines) + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.decode("utf-8").split("\n")
        shown = []
        for index, line in enumerate(lines):
            base, order, levels = output[3 * index : 3 * index + 3]
            level = [int(value) for value in levels.split()]
            visible = [
                i for i, character in enumerate(line) if character not in self.HIDDEN
            ]
            bases = [i for i in visible if unicodedata.bidirectional(line[i]) != "NSM"]
            rank = {position: number for number, position in enumerate(bases)}
            attached, base_level = [], None
            for i in visible:
                if unicodedata.bidirectional(line[i]) == "NSM":
                    attached.append(level[i] == base_level)
                else:
                    base_level = level[i]
            shown.append(
                (
                    base,
                    [rank[int(value)] for value in order.split() if int(value) in rank],
                    attached,
                    [level[i] % 2 for i in visible if unicodedata.mirrored(line[i])],
                )
            )
        return shown

    def reference(self, text):
        """The text with every decision applied except judging candidate marks."""
        previous_bases, next_bases = text_hygiene._neighboring_bases(text)
        context = text_hygiene._Context(
            previous_bases, next_bases, text_hygiene._cjk_space_offsets(text), {}
        )
        candidates = set()
        for start, end in text_hygiene._paragraphs(text):
            paragraph = text[start:end]
            if any(
                control in paragraph
                for control in text_hygiene._EXPLICIT_DIRECTIONAL_CONTROLS
            ) or not any(
                character not in self.MARKS
                and text_hygiene._bidi_class(character) in ("R", "AL")
                for character in paragraph
            ):
                continue
            judge = text_hygiene._ParagraphMarks(text, start, end, context, [0], {})
            candidates.update(judge.candidates)
        kept = []
        for offset, character in enumerate(text):
            if character in self.MARKS:
                if offset in candidates:
                    kept.append(character)
                continue
            classification = text_hygiene._classify(text, offset, context)
            if classification is None or classification[0] == "preserve":
                kept.append(character)
            elif classification[0] == "normalize":
                kept.append(" ")
        return "".join(kept)

    def test_cleanup_never_changes_display_and_kept_marks_matter(self):
        generator = random.Random(2026)
        pairs = []
        for _ in range(4000):
            pool = self.ALPHABET + (self.EXTRA if generator.random() < 0.5 else "")
            characters = [
                generator.choice(pool) for _ in range(generator.randint(2, 24))
            ]
            for _ in range(generator.randint(1, 5)):
                characters.insert(
                    generator.randint(0, len(characters)), generator.choice(self.MARKS)
                )
            text = "".join(characters)
            cleaned, manifest = clean_text(text)
            pairs.append(("unchanged", text, self.reference(text), cleaned))
            removed = {
                offset
                for item in manifest["findings"]
                if item["action"] == "remove"
                for offset in item["offsets"]
            }
            for item in manifest["findings"]:
                if item.get("reason") == SETS_DIRECTION_REASON:
                    for offset in item["offsets"]:
                        at = offset - sum(1 for other in removed if other < offset)
                        pairs.append(
                            ("changed", text, cleaned, cleaned[:at] + cleaned[at + 1 :])
                        )

        lines = [line for _, _, first, second in pairs for line in (first, second)]
        shown = self.displays(lines)
        failures = [
            hex_sequence(text)
            for index, (expected, text, _, _) in enumerate(pairs)
            if (shown[2 * index] == shown[2 * index + 1]) != (expected == "unchanged")
        ]

        self.assertEqual(failures, [])
        print(f"FriBidi check: {len(pairs)} display comparisons agree")


class EvalFixtureTests(unittest.TestCase):
    """Keep the hygiene numbers that evals promise in line with the helper."""

    def test_hygiene_evals_match_the_helper(self):
        evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        checked = 0
        for case in evals["evals"]:
            draft = case["prompt"].split(": ", 1)[-1]
            if draft.isascii():
                continue
            checked += 1
            manifest = inspect_text(draft)
            located = {}
            explained = {}
            for item in manifest["findings"]:
                located.setdefault(item["code_point"], set()).update(item["offsets"])
                key = (item["code_point"], item.get("reason"))
                explained.setdefault(key, set()).update(item["offsets"])
            for expectation in case["expectations"]:
                with self.subTest(eval_id=case["id"], expectation=expectation):
                    counts = re.search(
                        r"detected (\d+), removed (\d+), normalized (\d+),"
                        r"(?: and)? deliberately preserved (\d+)",
                        expectation,
                    )
                    if counts:
                        self.assertEqual(
                            [
                                manifest["summary"][key]
                                for key in (
                                    "detected",
                                    "removed",
                                    "normalized",
                                    "preserved",
                                )
                            ],
                            [int(value) for value in counts.groups()],
                        )
                    for code_point, offsets in re.findall(
                        r"(U\+[0-9A-F]{4,6}) at offsets? (\d+(?:(?:,| and) \d+)*)",
                        expectation,
                    ):
                        self.assertLessEqual(
                            {int(value) for value in re.findall(r"\d+", offsets)},
                            located.get(code_point, set()),
                        )
                    for reason, code_point, offsets in re.findall(
                        r"'([^']+)' for (U\+[0-9A-F]{4,6}) at offsets? "
                        r"(\d+(?:(?:,| and) \d+)*)",
                        expectation,
                    ):
                        self.assertLessEqual(
                            {int(value) for value in re.findall(r"\d+", offsets)},
                            explained.get((code_point, reason), set()),
                        )

        self.assertGreaterEqual(checked, 4)


class TextHygieneCliTests(unittest.TestCase):
    def run_cli(self, *args, input_bytes=b"", env=None, timeout=None):
        environment = os.environ.copy()
        if env is not None:
            environment.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            env=environment,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )

    def test_inspect_reads_stdin_emits_json_and_exits_one(self):
        result = self.run_cli("inspect", input_bytes=b"a\xc2\xadb")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b"")
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest, inspect_text("a\u00adb"))

    def test_inspect_zero_findings_exits_zero(self):
        result = self.run_cli("inspect", input_bytes=b"plain text")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["findings"], [])

    def test_clean_reads_file_without_modifying_it(self):
        source = "a\u00adb\u00a0c"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.txt"
            path.write_text(source, encoding="utf-8")

            result = self.run_cli("clean", "--stats", str(path))

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.decode("utf-8"), "ab c")
            self.assertEqual(path.read_text(encoding="utf-8"), source)
            manifest = json.loads(result.stderr)
            self.assertEqual(manifest["summary"]["removed"], 1)
            self.assertEqual(manifest["summary"]["normalized"], 1)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
    def test_path_input_rejects_symbolic_link_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.txt"
            link = Path(directory) / "draft.txt"
            target.write_text("private\u200btext", encoding="utf-8")
            try:
                os.symlink(target, link)
            except OSError as error:
                self.skipTest(f"symbolic link unavailable: {error}")

            result = self.run_cli("clean", str(link), timeout=1)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"path input must be a regular file", result.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO files unavailable")
    def test_path_input_rejects_fifo_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.fifo"
            try:
                os.mkfifo(path)
            except OSError as error:
                self.skipTest(f"FIFO unavailable: {error}")

            result = self.run_cli("clean", str(path), timeout=1)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"path input must be a regular file", result.stderr)

    @unittest.skipUnless(
        hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
        "non-blocking FIFO files unavailable",
    )
    def test_path_input_rejects_fifo_replacement_after_lstat_without_blocking(self):
        harness = "\n".join(
            [
                "import os",
                "import sys",
                "import scripts.text_hygiene as text_hygiene",
                "real_lstat = os.lstat",
                "def swapping_lstat(path):",
                "    checked = real_lstat(path)",
                "    os.unlink(path)",
                "    os.mkfifo(path)",
                "    return checked",
                "text_hygiene.os.lstat = swapping_lstat",
                "raise SystemExit(text_hygiene.main(['clean', sys.argv[1]]))",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.txt"
            path.write_text("ordinary text", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-c", harness, str(path)],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=1,
            )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"path input must be a regular file", result.stderr)

    def test_clean_reads_standard_input(self):
        result = self.run_cli("clean", input_bytes="x\u200by".encode("utf-8"))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"xy")
        self.assertEqual(result.stderr, b"")

    def test_clean_preserves_exact_crlf_bytes(self):
        source = b"first\r\nsecond\r\n"

        result = self.run_cli("clean", input_bytes=source)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, source)
        self.assertEqual(result.stderr, b"")

    def test_clean_writes_non_ascii_utf8_when_text_encoding_is_ascii(self):
        source = "\u0410\u0412\u0421".encode("utf-8")

        result = self.run_cli(
            "clean",
            input_bytes=source,
            env={"PYTHONIOENCODING": "ascii"},
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, source)
        self.assertEqual(result.stderr, b"")

    def test_standard_input_over_byte_cap_returns_two_without_output(self):
        self.assertEqual(text_hygiene.MAX_INPUT_BYTES, EXPECTED_INPUT_CAP)

        result = self.run_cli("clean", input_bytes=b"a" * (EXPECTED_INPUT_CAP + 1))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"input exceeds 4194304-byte limit", result.stderr)

    def test_file_over_byte_cap_returns_two_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.txt"
            path.write_bytes(b"a" * (EXPECTED_INPUT_CAP + 1))

            result = self.run_cli("clean", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"input exceeds 4194304-byte limit", result.stderr)

    def test_clean_output_failure_returns_two_without_traceback(self):
        class BrokenOutput:
            @property
            def buffer(self):
                return self

            def write(self, _value):
                raise BrokenPipeError("closed")

        error_output = io.StringIO()
        with mock.patch.object(text_hygiene, "_read_input", return_value="text"):
            with mock.patch.object(text_hygiene.sys, "stdout", BrokenOutput()):
                with mock.patch.object(text_hygiene.sys, "stderr", error_output):
                    exit_code = text_hygiene.main(["clean"])

        self.assertEqual(exit_code, 2)
        self.assertIn("could not write output", error_output.getvalue())
        self.assertNotIn("Traceback", error_output.getvalue())

    def test_invalid_utf8_file_returns_processing_error_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.txt"
            path.write_bytes(b"valid\xffinvalid")

            result = self.run_cli("clean", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"invalid UTF-8 input", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_unreadable_or_missing_file_returns_processing_error(self):
        result = self.run_cli("inspect", "does-not-exist.txt")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"could not read input", result.stderr)


def unicode_data_rows(name):
    """Yield the semicolon-separated fields of one Unicode emoji data file."""
    path = Path(UNICODE_DATA_DIR) / name
    for line in path.read_text(encoding="utf-8").splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            yield [field.strip() for field in body.split(";")]


def code_point_sequence(field):
    return "".join(chr(int(value, 16)) for value in field.split())


@unittest.skipUnless(
    UNICODE_DATA_DIR,
    "set VOICEPRINT_UNICODE_DATA_DIR to run the Unicode data check",
)
class UnicodeDataTests(unittest.TestCase):
    """Check the pinned tables and cleanup against the official Unicode files."""

    DATA_FILES = (
        "emoji-sequences.txt",
        "emoji-variation-sequences.txt",
        "emoji-zwj-sequences.txt",
    )

    def test_data_files_match_the_pinned_emoji_version(self):
        for name in self.DATA_FILES:
            with self.subTest(name=name):
                text = (Path(UNICODE_DATA_DIR) / name).read_text(encoding="utf-8")
                self.assertIn(
                    f"# Version: {text_hygiene.EMOJI_ZWJ_VERSION}\n",
                    text,
                )
        properties = (Path(UNICODE_DATA_DIR) / "DerivedCoreProperties.txt").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            properties.startswith(
                f"# DerivedCoreProperties-{text_hygiene.EMOJI_ZWJ_VERSION}.0.txt"
            )
        )

    def test_pinned_zwj_pairs_match_the_zwj_sequence_data(self):
        skipped = {0xFE0E, 0xFE0F, *range(0x1F3FB, 0x1F400)}
        pairs = set()
        for field, *_ in unicode_data_rows("emoji-zwj-sequences.txt"):
            code_points = [int(value, 16) for value in field.split()]
            for index, code_point in enumerate(code_points):
                if code_point != 0x200D:
                    continue
                before = index - 1
                while code_points[before] in skipped:
                    before -= 1
                after = index + 1
                while code_points[after] in skipped:
                    after += 1
                pairs.add((code_points[before], code_points[after]))

        self.assertEqual(pairs, set(text_hygiene._EMOJI_ZWJ_PAIRS))

    def test_pinned_variation_bases_match_the_variation_sequence_data(self):
        bases = {
            int(field.split()[0], 16)
            for field, *_ in unicode_data_rows("emoji-variation-sequences.txt")
        }

        self.assertEqual(bases, set(text_hygiene._EMOJI_VARIATION_BASES))

    def test_pinned_tag_sequences_match_the_rgi_tag_sequences(self):
        sequences = {
            code_point_sequence(field)
            for field, kind, *_ in unicode_data_rows("emoji-sequences.txt")
            if kind == "RGI_Emoji_Tag_Sequence"
        }

        self.assertEqual(sequences, set(text_hygiene._EMOJI_TAG_SEQUENCES))

    def test_cleanup_leaves_every_rgi_emoji_sequence_unchanged(self):
        sequences = []
        for field, *_ in unicode_data_rows("emoji-sequences.txt"):
            if ".." in field:
                start, end = (int(value, 16) for value in field.split(".."))
                sequences.extend(chr(code_point) for code_point in range(start, end + 1))
            else:
                sequences.append(code_point_sequence(field))
        sequences.extend(
            code_point_sequence(field)
            for field, *_ in unicode_data_rows("emoji-zwj-sequences.txt")
        )

        changed = [
            hex_sequence(sequence)
            for sequence in sequences
            if clean_text(sequence)[0] != sequence
        ]

        self.assertEqual(changed, [])
        print(f"Unicode data check: {len(sequences)} RGI emoji sequences unchanged")

    def test_cleanup_leaves_every_variation_sequence_unchanged(self):
        changed = []
        for field, *_ in unicode_data_rows("emoji-variation-sequences.txt"):
            sequence = code_point_sequence(field)
            if ord(sequence[0]) in text_hygiene._KEYCAP_BASES:
                sequence += "\u20e3"
            if clean_text(sequence)[0] != sequence:
                changed.append(hex_sequence(sequence))

        self.assertEqual(changed, [])

    def test_every_default_ignorable_code_point_is_detected(self):
        undetected = []
        kept_unassigned = []
        path = Path(UNICODE_DATA_DIR) / "DerivedCoreProperties.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            body, _, comment = line.partition("#")
            fields = [field.strip() for field in body.split(";")]
            if fields[-1] != "Default_Ignorable_Code_Point":
                continue
            start, _, end = fields[0].partition("..")
            unassigned = comment.split()[0] == "Cn"
            for code_point in range(int(start, 16), int(end or start, 16) + 1):
                cleaned, manifest = clean_text("a" + chr(code_point) + "b")
                if manifest["summary"]["detected"] != 1:
                    undetected.append(f"U+{code_point:04X}")
                if unassigned and cleaned != "ab":
                    kept_unassigned.append(f"U+{code_point:04X}")

        self.assertEqual(undetected, [])
        self.assertEqual(kept_unassigned, [])


if __name__ == "__main__":
    unittest.main()
