#!/usr/bin/env python3
"""Inspect and clean text-only Unicode artifacts without changing source files."""

from __future__ import annotations

import argparse
from array import array
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from itertools import accumulate, chain
import json
import os
import re
import stat
import sys
import unicodedata
from typing import NamedTuple


_JOINERS = {"\u200c", "\u200d"}
_MONGOLIAN_VARIATION_SELECTORS = range(0x180B, 0x180E)
_MONGOLIAN_VOWEL_SEPARATOR = 0x180E
MAX_INPUT_BYTES = 4 * 1024 * 1024
POLICY_VERSION = 3
# Unicode Emoji version of every pinned emoji table below.
EMOJI_ZWJ_VERSION = "17.0"
_SCRIPT_FAMILY_RANGES = (
    ("arabic", ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x08FF))),
    ("syriac", ((0x0700, 0x074F), (0x0860, 0x086F))),
    ("thaana", ((0x0780, 0x07BF),)),
    ("devanagari", ((0x0900, 0x097F), (0xA8E0, 0xA8FF))),
    ("bengali", ((0x0980, 0x09FF),)),
    ("gurmukhi", ((0x0A00, 0x0A7F),)),
    ("gujarati", ((0x0A80, 0x0AFF),)),
    ("odia", ((0x0B00, 0x0B7F),)),
    ("tamil", ((0x0B80, 0x0BFF),)),
    ("telugu", ((0x0C00, 0x0C7F),)),
    ("kannada", ((0x0C80, 0x0CFF),)),
    ("malayalam", ((0x0D00, 0x0D7F),)),
    ("sinhala", ((0x0D80, 0x0DFF),)),
    ("myanmar", ((0x1000, 0x109F), (0xAA60, 0xAA7F))),
    ("khmer", ((0x1780, 0x17FF),)),
    ("mongolian", ((0x1800, 0x18AF),)),
    ("syloti-nagri", ((0xA800, 0xA82F),)),
    ("saurashtra", ((0xA880, 0xA8DF),)),
    ("javanese", ((0xA980, 0xA9DF),)),
    ("cham", ((0xAA00, 0xAA5F),)),
    ("meetei-mayek", ((0xABC0, 0xABFF),)),
)
_REMOVABLE_FORMAT_CODE_POINTS = {
    0x00AD,
    0x200B,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2060,
    0x2061,
    0x2062,
    0x2063,
    0x2064,
    0x2065,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
    0x206A,
    0x206B,
    0x206C,
    0x206D,
    0x206E,
    0x206F,
    0xFEFF,
    0xFFF9,
    0xFFFA,
    0xFFFB,
}
# Default_Ignorable_Code_Point ranges that are unassigned in Unicode 17.0
# (https://www.unicode.org/Public/17.0.0/ucd/DerivedCoreProperties.txt). U+2065
# and the reserved code points in the tag block are covered above.
_UNASSIGNED_DEFAULT_IGNORABLE_RANGES = (
    (0xFFF0, 0xFFF8),
    (0xE0080, 0xE00FF),
    (0xE01F0, 0xE0FFF),
)
_UNASSIGNED_DEFAULT_IGNORABLE_CODE_POINTS = frozenset(
    code_point
    for start, end in _UNASSIGNED_DEFAULT_IGNORABLE_RANGES
    for code_point in range(start, end + 1)
)
# Assigned default-ignorable letters and marks that render invisibly but have
# orthographic uses, so they are reported rather than removed: the combining
# grapheme joiner, the Hangul fillers, and the Khmer inherent vowels.
_INVISIBLE_LETTERS_AND_MARKS = frozenset(
    {0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0}
)
# No-break spaces are kept only where they hold a number, a unit, or French
# punctuation together. Elsewhere they are normalized: a no-break space looks
# like any other space, so swapping one in at a word gap can hide a mark.
_NO_BREAK_SPACES = frozenset({chr(0x00A0), chr(0x202F), chr(0x2007)})
_FIGURE_SPACE = chr(0x2007)
_IDEOGRAPHIC_SPACE = chr(0x3000)
_FRENCH_CLOSING_PUNCTUATION = frozenset(
    {"!", "?", ";", ":", chr(0x00BB), chr(0x203A)}
)
_FRENCH_OPENING_QUOTES = frozenset({chr(0x00AB), chr(0x2039)})
_PERCENT_SIGNS = frozenset({"%", chr(0x2030), chr(0x2031)})
_CJK_RANGES = (
    (0x1100, 0x11FF),
    (0x2E80, 0x2FFF),
    (0x3001, 0x303F),
    (0x3040, 0x30FF),
    (0x3100, 0x31FF),
    (0x3200, 0x9FFF),
    (0xA960, 0xA97F),
    (0xAC00, 0xD7FF),
    (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
    (0x1AFF0, 0x1B16F),
    (0x20000, 0x3FFFF),
)
# The implicit directional marks: LEFT-TO-RIGHT MARK, RIGHT-TO-LEFT MARK, and
# ARABIC LETTER MARK. Embeddings, overrides, and isolates are always removed.
_DIRECTIONAL_MARKS = frozenset({chr(0x200E), chr(0x200F), chr(0x061C)})
_MARK_PATTERN = re.compile("[" + "".join(sorted(_DIRECTIONAL_MARKS)) + "]")
_EXPLICIT_DIRECTIONAL_CONTROLS = tuple(
    chr(code_point) for code_point in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))
)
_EXPLICIT_PATTERN = re.compile("[" + "".join(_EXPLICIT_DIRECTIONAL_CONTROLS) + "]")
# No right-to-left letter comes before U+0590.
_BEYOND_LATIN = re.compile(f"[{chr(0x0590)}-{chr(0x10FFFF)}]")
# Hygiene never acts on a character below U+00A0.
_FIRST_ACTED_ON = chr(0x00A0)
_STRONG_DIRECTIONS = frozenset({"L", "R", "AL"})
_NEUTRAL_TYPES = frozenset({"B", "S", "WS", "ON"})
# Bidi_Class defaults for code points the running Python leaves unassigned,
# from the @missing lines of
# https://www.unicode.org/Public/17.0.0/ucd/extracted/DerivedBidiClass.txt.
# Other unassigned code points default to BN (noncharacters and
# default-ignorable code points) or L.
_DEFAULT_BIDI_RANGES = (
    (0x0590, 0x05FF, "R"),
    (0x0600, 0x07BF, "AL"),
    (0x07C0, 0x085F, "R"),
    (0x0860, 0x08FF, "AL"),
    (0x20A0, 0x20CF, "ET"),
    (0xFB1D, 0xFB4F, "R"),
    (0xFB50, 0xFDCF, "AL"),
    (0xFDF0, 0xFDFF, "AL"),
    (0xFE70, 0xFEFF, "AL"),
    (0x10800, 0x10CFF, "R"),
    (0x10D00, 0x10D3F, "AL"),
    (0x10D40, 0x10EBF, "R"),
    (0x10EC0, 0x10EFF, "AL"),
    (0x10F00, 0x10F2F, "R"),
    (0x10F30, 0x10F6F, "AL"),
    (0x10F70, 0x10FFF, "R"),
    (0x1E800, 0x1EC6F, "R"),
    (0x1EC70, 0x1ECBF, "AL"),
    (0x1ECC0, 0x1ECFF, "R"),
    (0x1ED00, 0x1ED4F, "AL"),
    (0x1ED50, 0x1EDFF, "R"),
    (0x1EE00, 0x1EEFF, "AL"),
    (0x1EF00, 0x1EFFF, "R"),
)
# A mark is judged on the characters between the nearest letters around it,
# at most this many on each side. A mark farther from a letter is removed:
# such long runs without letters are rare in prose, and keeping their marks
# unjudged would leave room to hide data.
_MARK_WINDOW = 64
# How many characters judging may examine in one text. 4 MiB of short mixed
# Arabic, Hebrew, and English paragraphs with 227,000 marks needed three
# quarters of it in testing. Once it runs out, the paragraph being judged and
# every later one keep none of their marks, which bounds the time adversarial
# input can take.
_MARK_BUDGET = 4_000_000
# Judging repeats while a pass removes marks, up to this many passes.
_MARK_PASSES = 8
# A window widened over bracket pairs may span at most this many characters;
# a mark whose window would grow past it is removed.
_MARK_SPAN = 4096
# Judgments are remembered by the shape of the text around the mark, up to
# this many shapes per text.
_MARK_CACHE_SIZE = 65_536
_SETS_DIRECTION = "directional mark that sets its paragraph's direction"
_CHANGES_DISPLAY = (
    "directional mark that changes the order or mirroring of nearby characters"
)
# Opening and closing brackets that pair under bidi rule N0, from
# https://www.unicode.org/Public/17.0.0/ucd/BidiBrackets.txt.
_BRACKET_PAIRS = (
    (0x0028, 0x0029), (0x005B, 0x005D), (0x007B, 0x007D), (0x0F3A, 0x0F3B),
    (0x0F3C, 0x0F3D), (0x169B, 0x169C), (0x2045, 0x2046), (0x207D, 0x207E),
    (0x208D, 0x208E), (0x2308, 0x2309), (0x230A, 0x230B), (0x2329, 0x232A),
    (0x2768, 0x2769), (0x276A, 0x276B), (0x276C, 0x276D), (0x276E, 0x276F),
    (0x2770, 0x2771), (0x2772, 0x2773), (0x2774, 0x2775), (0x27C5, 0x27C6),
    (0x27E6, 0x27E7), (0x27E8, 0x27E9), (0x27EA, 0x27EB), (0x27EC, 0x27ED),
    (0x27EE, 0x27EF), (0x2983, 0x2984), (0x2985, 0x2986), (0x2987, 0x2988),
    (0x2989, 0x298A), (0x298B, 0x298C), (0x298D, 0x2990), (0x298F, 0x298E),
    (0x2991, 0x2992), (0x2993, 0x2994), (0x2995, 0x2996), (0x2997, 0x2998),
    (0x29D8, 0x29D9), (0x29DA, 0x29DB), (0x29FC, 0x29FD), (0x2E22, 0x2E23),
    (0x2E24, 0x2E25), (0x2E26, 0x2E27), (0x2E28, 0x2E29), (0x2E55, 0x2E56),
    (0x2E57, 0x2E58), (0x2E59, 0x2E5A), (0x2E5B, 0x2E5C), (0x3008, 0x3009),
    (0x300A, 0x300B), (0x300C, 0x300D), (0x300E, 0x300F), (0x3010, 0x3011),
    (0x3014, 0x3015), (0x3016, 0x3017), (0x3018, 0x3019), (0x301A, 0x301B),
    (0xFE59, 0xFE5A), (0xFE5B, 0xFE5C), (0xFE5D, 0xFE5E), (0xFF08, 0xFF09),
    (0xFF3B, 0xFF3D), (0xFF5B, 0xFF5D), (0xFF5F, 0xFF60), (0xFF62, 0xFF63),
)
_CLOSING_BRACKETS = {chr(closing): chr(opening) for opening, closing in _BRACKET_PAIRS}
_OPENING_BRACKETS = frozenset(chr(opening) for opening, _ in _BRACKET_PAIRS)
_PAIRED_BRACKETS = _OPENING_BRACKETS | frozenset(_CLOSING_BRACKETS)
# Canonically equivalent brackets pair with each other's partners.
_CANONICAL_BRACKETS = {chr(0x2329): chr(0x3008), chr(0x232A): chr(0x3009)}
_BRACKET_PATTERN = re.compile("[" + re.escape("".join(sorted(_PAIRED_BRACKETS))) + "]")
# The bracket-pair search stops after this many unclosed opening brackets.
_BRACKET_DEPTH = 63
# The characters of bidi class B, each of which ends a paragraph.
_PARAGRAPH_SEPARATORS = "".join(
    chr(code_point) for code_point in (0x0A, 0x0D, 0x1C, 0x1D, 0x1E, 0x85, 0x2029)
)
_PARAGRAPH_BREAK = re.compile(f"[{re.escape(_PARAGRAPH_SEPARATORS)}]")
# Derived from https://www.unicode.org/Public/17.0.0/emoji/emoji-zwj-sequences.txt
# by taking the numeric base pair on each side of U+200D.
_EMOJI_ZWJ_PAIRS = frozenset(
    {
        (0x2640, 0x27A1),
        (0x2642, 0x27A1),
        (0x26D3, 0x1F4A5),
        (0x26F9, 0x2640),
        (0x26F9, 0x2642),
        (0x2764, 0x1F468),
        (0x2764, 0x1F469),
        (0x2764, 0x1F48B),
        (0x2764, 0x1F525),
        (0x2764, 0x1F9D1),
        (0x2764, 0x1FA79),
        (0x1F344, 0x1F7EB),
        (0x1F34B, 0x1F7E9),
        (0x1F3C3, 0x2640),
        (0x1F3C3, 0x2642),
        (0x1F3C3, 0x27A1),
        (0x1F3C4, 0x2640),
        (0x1F3C4, 0x2642),
        (0x1F3CA, 0x2640),
        (0x1F3CA, 0x2642),
        (0x1F3CB, 0x2640),
        (0x1F3CB, 0x2642),
        (0x1F3CC, 0x2640),
        (0x1F3CC, 0x2642),
        (0x1F3F3, 0x26A7),
        (0x1F3F3, 0x1F308),
        (0x1F3F4, 0x2620),
        (0x1F408, 0x2B1B),
        (0x1F415, 0x1F9BA),
        (0x1F426, 0x2B1B),
        (0x1F426, 0x1F525),
        (0x1F430, 0x1F468),
        (0x1F430, 0x1F469),
        (0x1F430, 0x1F9D1),
        (0x1F43B, 0x2744),
        (0x1F441, 0x1F5E8),
        (0x1F466, 0x1F466),
        (0x1F467, 0x1F466),
        (0x1F467, 0x1F467),
        (0x1F468, 0x2695),
        (0x1F468, 0x2696),
        (0x1F468, 0x2708),
        (0x1F468, 0x2764),
        (0x1F468, 0x1F33E),
        (0x1F468, 0x1F373),
        (0x1F468, 0x1F37C),
        (0x1F468, 0x1F393),
        (0x1F468, 0x1F3A4),
        (0x1F468, 0x1F3A8),
        (0x1F468, 0x1F3EB),
        (0x1F468, 0x1F3ED),
        (0x1F468, 0x1F430),
        (0x1F468, 0x1F466),
        (0x1F468, 0x1F467),
        (0x1F468, 0x1F468),
        (0x1F468, 0x1F469),
        (0x1F468, 0x1F4BB),
        (0x1F468, 0x1F4BC),
        (0x1F468, 0x1F527),
        (0x1F468, 0x1F52C),
        (0x1F468, 0x1F680),
        (0x1F468, 0x1F692),
        (0x1F468, 0x1F91D),
        (0x1F468, 0x1F9AF),
        (0x1F468, 0x1F9B0),
        (0x1F468, 0x1F9B1),
        (0x1F468, 0x1F9B2),
        (0x1F468, 0x1F9B3),
        (0x1F468, 0x1F9BC),
        (0x1F468, 0x1F9BD),
        (0x1F468, 0x1FAEF),
        (0x1F469, 0x2695),
        (0x1F469, 0x2696),
        (0x1F469, 0x2708),
        (0x1F469, 0x2764),
        (0x1F469, 0x1F33E),
        (0x1F469, 0x1F373),
        (0x1F469, 0x1F37C),
        (0x1F469, 0x1F393),
        (0x1F469, 0x1F3A4),
        (0x1F469, 0x1F3A8),
        (0x1F469, 0x1F3EB),
        (0x1F469, 0x1F3ED),
        (0x1F469, 0x1F430),
        (0x1F469, 0x1F466),
        (0x1F469, 0x1F467),
        (0x1F469, 0x1F469),
        (0x1F469, 0x1F4BB),
        (0x1F469, 0x1F4BC),
        (0x1F469, 0x1F527),
        (0x1F469, 0x1F52C),
        (0x1F469, 0x1F680),
        (0x1F469, 0x1F692),
        (0x1F469, 0x1F91D),
        (0x1F469, 0x1F9AF),
        (0x1F469, 0x1F9B0),
        (0x1F469, 0x1F9B1),
        (0x1F469, 0x1F9B2),
        (0x1F469, 0x1F9B3),
        (0x1F469, 0x1F9BC),
        (0x1F469, 0x1F9BD),
        (0x1F469, 0x1FAEF),
        (0x1F46E, 0x2640),
        (0x1F46E, 0x2642),
        (0x1F46F, 0x2640),
        (0x1F46F, 0x2642),
        (0x1F470, 0x2640),
        (0x1F470, 0x2642),
        (0x1F471, 0x2640),
        (0x1F471, 0x2642),
        (0x1F473, 0x2640),
        (0x1F473, 0x2642),
        (0x1F477, 0x2640),
        (0x1F477, 0x2642),
        (0x1F481, 0x2640),
        (0x1F481, 0x2642),
        (0x1F482, 0x2640),
        (0x1F482, 0x2642),
        (0x1F486, 0x2640),
        (0x1F486, 0x2642),
        (0x1F487, 0x2640),
        (0x1F487, 0x2642),
        (0x1F48B, 0x1F468),
        (0x1F48B, 0x1F469),
        (0x1F48B, 0x1F9D1),
        (0x1F575, 0x2640),
        (0x1F575, 0x2642),
        (0x1F62E, 0x1F4A8),
        (0x1F635, 0x1F4AB),
        (0x1F636, 0x1F32B),
        (0x1F642, 0x2194),
        (0x1F642, 0x2195),
        (0x1F645, 0x2640),
        (0x1F645, 0x2642),
        (0x1F646, 0x2640),
        (0x1F646, 0x2642),
        (0x1F647, 0x2640),
        (0x1F647, 0x2642),
        (0x1F64B, 0x2640),
        (0x1F64B, 0x2642),
        (0x1F64D, 0x2640),
        (0x1F64D, 0x2642),
        (0x1F64E, 0x2640),
        (0x1F64E, 0x2642),
        (0x1F6A3, 0x2640),
        (0x1F6A3, 0x2642),
        (0x1F6B4, 0x2640),
        (0x1F6B4, 0x2642),
        (0x1F6B5, 0x2640),
        (0x1F6B5, 0x2642),
        (0x1F6B6, 0x2640),
        (0x1F6B6, 0x2642),
        (0x1F6B6, 0x27A1),
        (0x1F91D, 0x1F468),
        (0x1F91D, 0x1F469),
        (0x1F91D, 0x1F9D1),
        (0x1F926, 0x2640),
        (0x1F926, 0x2642),
        (0x1F935, 0x2640),
        (0x1F935, 0x2642),
        (0x1F937, 0x2640),
        (0x1F937, 0x2642),
        (0x1F938, 0x2640),
        (0x1F938, 0x2642),
        (0x1F939, 0x2640),
        (0x1F939, 0x2642),
        (0x1F93C, 0x2640),
        (0x1F93C, 0x2642),
        (0x1F93D, 0x2640),
        (0x1F93D, 0x2642),
        (0x1F93E, 0x2640),
        (0x1F93E, 0x2642),
        (0x1F9AF, 0x27A1),
        (0x1F9B8, 0x2640),
        (0x1F9B8, 0x2642),
        (0x1F9B9, 0x2640),
        (0x1F9B9, 0x2642),
        (0x1F9BC, 0x27A1),
        (0x1F9BD, 0x27A1),
        (0x1F9CD, 0x2640),
        (0x1F9CD, 0x2642),
        (0x1F9CE, 0x2640),
        (0x1F9CE, 0x2642),
        (0x1F9CE, 0x27A1),
        (0x1F9CF, 0x2640),
        (0x1F9CF, 0x2642),
        (0x1F9D1, 0x2695),
        (0x1F9D1, 0x2696),
        (0x1F9D1, 0x2708),
        (0x1F9D1, 0x2764),
        (0x1F9D1, 0x1F33E),
        (0x1F9D1, 0x1F373),
        (0x1F9D1, 0x1F37C),
        (0x1F9D1, 0x1F384),
        (0x1F9D1, 0x1F393),
        (0x1F9D1, 0x1F3A4),
        (0x1F9D1, 0x1F3A8),
        (0x1F9D1, 0x1F3EB),
        (0x1F9D1, 0x1F3ED),
        (0x1F9D1, 0x1F430),
        (0x1F9D1, 0x1F4BB),
        (0x1F9D1, 0x1F4BC),
        (0x1F9D1, 0x1F527),
        (0x1F9D1, 0x1F52C),
        (0x1F9D1, 0x1F680),
        (0x1F9D1, 0x1F692),
        (0x1F9D1, 0x1F91D),
        (0x1F9D1, 0x1F9AF),
        (0x1F9D1, 0x1F9B0),
        (0x1F9D1, 0x1F9B1),
        (0x1F9D1, 0x1F9B2),
        (0x1F9D1, 0x1F9B3),
        (0x1F9D1, 0x1F9BC),
        (0x1F9D1, 0x1F9BD),
        (0x1F9D1, 0x1F9D1),
        (0x1F9D1, 0x1F9D2),
        (0x1F9D1, 0x1FA70),
        (0x1F9D1, 0x1FAEF),
        (0x1F9D2, 0x1F9D2),
        (0x1F9D4, 0x2640),
        (0x1F9D4, 0x2642),
        (0x1F9D6, 0x2640),
        (0x1F9D6, 0x2642),
        (0x1F9D7, 0x2640),
        (0x1F9D7, 0x2642),
        (0x1F9D8, 0x2640),
        (0x1F9D8, 0x2642),
        (0x1F9D9, 0x2640),
        (0x1F9D9, 0x2642),
        (0x1F9DA, 0x2640),
        (0x1F9DA, 0x2642),
        (0x1F9DB, 0x2640),
        (0x1F9DB, 0x2642),
        (0x1F9DC, 0x2640),
        (0x1F9DC, 0x2642),
        (0x1F9DD, 0x2640),
        (0x1F9DD, 0x2642),
        (0x1F9DE, 0x2640),
        (0x1F9DE, 0x2642),
        (0x1F9DF, 0x2640),
        (0x1F9DF, 0x2642),
        (0x1FAEF, 0x1F468),
        (0x1FAEF, 0x1F469),
        (0x1FAEF, 0x1F9D1),
        (0x1FAF1, 0x1FAF2),
    }
)
_EMOJI_ZWJ_BASES = frozenset(
    code_point for pair in _EMOJI_ZWJ_PAIRS for code_point in pair
)
# Derived from https://www.unicode.org/Public/17.0.0/ucd/emoji/emoji-variation-sequences.txt
# by taking the base of each sequence. Every base there has both a text
# (U+FE0E) and an emoji (U+FE0F) presentation sequence.
_EMOJI_VARIATION_BASES = frozenset(
    {
        0x0023, 0x002A, 0x0030, 0x0031, 0x0032, 0x0033,
        0x0034, 0x0035, 0x0036, 0x0037, 0x0038, 0x0039,
        0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139,
        0x2194, 0x2195, 0x2196, 0x2197, 0x2198, 0x2199,
        0x21A9, 0x21AA, 0x231A, 0x231B, 0x2328, 0x23CF,
        0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23ED, 0x23EE,
        0x23EF, 0x23F0, 0x23F1, 0x23F2, 0x23F3, 0x23F8,
        0x23F9, 0x23FA, 0x24C2, 0x25AA, 0x25AB, 0x25B6,
        0x25C0, 0x25FB, 0x25FC, 0x25FD, 0x25FE, 0x2600,
        0x2601, 0x2602, 0x2603, 0x2604, 0x260E, 0x2611,
        0x2614, 0x2615, 0x2618, 0x261D, 0x2620, 0x2622,
        0x2623, 0x2626, 0x262A, 0x262E, 0x262F, 0x2638,
        0x2639, 0x263A, 0x2640, 0x2642, 0x2648, 0x2649,
        0x264A, 0x264B, 0x264C, 0x264D, 0x264E, 0x264F,
        0x2650, 0x2651, 0x2652, 0x2653, 0x265F, 0x2660,
        0x2663, 0x2665, 0x2666, 0x2668, 0x267B, 0x267E,
        0x267F, 0x2692, 0x2693, 0x2694, 0x2695, 0x2696,
        0x2697, 0x2699, 0x269B, 0x269C, 0x26A0, 0x26A1,
        0x26A7, 0x26AA, 0x26AB, 0x26B0, 0x26B1, 0x26BD,
        0x26BE, 0x26C4, 0x26C5, 0x26C8, 0x26CE, 0x26CF,
        0x26D1, 0x26D3, 0x26D4, 0x26E9, 0x26EA, 0x26F0,
        0x26F1, 0x26F2, 0x26F3, 0x26F4, 0x26F5, 0x26F7,
        0x26F8, 0x26F9, 0x26FA, 0x26FD, 0x2702, 0x2705,
        0x2708, 0x2709, 0x270A, 0x270B, 0x270C, 0x270D,
        0x270F, 0x2712, 0x2714, 0x2716, 0x271D, 0x2721,
        0x2728, 0x2733, 0x2734, 0x2744, 0x2747, 0x274C,
        0x274E, 0x2753, 0x2754, 0x2755, 0x2757, 0x2763,
        0x2764, 0x2795, 0x2796, 0x2797, 0x27A1, 0x27B0,
        0x27BF, 0x2934, 0x2935, 0x2B05, 0x2B06, 0x2B07,
        0x2B1B, 0x2B1C, 0x2B50, 0x2B55, 0x3030, 0x303D,
        0x3297, 0x3299, 0x1F004, 0x1F170, 0x1F171, 0x1F17E,
        0x1F17F, 0x1F202, 0x1F21A, 0x1F22F, 0x1F237, 0x1F30D,
        0x1F30E, 0x1F30F, 0x1F315, 0x1F31C, 0x1F321, 0x1F324,
        0x1F325, 0x1F326, 0x1F327, 0x1F328, 0x1F329, 0x1F32A,
        0x1F32B, 0x1F32C, 0x1F336, 0x1F378, 0x1F37D, 0x1F393,
        0x1F396, 0x1F397, 0x1F399, 0x1F39A, 0x1F39B, 0x1F39E,
        0x1F39F, 0x1F3A7, 0x1F3AC, 0x1F3AD, 0x1F3AE, 0x1F3C2,
        0x1F3C4, 0x1F3C6, 0x1F3CA, 0x1F3CB, 0x1F3CC, 0x1F3CD,
        0x1F3CE, 0x1F3D4, 0x1F3D5, 0x1F3D6, 0x1F3D7, 0x1F3D8,
        0x1F3D9, 0x1F3DA, 0x1F3DB, 0x1F3DC, 0x1F3DD, 0x1F3DE,
        0x1F3DF, 0x1F3E0, 0x1F3ED, 0x1F3F3, 0x1F3F5, 0x1F3F7,
        0x1F408, 0x1F415, 0x1F41F, 0x1F426, 0x1F43F, 0x1F441,
        0x1F442, 0x1F446, 0x1F447, 0x1F448, 0x1F449, 0x1F44D,
        0x1F44E, 0x1F453, 0x1F46A, 0x1F47D, 0x1F4A3, 0x1F4B0,
        0x1F4B3, 0x1F4BB, 0x1F4BF, 0x1F4CB, 0x1F4DA, 0x1F4DF,
        0x1F4E4, 0x1F4E5, 0x1F4E6, 0x1F4EA, 0x1F4EB, 0x1F4EC,
        0x1F4ED, 0x1F4F7, 0x1F4F9, 0x1F4FA, 0x1F4FB, 0x1F4FD,
        0x1F508, 0x1F50D, 0x1F512, 0x1F513, 0x1F549, 0x1F54A,
        0x1F550, 0x1F551, 0x1F552, 0x1F553, 0x1F554, 0x1F555,
        0x1F556, 0x1F557, 0x1F558, 0x1F559, 0x1F55A, 0x1F55B,
        0x1F55C, 0x1F55D, 0x1F55E, 0x1F55F, 0x1F560, 0x1F561,
        0x1F562, 0x1F563, 0x1F564, 0x1F565, 0x1F566, 0x1F567,
        0x1F56F, 0x1F570, 0x1F573, 0x1F574, 0x1F575, 0x1F576,
        0x1F577, 0x1F578, 0x1F579, 0x1F587, 0x1F58A, 0x1F58B,
        0x1F58C, 0x1F58D, 0x1F590, 0x1F5A5, 0x1F5A8, 0x1F5B1,
        0x1F5B2, 0x1F5BC, 0x1F5C2, 0x1F5C3, 0x1F5C4, 0x1F5D1,
        0x1F5D2, 0x1F5D3, 0x1F5DC, 0x1F5DD, 0x1F5DE, 0x1F5E1,
        0x1F5E3, 0x1F5E8, 0x1F5EF, 0x1F5F3, 0x1F5FA, 0x1F610,
        0x1F687, 0x1F68D, 0x1F691, 0x1F694, 0x1F698, 0x1F6AD,
        0x1F6B2, 0x1F6B9, 0x1F6BA, 0x1F6BC, 0x1F6CB, 0x1F6CD,
        0x1F6CE, 0x1F6CF, 0x1F6E0, 0x1F6E1, 0x1F6E2, 0x1F6E3,
        0x1F6E4, 0x1F6E5, 0x1F6E9, 0x1F6F0, 0x1F6F3,
    }
)
# "#", "*", and the digits are ordinary prose characters. Their selector is
# load-bearing only inside an emoji keycap sequence, which ends with U+20E3.
_KEYCAP_BASES = frozenset({0x0023, 0x002A, *range(0x0030, 0x003A)})
_COMBINING_ENCLOSING_KEYCAP = "\u20e3"
# Derived from https://www.unicode.org/Public/17.0.0/emoji/emoji-sequences.txt
# (RGI_Emoji_Tag_Sequence): U+1F3F4, tag characters, then U+E007F.
_EMOJI_TAG_BASE = "\U0001f3f4"
_EMOJI_TAG_SEQUENCES = (
    "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
)


