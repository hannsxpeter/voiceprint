# Deterministic text hygiene

This is the deep reference for `scripts/text_hygiene.py`. The product README
keeps the short version; maintainers and release checks live in
[CONTRIBUTING.md](../CONTRIBUTING.md).

The helper requires Python 3.11 or newer. CI runs it on Python 3.11, the
documented minimum, and 3.14.

The original remains byte-for-byte unchanged in `Before` and is the input to
the before diagnosis. At the start of Step 2, `scripts/text_hygiene.py` creates
a cleaned working copy. It replaces Unicode space variants with an ordinary
space, except the typographic spaces described below, and removes soft
hyphens, U+200B, invalid or free-floating joiners, directional embeddings,
overrides, and isolates, directional marks that do not affect the display,
tag characters outside the pinned emoji tag sequences, BOM, interlinear
annotation controls, invisible operators, the Mongolian vowel separator
outside Mongolian words, unsupported variation selectors, and unassigned
default-ignorable code points. Other format controls, and the
default-ignorable letters and marks that render invisibly but have
orthographic uses (U+034F, U+115F, U+1160, U+17B4, U+17B5, U+3164, U+FFA0),
are preserved conservatively and reported with a reason, so every
default-ignorable code point in the Unicode 17.0 data is at least reported.
Tabs, line breaks, fullwidth letters, and confusable visible letters remain
unchanged.

Script joiners are preserved only between letters in the same supported
script family, and the Mongolian vowel separator only between Mongolian
letters. Mongolian variation selectors are preserved only directly after a
Mongolian letter. Emoji preservation uses three tables pinned from the
official Unicode Emoji 17.0 data:

- **ZWJ pairs.** U+200D is preserved only when its neighboring bases match
  one of 245 pairs taken from the ZWJ sequence data.
- **Presentation selectors.** U+FE0E and U+FE0F are preserved only directly
  after one of the 371 bases in the variation-sequence data, and after `#`,
  `*`, or a digit only inside a keycap sequence (when U+20E3 follows).
- **Tag sequences.** Tag characters are preserved only inside the three RGI
  emoji tag sequences, the England, Scotland, and Wales flags.

Repeated selectors, selectors after any other base, supplementary variation
selectors, and other unsupported selector contexts are removed. That includes
standardized variation sequences outside emoji and Mongolian, such as CJK
ideographic variation sequences, which lose their selector.

No-break spaces are kept only where typography depends on them. A no-break
space (U+00A0) or narrow no-break space (U+202F) stays inside a number (a
thousands separator), between a number and a unit of one to three letters or
a symbol (5 km, 12 %), before French closing punctuation (`!`, `?`, `;`, `:`,
and the closing guillemets U+00BB and U+203A), and after the opening
guillemets (U+00AB and U+2039). A figure space (U+2007) stays only inside a
number, and an ideographic space (U+3000) only in a run that touches CJK
text. The neighbors that decide this are the nearest characters that take
space, so an invisible character beside the space never changes the answer.
Everywhere else these spaces become ordinary spaces: a no-break space looks
like any other space, so swapping one in at a word gap can carry a hidden
mark. Other typographic uses, such as a no-break space after a one-letter
word in Czech or Polish or inside an abbreviation, are normalized too, as are
thin, hair, em, and the other width-specific spaces. Where a no-break space is
kept, choosing it over an ordinary space is still invisible, so each kept one
could carry one hidden bit; the manifest counts every one, with its reason
and up to ten offsets.

A directional mark is removed unless removing it would change how its
paragraph displays. A left-to-right mark (U+200E), right-to-left mark
(U+200F), or Arabic letter mark (U+061C) can stay only in a paragraph that
contains right-to-left letters and no embeddings, overrides, or isolates.
There the helper applies the Unicode Bidirectional Algorithm (numbers,
neutral characters, bracket pairs, tabs, and the paragraph direction) to the
text between the nearest letters around the mark, once with the mark and
once without, and keeps the mark when the paragraph direction, the order of
those characters, their mirroring, or a combining mark's attachment would
differ. Bracket pairs are resolved exactly: the text judged widens over
every pair whose resolution the mark could change, such as an English phrase
in parentheses inside Hebrew text, together with the letter before it.
Characters the helper removes count as already gone, and unassigned code
points take their Unicode default direction (the pinned defaults match ICU's
Unicode 17.0 data for every unassigned code point). Each mark is judged
against the marks that remain, and judging repeats until a pass removes
nothing (at most 8 passes). Only the first mark of a run can stay, and a
mark is removed when it sits directly before a combining mark, more than 64
characters from the nearest letter, or where the text to judge would span
more than 4,096 characters. To bound adversarial input, judging has a budget
of 4,000,000 steps per text: one for each character, bracket, or mark it
reads, and three more for each character it resolves. When that runs out,
the paragraph being judged and every later one keep none of their marks, and
so does a paragraph whose marks still lack verdicts for their present
surroundings after 8 passes. In testing on an Apple M4 Max, 4 MiB of short
mixed Arabic, Hebrew, and English paragraphs with 227,000 marks used three
quarters of the budget. Adversarial inputs took at most about eight seconds
longer than under policy 2, the slowest being 4 MiB of paragraphs a few
characters long that each hold marks (about four and a half times as long),
and used at most about 110 MB more memory, the most for inputs that keep
hundreds of thousands of marks. Embeddings, overrides, and isolates (U+202A
to U+202E and U+2066 to U+2069) are always removed: they can reorder whole
spans, which is how Trojan Source attacks make text display in a different
order from the one it is stored in. A kept mark still reorders text, since
that is its job, but only where the text around it shows the change. These
rules are policy version 3; version 2 normalized every space variant and
removed every directional mark.

