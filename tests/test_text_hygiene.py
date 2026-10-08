#!/usr/bin/env python3
"""Exact behavior tests for Voiceprint's deterministic Unicode hygiene."""

import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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
        self.assertEqual(manifest["policy_version"], 2)
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