def _in_ranges(code_point: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= code_point <= end for start, end in ranges)


def _is_variation_selector(character: str) -> bool:
    code_point = ord(character)
    return (
        code_point in _MONGOLIAN_VARIATION_SELECTORS
        or code_point == 0x180F
        or 0xFE00 <= code_point <= 0xFE0F
        or 0xE0100 <= code_point <= 0xE01EF
    )


def _script_family(character: str) -> str | None:
    if unicodedata.category(character)[0] != "L":
        return None
    code_point = ord(character)
    for family, ranges in _SCRIPT_FAMILY_RANGES:
        if _in_ranges(code_point, ranges):
            return family
    return None


def _is_emoji_variation_sequence(text: str, offset: int) -> bool:
    """Whether the selector at offset directly follows a pinned variation base."""
    if offset == 0 or ord(text[offset - 1]) not in _EMOJI_VARIATION_BASES:
        return False
    if ord(text[offset - 1]) in _KEYCAP_BASES:
        return text[offset + 1 : offset + 2] == _COMBINING_ENCLOSING_KEYCAP
    return True


def _tag_sequence_offsets(text: str) -> frozenset[int]:
    """Offsets of tag characters that belong to a pinned emoji tag sequence."""
    offsets: set[int] = set()
    start = text.find(_EMOJI_TAG_BASE)
    while start != -1:
        for sequence in _EMOJI_TAG_SEQUENCES:
            if text.startswith(sequence, start):
                offsets.update(range(start + 1, start + len(sequence)))
                break
        start = text.find(_EMOJI_TAG_BASE, start + 1)
    return frozenset(offsets)