The directional-mark rule is checked against ICU's implementation of the
bidirectional algorithm (with Unicode 17.0 data) on 40,000 random paragraphs
from two generators that mix Hebrew, Arabic, and Latin letters, both kinds
of digits with separators, nested brackets, tabs, combining marks, no-break
spaces, stray selectors, unassigned code points, and explicit controls.
Measured against the same text with the helper's other removals and
normalizations applied, every cleaned paragraph displayed like the original
apart from the removals listed above, except one in which ICU leaves an
angle-bracket pair unpaired around an inner U+2329 and U+232A pair that
holds no strong character (FriBidi and the helper pair them, as the standard
requires). Every one of 13,528 kept marks changed the display, and cleaning
the cleaned copy changed nothing, which holds whenever both cleanings finish
judging within the budget. GNU FriBidi agrees on the same paragraphs except
where it departs from the standard by not pairing a bracket that follows a
combining mark. There, and where ICU leaves a combining mark after a
resolved bracket unresolved, the helper follows the standard's text. In
realistic Hebrew, Arabic, and mixed prose, and in inputs built to pack marks
around parentheticals, no position lets an invisible mark survive without a
visible effect. With FriBidi installed, an opt-in test repeats a smaller
version of the check:

```sh
VOICEPRINT_FRIBIDI=1 python3 -m unittest -v tests.test_text_hygiene.BidiReferenceTests
```

Since policy version 2 (voiceprint 1.5.0), cleanup leaves every sequence in
the pinned data unchanged: 1,400 basic emoji, 12 keycap, 259 flag,
3 tag, 665 modifier, and 1,614 ZWJ sequences, plus all 742 emoji variation
sequences (keycap bases checked inside their keycap sequence). Policy version
1, shipped in 1.4.0, removed the selector from 132 of those variation
sequences, which broke 40 basic emoji, all 12 keycaps, and two ZWJ sequences,
and it stripped the tag characters from all three tag sequences. The same
check confirms that every default-ignorable code point is detected and every
unassigned one removed; policy 1 missed 3,776 of the 4,174. To reproduce the
check against the official files:

```sh
DATA=$(mktemp -d)
for f in emoji/emoji-sequences.txt emoji/emoji-zwj-sequences.txt ucd/emoji/emoji-variation-sequences.txt ucd/DerivedCoreProperties.txt; do
  curl -fsSL -o "$DATA/$(basename "$f")" "https://www.unicode.org/Public/17.0.0/$f"
done
VOICEPRINT_UNICODE_DATA_DIR="$DATA" python3 -m unittest -v tests.test_text_hygiene.UnicodeDataTests
```

The helper is dependency-free, offline, and never writes a source file in
place. It requires Python 3.11 or newer, accepts at most 4 MiB (4,194,304
bytes) from a regular, non-symbolic-link file or standard input, and exposes
an importable Python API and two CLI operations:

```sh
python3 scripts/text_hygiene.py inspect draft.txt
python3 scripts/text_hygiene.py clean --stats draft.txt > cleaned.txt 2> hygiene.json
```

`inspect` emits a JSON manifest and exits 1 when actionable characters exist,
0 when none are actionable, and 2 on a usage or processing error. Preserved
context can therefore appear in a successful exit-0 manifest. Manifests carry
the `policy_version` and name the Python Unicode database version and the
Unicode Emoji version of the pinned emoji data (`emoji_zwj_version`). `clean`
writes exact UTF-8 bytes to standard output and exits 0 on success. With
`--stats`, it writes the same manifest to standard error. Omitting the path
reads standard input, which is preferred for pasted text.

The 200 ms p95 release gate is opt-in so routine CI does not depend on noisy
wall-clock timing. Its input, 100,000 code points of letters and zero-width
spaces, holds no directional marks, so it times the cleanup every text gets.
Text dense with right-to-left letters and directional marks also pays for
the mark rule and took about 150 to 210 ms per 100,000 code points in
testing, two to three times as long as under policy 2. Run the gate on the
release reference runner and record its printed p95 with the release
evidence, as CONTRIBUTING.md describes:

```sh
VOICEPRINT_RELEASE_BENCHMARK=1 python3 -m unittest -v tests.test_text_hygiene.TextHygieneApiTests.test_p95_is_within_budget_for_one_hundred_thousand_code_points
```

This inspection establishes only which Unicode code points were acted on. It
cannot establish that a watermark, vendor provenance signal, or detector
signal exists, and it makes no promise about external detector results. It
does not use NFKC normalization, map lookalike letters, inspect file metadata,
or process images, audio, or video.

### How the vendored skills' own Unicode handling fits

Since their 1.2.0 releases, both vendored skills also look at Unicode in the
text layer, and voiceprint runs them as written:

- authenticity-check's read-only provenance preflight reports suspicious
  carriers in its own `Provenance signals` section. The before read shows
  what the original contained and the residual read shows what is left.
  Neither read changes the text or moves the authenticity score.
- humanizer's prompt-level hygiene preflight runs inside the single humanizer
  invocation, on the working copy the helper already cleaned. Its
  `Text hygiene:` header line is folded into `What changed` after the
  helper's manifest counts, which stay the authoritative hygiene record.

Neither adds a stage or a loop, and neither skill's standalone `Next step` is
emitted inside the pass. The helper is still stricter than humanizer's
prompt-level guidance in three places: it always removes directional
embeddings, overrides, and isolates, along with every directional mark in a
paragraph that held one; it removes a directional mark that does not change
the display even where the mark is expected; and it normalizes
width-specific spaces and any no-break space outside the contexts above.
Review the hygiene counts in `What changed` for such text.