def _is_zero_width(character: str) -> bool:
    """Whether a character takes no space of its own: format controls and marks."""
    return unicodedata.category(character) in (
        "Cf",
        "Mn",
        "Me",
    ) or _is_explicit_removal(ord(character))


def _visible_neighbor(text: str, offset: int, step: int) -> str:
    """The nearest character that takes space before (-1) or after (+1) offset."""
    offset += step
    while 0 <= offset < len(text) and _is_zero_width(text[offset]):
        offset += step
    return text[offset] if 0 <= offset < len(text) else ""


def _unit_follows(text: str, offset: int) -> bool:
    """Whether one to three letters, then a non-letter or the end, follow offset."""
    letters = 0
    for character in text[offset + 1 : offset + 16]:
        if _is_zero_width(character):
            continue
        if (
            unicodedata.category(character)[0] != "L"
            or ord(character) in _INVISIBLE_LETTERS_AND_MARKS
        ):
            return 0 < letters
        letters += 1
        if letters > 3:
            return False
    return 0 < letters <= 3 and offset + 16 >= len(text)


def _no_break_reason(text: str, offset: int) -> str | None:
    """Why a no-break space holds typography together, or None.

    The neighbors are the nearest characters that take space, so an invisible
    character beside the space, removed or kept, never changes the answer.
    """
    before = _visible_neighbor(text, offset, -1)
    after = _visible_neighbor(text, offset, 1)
    digit_before = bool(before) and unicodedata.category(before) == "Nd"
    if digit_before and after and unicodedata.category(after) == "Nd":
        return "no-break space inside a number"
    if text[offset] == _FIGURE_SPACE:
        return None
    if (
        digit_before
        and after
        and (
            after in _PERCENT_SIGNS
            or unicodedata.category(after)[0] == "S"
            or _unit_follows(text, offset)
        )
    ):
        return "no-break space between a number and a unit or symbol"
    if (
        after in _FRENCH_CLOSING_PUNCTUATION and before and not before.isspace()
    ) or (before in _FRENCH_OPENING_QUOTES and after and not after.isspace()):
        return "no-break space at French punctuation or quotation marks"
    return None


def _is_cjk(character: str) -> bool:
    code_point = ord(character)
    return (
        _in_ranges(code_point, _CJK_RANGES)
        and code_point not in _INVISIBLE_LETTERS_AND_MARKS
        and unicodedata.category(character)[0] in "LNPS"
    )


def _cjk_space_offsets(text: str) -> frozenset[int]:
    """Offsets of ideographic spaces in runs that touch CJK text."""
    offsets: set[int] = set()
    start = text.find(_IDEOGRAPHIC_SPACE)
    while start != -1:
        end = start
        while end < len(text) and text[end] == _IDEOGRAPHIC_SPACE:
            end += 1
        before = _visible_neighbor(text, start, -1)
        after = _visible_neighbor(text, end - 1, 1)
        if (before and _is_cjk(before)) or (after and _is_cjk(after)):
            offsets.update(range(start, end))
        start = text.find(_IDEOGRAPHIC_SPACE, end)
    return frozenset(offsets)


def _paragraphs(text: str) -> Iterator[tuple[int, int]]:
    """Yield the start and end offsets of each bidi paragraph."""
    start = 0
    for match in _PARAGRAPH_BREAK.finditer(text):
        yield start, match.start()
        start = match.end()
    yield start, len(text)


def _bidi_class(character: str) -> str:
    """The Bidi_Class of a character, with Unicode's default when unassigned."""
    bidi_class = unicodedata.bidirectional(character)
    if bidi_class:
        return bidi_class
    code_point = ord(character)
    if (
        0xFDD0 <= code_point <= 0xFDEF
        or code_point & 0xFFFE == 0xFFFE
        or code_point == 0x2065
        or 0xFFF0 <= code_point <= 0xFFF8
        or 0xE0000 <= code_point <= 0xE0FFF
    ):
        return "BN"
    for start, end, default in _DEFAULT_BIDI_RANGES:
        if start <= code_point <= end:
            return default
    return "L"


def _direction(bidi_class: str) -> str:
    return "L" if bidi_class == "L" else "R"


def _resolve_levels(
    classes: list[str],
    base_level: int,
    line_end: bool,
    pairs: list[tuple[int, int]] = (),
    fixed: dict[int, str] | None = None,
) -> list[int]:
    """Embedding levels for a stretch of one paragraph (bidi rules W1 to I2, L1).

    The stretch must hold every strong character that its weak and neutral
    characters depend on, so it runs from a strong character, or the start of
    the paragraph, to a strong character, or the end. For rule N0, pairs are
    the bracket pairs inside the stretch, by index, and fixed gives the type
    of each bracket whose pair reaches outside it.
    """
    direction = "R" if base_level % 2 else "L"
    types = list(classes)
    previous = last_strong = direction
    for index, value in enumerate(types):
        if value == "NSM":
            value = previous
        if value in _STRONG_DIRECTIONS:
            last_strong = value
        elif value == "EN" and last_strong == "AL":
            value = "AN"
        types[index] = previous = value
    types = ["R" if value == "AL" else value for value in types]
    for index in range(1, len(types) - 1):
        value = types[index]
        if value == "ES" and types[index - 1] == "EN" == types[index + 1]:
            types[index] = "EN"
        elif value == "CS" and types[index - 1] == types[index + 1] in ("EN", "AN"):
            types[index] = types[index - 1]
    index = 0
    while index < len(types):
        end = index
        while end < len(types) and types[end] == "ET":
            end += 1
        if end > index and (
            (index and types[index - 1] == "EN")
            or (end < len(types) and types[end] == "EN")
        ):
            types[index:end] = ["EN"] * (end - index)
        index = max(end, index + 1)
    types = ["ON" if value in ("ES", "ET", "CS") else value for value in types]
    last_strong = direction
    for index, value in enumerate(types):
        if value in ("L", "R"):
            last_strong = value
        elif value == "EN" and last_strong == "L":
            types[index] = "L"
    _resolve_brackets(classes, types, direction, pairs, fixed or {})
    index = 0
    while index < len(types):
        if types[index] not in _NEUTRAL_TYPES:
            index += 1
            continue
        end = index
        while end < len(types) and types[end] in _NEUTRAL_TYPES:
            end += 1
        before = direction if index == 0 else ("L" if types[index - 1] == "L" else "R")
        after = direction if end == len(types) else ("L" if types[end] == "L" else "R")
        types[index:end] = [before if before == after else direction] * (end - index)
        index = end
    levels = []
    for value in types:
        if base_level % 2:
            levels.append(base_level + (value in ("L", "EN", "AN")))
        else:
            levels.append(base_level + (2 if value in ("EN", "AN") else value == "R"))
    reset = line_end
    for index in range(len(classes) - 1, -1, -1):
        if classes[index] == "S":
            levels[index] = base_level
            reset = True
        elif classes[index] == "WS" and reset:
            levels[index] = base_level
        else:
            reset = False
    return levels


def _resolve_brackets(classes, types, direction, pairs, fixed):
    """Bidi rule N0 for the bracket pairs of a stretch, in place."""

    def strong(value):
        return "L" if value == "L" else "R" if value in ("R", "EN", "AN") else None

    def set_type(index, value):
        types[index] = value
        index += 1
        while index < len(types) and classes[index] == "NSM":
            types[index] = value
            index += 1

    for index, value in fixed.items():
        set_type(index, value)
    if not pairs:
        return
    opposite = "R" if direction == "L" else "L"
    # Pairs nest and resolve in order of their opening brackets, so no pair
    # changes a character inside a pair still to come, and counts taken now
    # say which strong types each pair holds.
    kinds = [strong(value) for value in types]
    counts = {
        side: list(accumulate((kind == side for kind in kinds), initial=0))
        for side in ("L", "R")
    }
    for opening, closing in sorted(pairs):
        if counts[direction][closing] > counts[direction][opening + 1]:
            resolved = direction
        elif counts[opposite][closing] > counts[opposite][opening + 1]:
            context = direction
            for index in range(opening - 1, -1, -1):
                kind = strong(types[index])
                if kind:
                    context = kind
                    break
            resolved = opposite if context == opposite else direction
        else:
            continue
        set_type(opening, resolved)
        set_type(closing, resolved)


def _bracket_structure(text: str, start: int, end: int) -> tuple[array, array]:
    """The paired brackets of text[start:end] (definition BD16).

    Returns every bracket's offset, in order, and the index of its partner
    in that list, or -1 for a bracket left unpaired.
    """
    positions = array("i")
    partners = array("i")
    stack: list[tuple[str, int]] = []
    open_count: dict[str, int] = {}
    pairing = True
    for match in _BRACKET_PATTERN.finditer(text, start, end):
        character, index = match.group(), len(positions)
        positions.append(match.start())
        partners.append(-1)
        if not pairing:
            continue
        if character in _OPENING_BRACKETS:
            if len(stack) == _BRACKET_DEPTH:
                pairing = False
                continue
            canonical = _CANONICAL_BRACKETS.get(character, character)
            stack.append((canonical, index))
            open_count[canonical] = open_count.get(canonical, 0) + 1
            continue
        opening = _CLOSING_BRACKETS[character]
        opening = _CANONICAL_BRACKETS.get(opening, opening)
        if not open_count.get(opening):
            continue
        for depth in range(len(stack) - 1, -1, -1):
            if stack[depth][0] == opening:
                partners[index] = stack[depth][1]
                partners[stack[depth][1]] = index
                for canonical, _ in stack[depth:]:
                    open_count[canonical] -= 1
                del stack[depth:]
                break
    return positions, partners


def _visual_order(levels: list[int]) -> list[int]:
    """Indices in display order (bidi rule L2)."""
    order = list(range(len(levels)))
    for level in range(max(levels, default=0), 0, -1):
        index = 0
        while index < len(order):
            if levels[order[index]] < level:
                index += 1
                continue
            end = index
            while end < len(order) and levels[order[end]] >= level:
                end += 1
            order[index:end] = order[index:end][::-1]
            index = end
    return order


class _ParagraphMarks:
    """Judges the directional marks of one paragraph against the bidi algorithm.

    A mark is removed only when the paragraph displays the same without it,
    given the letters and the marks still in place: the same paragraph
    direction, the same order of the characters around it, the same
    mirroring, and the same attachment of combining marks. Only the first
    mark of a run is a candidate, and so is no mark directly before a
    combining mark, which belongs to the letter before it.
    """

    def __init__(self, text, start, end, context, budget, cache):
        self.text = text
        self.start = start
        self.end = end
        self.context = context
        self.budget = budget
        self.cache = cache
        self.candidates = array("i", self._find_candidates())
        count = len(self.candidates)
        self.alive = bytearray(b"\x01") * count
        self.previous = array("i", range(-1, count - 1))
        self.following = array("i", range(1, count + 1))
        self.head = 0
        # The span each mark's last judgment read, to know what to judge again.
        self.read_low = array("i", self.candidates)
        self.read_high = array("i", self.candidates)
        self.widest = 0
        # Marks kept for setting the paragraph direction read every mark
        # before the first letter; they are tracked apart so that span does
        # not widen the search for every other mark's readers.
        self.direction_setters: set[int] = set()
        self.first_letter = next(
            (
                offset
                for offset in range(start, end)
                if text[offset] not in _DIRECTIONAL_MARKS
                and self._cleaned_class(offset) in _STRONG_DIRECTIONS
            ),
            end,
        )
        self.brackets: array | None = None
        self.holds: dict[tuple[int, str], bool] = {}

    def _cleaned_class(self, offset: int) -> str:
        """The bidi class of a character in the cleaned copy; BN once removed."""
        character = self.text[offset]
        # ASCII, and letters and numbers other than the invisible fillers,
        # are never acted on, so they skip the full classification.
        if character < _FIRST_ACTED_ON or (
            unicodedata.category(character)[0] in "LN"
            and ord(character) not in _INVISIBLE_LETTERS_AND_MARKS
        ):
            return _bidi_class(character)
        classification = _classify(self.text, offset, self.context)
        if classification is not None and classification[0] == "remove":
            return "BN"
        if classification is not None and classification[0] == "normalize":
            return "WS"
        return _bidi_class(self.text[offset])

    def _find_candidates(self) -> Iterator[int]:
        text, start, end = self.text, self.start, self.end
        for match in _MARK_PATTERN.finditer(text, start, end):
            offset = match.start()
            before = offset - 1
            while (
                before >= start
                and text[before] not in _DIRECTIONAL_MARKS
                and self._cleaned_class(before) == "BN"
            ):
                before -= 1
            if before >= start and text[before] in _DIRECTIONAL_MARKS:
                continue
            after = offset + 1
            while after < end and (
                text[after] in _DIRECTIONAL_MARKS or self._cleaned_class(after) == "BN"
            ):
                after += 1
            if after < end and self._cleaned_class(after) == "NSM":
                continue
            yield offset

    def _present(self, offset: int) -> bool:
        index = bisect_left(self.candidates, offset)
        return (
            index < len(self.candidates)
            and self.candidates[index] == offset
            and bool(self.alive[index])
        )

    def _side(self, mark: int, step: int) -> tuple[list[tuple[int, str]], bool | None]:
        """Characters beside a mark, nearest first, through the nearest letter.

        Returns them with True when a letter ends them, False at the paragraph
        edge, or None when the letter is more than _MARK_WINDOW characters away.
        """
        text = self.text
        limit = self.start - 1 if step < 0 else self.end
        elements: list[tuple[int, str]] = []
        shown = 0
        offset = mark + step
        while offset != limit:
            self.budget[0] -= 1
            if text[offset] in _DIRECTIONAL_MARKS:
                if self._present(offset):
                    elements.append((offset, unicodedata.bidirectional(text[offset])))
            else:
                bidi_class = self._cleaned_class(offset)
                if bidi_class != "BN":
                    shown += 1
                    if shown > _MARK_WINDOW:
                        return elements, None
                    elements.append((offset, bidi_class))
                    if bidi_class in _STRONG_DIRECTIONS:
                        return elements, True
            offset += step
        return elements, False

    def _letter(self, offset: int, step: int) -> tuple[int, bool]:
        """The nearest letter past offset in one direction, or the paragraph edge."""
        limit = self.start - 1 if step < 0 else self.end
        offset += step
        while offset != limit:
            self.budget[0] -= 1
            if (
                self.text[offset] not in _DIRECTIONAL_MARKS
                and self._cleaned_class(offset) in _STRONG_DIRECTIONS
            ):
                return offset, True
            offset += step
        return (self.start if step < 0 else self.end - 1), False

    def _has_pairs(self) -> bool:
        """Whether the paragraph has bracket pairs, finding them on first use."""
        if self.brackets is None:
            self.brackets, self.partners = array("i"), array("i")
            if _BRACKET_PATTERN.search(self.text, self.start, self.end):
                self.brackets, self.partners = _bracket_structure(
                    self.text, self.start, self.end
                )
            # The innermost pair still open after each bracket, by the index
            # of its opening bracket; pairs nest, so this also gives parents.
            self.enclosing = array("i", [-1]) * len(self.brackets)
            stack: list[int] = []
            for index, partner in enumerate(self.partners):
                if partner > index:
                    stack.append(index)
                elif 0 <= partner < index:
                    stack.pop()
                self.enclosing[index] = stack[-1] if stack else -1
            self.paired = any(partner >= 0 for partner in self.partners)
        return self.paired

    def _bracket_index(self, offset: int) -> int:
        return bisect_left(self.brackets, offset)

    def _holds(self, opening: int, direction: str) -> bool:
        """Whether a pair holds a character, other than a mark, of a direction.

        The pair is named by the index of its opening bracket.
        """
        key = (opening, direction)
        if key not in self.holds:
            wanted = ("L",) if direction == "L" else ("R", "AL", "AN")
            self.holds[key] = False
            closing = self.brackets[self.partners[opening]]
            for inside in range(self.brackets[opening] + 1, closing):
                self.budget[0] -= 1
                if self.budget[0] <= 0:
                    break
                if (
                    self.text[inside] not in _DIRECTIONAL_MARKS
                    and self._cleaned_class(inside) in wanted
                ):
                    self.holds[key] = True
                    break
        return self.holds[key]

    def _unheld_pairs(self, indices, low, high, direction):
        """Pairs, by opening index, with a bracket among indices and the other
        outside low..high, that hold no character of the paragraph direction."""
        found = []
        for index in indices:
            self.budget[0] -= 1
            partner = self.partners[index]
            if partner >= 0 and not low <= self.brackets[partner] <= high:
                opening = min(index, partner)
                if not self._holds(opening, direction):
                    found.append(opening)
        return found

    def _widen(self, low, high, at_end, mark_direction):
        """A window grown over every bracket pair rule N0 needs it to hold whole.

        A pair holding a letter of the paragraph direction resolves to that
        direction whatever the marks, so it never needs widening. Any other
        pair with a bracket in the window does, and so does a pair around the
        whole window with no other character of the mark's direction, which
        the mark alone could decide. Returns the window's bounds, whether it
        reaches the end of the paragraph, and whether it fits the limits.
        """
        direction = self._paragraph_direction(None)
        brackets, partners = self.brackets, self.partners
        first = last = self._bracket_index(low)
        # Pairs around a grown window were around the first one, and whether
        # a pair needs widening does not depend on the window, so the pairs
        # around the window are checked once.
        pending = []
        opening = self.enclosing[first - 1] if first > 0 else -1
        while opening >= 0:
            self.budget[0] -= 1
            if (
                brackets[opening] < low
                and brackets[partners[opening]] > high
                and not self._holds(opening, direction)
                and not self._holds(opening, mark_direction)
            ):
                pending.append(opening)
            opening = self.enclosing[opening - 1] if opening > 0 else -1
        while True:
            # Only brackets the window gained since the last check can belong
            # to a pair it does not hold whole yet.
            grown_first = self._bracket_index(low)
            grown_last = bisect_right(brackets, high)
            pending.extend(
                self._unheld_pairs(
                    chain(range(grown_first, first), range(last, grown_last)),
                    low,
                    high,
                    direction,
                )
            )
            first, last = grown_first, grown_last
            if self.budget[0] <= 0:
                return low, high, at_end, False
            if not pending:
                return low, high, at_end, True
            for opening in pending:
                if brackets[opening] < low:
                    low, _ = self._letter(brackets[opening], -1)
                closing = brackets[partners[opening]]
                if closing > high:
                    high, found = self._letter(closing, 1)
                    at_end = not found
            pending = []
            if high - low > _MARK_SPAN:
                return low, high, at_end, False

    def _paragraph_direction(self, without: int | None) -> str:
        """The paragraph direction (rule P2), optionally without one mark."""
        head = self.head
        if head < len(self.candidates) and self.candidates[head] == without:
            head = self.following[head]
        first = self.first_letter
        if head < len(self.candidates) and self.candidates[head] < first:
            first = self.candidates[head]
        if first >= self.end:
            return "L"
        if self.text[first] in _DIRECTIONAL_MARKS:
            return _direction(unicodedata.bidirectional(self.text[first]))
        return _direction(self._cleaned_class(first))

    def _display(self, window, levels):
        """What a reader sees of a window: the order of its characters, whether
        each combining mark stays at its base's level, and which characters are
        mirrored."""
        text = self.text
        shown = [
            offset
            for offset, value in (window[index] for index in _visual_order(levels))
            if value != "NSM" and text[offset] not in _DIRECTIONAL_MARKS
        ]
        attached = []
        mirrored = []
        base_level = None
        for (offset, value), level in zip(window, levels):
            if value == "NSM":
                attached.append(level == base_level)
            elif text[offset] not in _DIRECTIONAL_MARKS:
                base_level = level
                if unicodedata.mirrored(text[offset]):
                    mirrored.append(level % 2)
        return shown, attached, mirrored

    def _judge(self, item: int) -> tuple[str | None, int, int]:
        """A reason to keep a mark, or None, and the span its judgment read.

        The mark is judged on the text between the nearest letters around it,
        widened over any bracket pair whose resolution that text could change,
        and removed when the window cannot be judged within the limits.
        """
        mark = self.candidates[item]
        direction = self._paragraph_direction(None)
        if direction != self._paragraph_direction(mark):
            return _SETS_DIRECTION, mark, mark
        left, left_letter = self._side(mark, -1)
        right, right_letter = (
            self._side(mark, 1) if left_letter is not None else ([], None)
        )
        low = left[-1][0] if left else mark
        high = right[-1][0] if right else mark
        if left_letter is None or right_letter is None or self.budget[0] <= 0:
            return None, low, high
        low = left[-1][0] if left else self.start
        high = right[-1][0] if right else self.end - 1
        at_end = not right_letter
        left.reverse()
        mark_element = (mark, unicodedata.bidirectional(self.text[mark]))
        window = [*left, mark_element, *right]
        if self._has_pairs():
            initial = low, high
            low, high, at_end, fits = self._widen(
                low, high, at_end, _direction(mark_element[1])
            )
            if not fits:
                return None, low, high
            if (low, high) != initial:
                window = self._elements(mark, low, high)
                if self.budget[0] <= 0:
                    return None, low, high
        position = next(
            index for index, (offset, _) in enumerate(window) if offset == mark
        )
        pairs, fixed = [], {}
        if self.paired:
            index_of = {offset: index for index, (offset, _) in enumerate(window)}
            for index, (offset, _) in enumerate(window):
                if self.text[offset] not in _PAIRED_BRACKETS:
                    continue
                partner_index = self.partners[self._bracket_index(offset)]
                if partner_index < 0:
                    continue
                partner = self.brackets[partner_index]
                if partner in index_of:
                    if offset < partner:
                        pairs.append((index, index_of[partner]))
                else:
                    # Only a pair fixed to the paragraph direction reaches out.
                    fixed[index] = direction
        # The judgment depends only on these facts, so equal shapes share it.
        # Bracket indices are packed, so a key holds a few bytes per bracket.
        shape = (
            "".join(self._shape_code(element) for element in window),
            position,
            direction,
            at_end,
            array("i", [index for pair in pairs for index in pair]).tobytes(),
            array("i", fixed).tobytes(),
        )
        if shape not in self.cache:
            if len(self.cache) >= _MARK_CACHE_SIZE:
                self.cache.clear()
            self.cache[shape] = self._changes_display(
                window, position, direction, at_end, pairs, fixed
            )
        return (_CHANGES_DISPLAY if self.cache[shape] else None), low, high

    def _elements(self, mark: int, low: int, high: int) -> list[tuple[int, str]]:
        """The characters of a window that the cleaned copy keeps, with classes."""
        window = []
        for offset in range(low, high + 1):
            self.budget[0] -= 1
            if self.text[offset] in _DIRECTIONAL_MARKS:
                if offset == mark or self._present(offset):
                    value = unicodedata.bidirectional(self.text[offset])
                    window.append((offset, value))
            else:
                value = self._cleaned_class(offset)
                if value != "BN":
                    window.append((offset, value))
        return window

    def _shape_code(self, element: tuple[int, str]) -> str:
        offset, value = element
        character = self.text[offset]
        code = value + ("^" if character in _DIRECTIONAL_MARKS else "")
        return code + ("~" if unicodedata.mirrored(character) else "") + ","

    def _changes_display(self, window, position, direction, line_end, pairs, fixed):
        """Whether the window displays differently without the mark at position."""
        base_level = 0 if direction == "L" else 1
        without = window[:position] + window[position + 1 :]

        def shifted(index):
            return index - (index > position)

        displays = [
            self._display(
                window,
                _resolve_levels(
                    [value for _, value in window], base_level, line_end, pairs, fixed
                ),
            ),
            self._display(
                without,
                _resolve_levels(
                    [value for _, value in without],
                    base_level,
                    line_end,
                    [(shifted(first), shifted(last)) for first, last in pairs],
                    {shifted(index): value for index, value in fixed.items()},
                ),
            ),
        ]
        return displays[0] != displays[1]

    def _remove(self, item: int) -> None:
        self.alive[item] = 0
        previous, following = self.previous[item], self.following[item]
        if previous >= 0:
            self.following[previous] = following
        else:
            self.head = following
        if following < len(self.candidates):
            self.previous[following] = previous

    def _readers(self, item: int) -> list[int]:
        """The marks still in place whose last judgment read this mark."""
        mark = self.candidates[item]
        readers = []
        if mark < self.first_letter:
            readers.extend(
                setter
                for setter in self.direction_setters
                if setter != item and self.alive[setter]
            )
        first = bisect_left(self.candidates, mark - self.widest)
        last = bisect_right(self.candidates, mark + self.widest)
        for other in range(first, last):
            self.budget[0] -= 1
            if (
                other != item
                and self.alive[other]
                and self.read_low[other] <= mark <= self.read_high[other]
            ):
                readers.append(other)
        return readers

    def judge(self) -> dict[int, str]:
        """Offsets of the marks to keep, with reasons."""
        count = len(self.candidates)
        reasons: list[str | None] = [None] * count
        dirty = bytearray(b"\x01") * count
        for pass_number in range(_MARK_PASSES):
            removed = False
            order = range(count) if pass_number % 2 == 0 else range(count - 1, -1, -1)
            for item in order:
                if not (self.alive[item] and dirty[item]):
                    continue
                if self.budget[0] <= 0:
                    break
                dirty[item] = 0
                reason, low, high = self._judge(item)
                self.read_low[item], self.read_high[item] = low, high
                self.widest = max(self.widest, high - low)
                if reason == _SETS_DIRECTION:
                    self.direction_setters.add(item)
                else:
                    self.direction_setters.discard(item)
                if reason is not None:
                    reasons[item] = reason
                    continue
                self._remove(item)
                removed = True
                # Every mark whose last judgment read this one is judged again.
                for other in self._readers(item):
                    dirty[other] = 1
            if not removed or self.budget[0] <= 0:
                break
        if self.budget[0] <= 0 or any(
            self.alive[item] and dirty[item] for item in range(count)
        ):
            # The budget ran out, or the pass limit did before every mark had
            # a verdict for its present surroundings. Removing only the marks
            # without one could change the paragraph direction or another
            # mark's verdict, so the paragraph keeps none of its marks.
            return {}
        return {
            self.candidates[item]: reason
            for item, reason in enumerate(reasons)
            if self.alive[item] and reason is not None
        }


def _kept_mark_reasons(text: str, context: _Context) -> dict[int, str]:
    """Offsets of the directional marks to keep, with the reason for each.

    Every mark is removed in a paragraph without right-to-left letters, and in
    one that held embeddings, overrides, or isolates, since those are removed
    and a mark that worked inside one could reorder the paragraph without it.
    """
    kept: dict[int, str] = {}
    if not _MARK_PATTERN.search(text):
        return kept
    budget = [_MARK_BUDGET]
    cache: dict = {}
    for start, end in _paragraphs(text):
        if not _MARK_PATTERN.search(text, start, end):
            continue
        if _EXPLICIT_PATTERN.search(text, start, end):
            continue
        if not any(
            match.group() not in _DIRECTIONAL_MARKS
            and _bidi_class(match.group()) in ("R", "AL")
            for match in _BEYOND_LATIN.finditer(text, start, end)
        ):
            continue
        kept.update(_ParagraphMarks(text, start, end, context, budget, cache).judge())
        if budget[0] <= 0:
            # Every later paragraph would keep none of its marks.
            break
    return kept


def _is_known_emoji_zwj_pair(previous_base: str, next_base: str) -> bool:
    return (ord(previous_base), ord(next_base)) in _EMOJI_ZWJ_PAIRS


def _is_explicit_removal(code_point: int) -> bool:
    return (
        code_point in _REMOVABLE_FORMAT_CODE_POINTS
        or 0xE0000 <= code_point <= 0xE007F
        or code_point in _UNASSIGNED_DEFAULT_IGNORABLE_CODE_POINTS
    )


def _is_emoji_modifier(character: str) -> bool:
    return 0x1F3FB <= ord(character) <= 0x1F3FF


def _is_base_character(character: str) -> bool:
    code_point = ord(character)
    category_group = unicodedata.category(character)[0]
    return not _is_emoji_modifier(character) and (
        code_point in _EMOJI_ZWJ_BASES or category_group in {"L", "N", "S"}
    )


def _is_context_extender(character: str) -> bool:
    return (
        unicodedata.category(character)[0] == "M"
        or _is_variation_selector(character)
        or _is_emoji_modifier(character)
    )


def _neighboring_bases(text: str) -> tuple[list[str | None], list[str | None]]:
    previous: list[str | None] = [None] * len(text)
    following: list[str | None] = [None] * len(text)
    last_base = None
    for index, character in enumerate(text):
        previous[index] = last_base
        if _is_base_character(character):
            last_base = character
        elif not _is_context_extender(character):
            last_base = None

    next_base = None
    for index in range(len(text) - 1, -1, -1):
        following[index] = next_base
        character = text[index]
        if _is_base_character(character):
            next_base = character
        elif not _is_context_extender(character):
            next_base = None
    return previous, following


class _Context(NamedTuple):
    """Facts about the whole text, computed once before classification."""

    previous_bases: list[str | None]
    next_bases: list[str | None]
    cjk_spaces: frozenset[int]
    # Filled in once the marks are judged, which needs the other characters.
    kept_marks: dict[int, str]


def _classify(
    text: str,
    offset: int,
    context: _Context,
) -> tuple[str, str | None] | None:
    character = text[offset]
    code_point = ord(character)
    previous_base = context.previous_bases[offset]
    next_base = context.next_bases[offset]

    # Nothing in ASCII is ever acted on: the first candidate is U+00A0.
    if code_point < 0x80:
        return None

    category = unicodedata.category(character)
    # Letters and numbers are never acted on, except the invisible fillers.
    if category[0] in "LN" and code_point not in _INVISIBLE_LETTERS_AND_MARKS:
        return None

    if category == "Zs":
        reason = None
        if character in _NO_BREAK_SPACES:
            reason = _no_break_reason(text, offset)
        elif offset in context.cjk_spaces:
            reason = "ideographic space beside CJK text"
        return ("normalize", None) if reason is None else ("preserve", reason)

    if character in _JOINERS:
        if (
            character == "\u200d"
            and previous_base is not None
            and next_base is not None
            and _is_known_emoji_zwj_pair(previous_base, next_base)
        ):
            return "preserve", "matches a pinned Emoji 17 pair"
        previous_family = (
            _script_family(previous_base) if previous_base is not None else None
        )
        next_family = _script_family(next_base) if next_base is not None else None
        if previous_family is not None and previous_family == next_family:
            return "preserve", "required by surrounding complex-script orthography"
        return "remove", None

    if _is_variation_selector(character):
        if code_point in _MONGOLIAN_VARIATION_SELECTORS or code_point == 0x180F:
            if offset > 0 and _script_family(text[offset - 1]) == "mongolian":
                return "preserve", "Mongolian selector after Mongolian base"
            return "remove", None
        if code_point in {0xFE0E, 0xFE0F} and _is_emoji_variation_sequence(
            text, offset
        ):
            presentation = "text" if code_point == 0xFE0E else "emoji"
            return (
                "preserve",
                f"{presentation}-presentation selector in a pinned Emoji 17 "
                "variation sequence",
            )
        return "remove", None

    if code_point == _MONGOLIAN_VOWEL_SEPARATOR:
        if (
            previous_base is not None
            and next_base is not None
            and _script_family(previous_base) == "mongolian"
            and _script_family(next_base) == "mongolian"
        ):
            return "preserve", "Mongolian vowel separator between Mongolian letters"
        return "remove", None

    if character in _DIRECTIONAL_MARKS:
        reason = context.kept_marks.get(offset)
        return ("remove", None) if reason is None else ("preserve", reason)

    if _is_explicit_removal(code_point):
        return "remove", None

    if category == "Cf":
        return "preserve", "unclassified format control preserved conservatively"

    if code_point in _INVISIBLE_LETTERS_AND_MARKS:
        return (
            "preserve",
            "invisible default-ignorable character preserved conservatively",
        )

    return None


def _code_point_label(character: str) -> str:
    return f"U+{ord(character):04X}"


def _process(text: str) -> tuple[str, dict[str, object]]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    previous_bases, next_bases = _neighboring_bases(text)
    context = _Context(previous_bases, next_bases, _cjk_space_offsets(text), {})
    context = context._replace(kept_marks=_kept_mark_reasons(text, context))
    tag_sequence_offsets = _tag_sequence_offsets(text)
    findings: dict[tuple[str, str, str | None], dict[str, object]] = {}
    cleaned_characters: list[str] = []
    summary = {
        "detected": 0,
        "removed": 0,
        "normalized": 0,
        "preserved": 0,
        "actionable": 0,
    }

    for offset, character in enumerate(text):
        if offset in tag_sequence_offsets:
            classification = ("preserve", "part of a pinned Emoji 17 tag sequence")
        else:
            classification = _classify(text, offset, context)
        if classification is None:
            cleaned_characters.append(character)
            continue

        action, reason = classification
        key = (character, action, reason)
        item = findings.get(key)
        if item is None:
            item = {
                "code_point": _code_point_label(character),
                "name": unicodedata.name(character, "UNNAMED CHARACTER"),
                "action": action,
                "count": 0,
                "offsets": [],
            }
            if reason is not None:
                item["reason"] = reason
            findings[key] = item

        item["count"] += 1
        if len(item["offsets"]) < 10:
            item["offsets"].append(offset)

        summary["detected"] += 1
        if action == "remove":
            summary["removed"] += 1
            summary["actionable"] += 1
        elif action == "normalize":
            summary["normalized"] += 1
            summary["actionable"] += 1
            cleaned_characters.append(" ")
        else:
            summary["preserved"] += 1
            cleaned_characters.append(character)

    manifest: dict[str, object] = {
        "policy_version": POLICY_VERSION,
        "unicode_version": unicodedata.unidata_version,
        "emoji_zwj_version": EMOJI_ZWJ_VERSION,
        "findings": list(findings.values()),
        "summary": summary,
    }
    return "".join(cleaned_characters), manifest


def inspect_text(text: str) -> dict[str, object]:
    """Return a deterministic manifest without changing the supplied text."""
    return _process(text)[1]


def clean_text(text: str) -> tuple[str, dict[str, object]]:
    """Return a cleaned working copy and its deterministic manifest."""
    return _process(text)


class InputTooLargeError(ValueError):
    """Raised when input exceeds the documented byte cap."""


class UnsafeInputPathError(ValueError):
    """Raised when path input is not a stable regular file."""


def _read_limited_bytes(stream) -> bytes:
    data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise InputTooLargeError
    return data


def _open_regular_file(path: str):
    before_open = os.lstat(path)
    if not stat.S_ISREG(before_open.st_mode):
        raise UnsafeInputPathError

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        after_open = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after_open.st_mode)
            or before_open.st_dev != after_open.st_dev
            or before_open.st_ino != after_open.st_ino
        ):
            raise UnsafeInputPathError
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _read_input(path: str) -> str:
    if path == "-":
        data = _read_limited_bytes(sys.stdin.buffer)
    else:
        with _open_regular_file(path) as source:
            data = _read_limited_bytes(source)
    return data.decode("utf-8")


def _write_json(stream, value: dict[str, object]) -> None:
    json.dump(value, stream, ensure_ascii=True, separators=(",", ":"))
    stream.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or clean deterministic Unicode text artifacts."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("path", nargs="?", default="-")

    clean_parser = subparsers.add_parser("clean")
    clean_parser.add_argument("--stats", action="store_true")
    clean_parser.add_argument("path", nargs="?", default="-")
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    try:
        text = _read_input(args.path)
        cleaned, manifest = clean_text(text)
    except InputTooLargeError:
        sys.stderr.write(
            f"text_hygiene: input exceeds {MAX_INPUT_BYTES}-byte limit\n"
        )
        return 2
    except UnsafeInputPathError:
        sys.stderr.write(
            "text_hygiene: path input must be a regular file and not a symbolic link\n"
        )
        return 2
    except UnicodeDecodeError:
        sys.stderr.write("text_hygiene: invalid UTF-8 input\n")
        return 2
    except OSError as error:
        sys.stderr.write(f"text_hygiene: could not read input: {error}\n")
        return 2
    except Exception as error:
        sys.stderr.write(f"text_hygiene: processing failed: {error}\n")
        return 2

    try:
        if args.operation == "inspect":
            _write_json(sys.stdout, manifest)
            return 1 if manifest["summary"]["actionable"] else 0

        sys.stdout.buffer.write(cleaned.encode("utf-8"))
        sys.stdout.buffer.flush()
        if args.stats:
            _write_json(sys.stderr, manifest)
        return 0
    except (BrokenPipeError, OSError) as error:
        sys.stderr.write(f"text_hygiene: could not write output: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
