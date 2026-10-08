# voiceprint

![version](https://img.shields.io/badge/version-1.5.2-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![type](https://img.shields.io/badge/type-thin%20orchestrator-purple)
![pass](https://img.shields.io/badge/behavior-one%20pass%2C%20no%20loop-red)
![upstreams](https://img.shields.io/badge/vendors-humanizer%20%2B%20authenticity--check-orange)
![tools](https://img.shields.io/badge/works%20with-8%20AI%20coding%20tools-teal)

A single unified prose-authenticity tool with one entry point. You give it
text. It checks how authentically the text reads, rewrites the AI tells once,
and tells you what is left. It composes two existing prose skills in a fixed
order, exactly once, and applies one deterministic Unicode hygiene operation
inside the existing transformation stage.

## Where this comes from

voiceprint is the bundled product of two standalone, pure-prompt skills that
each do one job well:

- [humanizer](https://github.com/hannsxpeter/humanizer) rewrites AI-sounding prose
  so it reads as genuinely human, and in a specific writer's voice when a
  sample or profile is available.
- [authenticity-check](https://github.com/hannsxpeter/authenticity-check) is a
  read-only diagnostic that scores how authentically text reads as a real
  human author and flags the spans that read as AI-generated, AI-templated, or
  derivative. It never rewrites.

Both descend from the voice-preservation logic that powers
[Scriveno](https://github.com/hannsxpeter/scriveno) (formerly Scriven), an AI-native
longform writing system whose core promise is that drafted prose should sound
like the writer, not like AI. The two skills were deliberately kept separate
upstream, because a single tool that scores text and then rewrites it to raise
its own score is a detector-gaming loop. voiceprint composes them without
recreating that loop: it runs the diagnostic, the rewrite, and the diagnostic
again, once each, with a human deciding what to do about anything left over.

The text hygiene stage was inspired by the deterministic Unicode cleanup in
[watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover).
Voiceprint adopts only the compatible text-hygiene idea. It does not adopt
statistical watermark rewriting, metadata removal, image processing, vendor
attribution, or detector optimization.

## The one-pass rule

This is the behavior the product exists to guarantee, and it does not relax:

1. Run the authenticity-check logic once on the input. This is the **before**
   read.
2. Clean a working copy once, then apply humanizer's known fixes once. This
   produces the **after** text.
3. Run the authenticity-check logic again **only to report the residual**.

There is no iteration toward a score threshold. The re-check informs you; it
never drives further rewriting. The output is the before text, the after
text, the residual flagged spans, the authenticity read, and an explicit
statement that what remains requires human judgment. A silent
score-optimization loop is exactly what this design forbids. voiceprint is not
an AI-detector-beating tool, and it names and targets no detector.

## Why this one is different

- **One pass, never a loop.** The re-diagnosis is a report, not a feedback
  signal. There is no target score and no "try again until it passes."
- **Thin orchestration.** The prose methods remain in the vendored skills.
  The only local transformation is the narrow Unicode hygiene helper that
  prepares the working copy.
- **Inspectable text hygiene.** Hidden formatting controls and exotic Unicode
  spaces are reported and cleaned deterministically, while recognized script
  joiners and the emoji sequences in the pinned Unicode data are preserved
  with a reason.
- **Canonical upstreams, one-directional sync.** humanizer and
  authenticity-check stay independently usable and authoritative. voiceprint
  vendors copies and never edits them in place.
- **Faithfulness inherited.** humanizer's anti-fabrication guards and
  authenticity-check's restraint and caveats pass through unaltered, because
  voiceprint runs the vendored skills as written.

## What it does

Given text, voiceprint returns one structured result: the original, the
before authenticity read (including authenticity-check's Unicode provenance
signals), the humanized rewrite with humanizer's own "what changed /
deliberately left alone / meaning check" report, the residual read after the
single pass, and a closing statement that the remaining gap is a human's
call, not another automated rewrite. Text hygiene counts and preservation
reasons appear inside `What changed`, so the public result still has exactly
six top-level sections.

## Deterministic text hygiene

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
text between the nearest letters around the mark, once with the mark and once
without, and keeps the mark when the paragraph direction, the order of those
characters, their mirroring, or a combining mark's attachment would differ.
Bracket pairs are resolved exactly: the text judged widens over every pair
whose resolution the mark could change, such as an English phrase in
parentheses inside Hebrew text, together with the letter before it.
Characters the helper removes count as already gone, and unassigned code
points take their Unicode default direction (the pinned defaults match
ICU's Unicode 17.0 data for every unassigned code point). Each mark is judged
against the marks that remain, and judging repeats until a pass removes
nothing (at most 8 passes). Only the first mark of a run can stay, and a mark
is removed when it sits between a letter and its combining mark, more than
64 characters from the nearest letter, or where the text to judge would
span more than 4,096 characters. To bound adversarial input, judging has a
budget of 4,000,000 steps per text: one for each character, bracket, or mark
it reads, and three more for each character it resolves. When that runs out,
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

The directional-mark rule is checked against two independent
implementations of the bidirectional algorithm, ICU (with Unicode 17.0 data)
and GNU FriBidi, on 40,000 random paragraphs from two generators that mix
Hebrew, Arabic, and Latin letters, both kinds of digits with separators,
nested brackets, tabs, combining marks, no-break spaces, stray selectors,
unassigned code points, and explicit controls. Measured against the same
text with the helper's other removals and normalizations applied, every
cleaned paragraph displayed like the original apart from the removals listed
above, except one in which ICU leaves an angle-bracket pair unpaired around
an inner U+2329 and U+232A pair that holds no strong character (FriBidi and
the helper pair them, as the standard requires). Every one of 13,528 kept
marks changed the display, and cleaning the cleaned copy changed nothing,
which holds whenever both cleanings finish judging within the budget. Where
one library departs from the standard (FriBidi stops pairing a bracket that
follows a combining mark, and ICU leaves a combining mark after a resolved
bracket unresolved), the helper follows the standard's text. In realistic Hebrew, Arabic, and mixed prose,
and in inputs built to pack marks around parentheticals, no position lets an
invisible mark survive without a visible effect. With FriBidi installed, an
opt-in test repeats a smaller version of the check:

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
wall-clock timing. Run it on the release reference runner and retain its
printed p95 result with the release evidence:

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

## Supported tools

| Tool | File it reads | Install |
|---|---|---|
| Claude Code | `SKILL.md` | `cp -r` this repo to `~/.claude/skills/voiceprint/`, or use the repo in-project |
| Cursor | `.cursor/rules/voiceprint.mdc` | Open this repo in Cursor, or copy `.cursor/rules/voiceprint.mdc` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` into your project |
| Codex | `AGENTS.md` | Clone this repo into (or beside) your project; Codex reads `AGENTS.md` |
| Antigravity | `AGENTS.md` | Same as Codex: keep `AGENTS.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` in the workspace |
| Gemini CLI | `GEMINI.md` | Keep `GEMINI.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` in the project Gemini runs in |
| Pi | `AGENTS.md` | Point Pi at this repo / its `AGENTS.md` |
| OpenCode | `AGENTS.md` or `SKILL.md` | Copy the skill into OpenCode's skills directory, or keep `AGENTS.md` in the project |
| GitHub Copilot | `.github/copilot-instructions.md` | Copy `.github/copilot-instructions.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` into the target repository |

Every adapter points the agent at the same `SKILL.md`, deterministic hygiene
helper, and vendored skills under `vendor/`, so the one-pass behavior is
identical across tools.

Because the pass reads untrusted text, `SKILL.md` pre-approves only
read-only tools. In Claude Code that means a permission prompt before the
hygiene helper runs, and before a temporary input file is written when the
host offers no way to pass standard input. The prompt is deliberate: pasted
text never reaches a shell command or heredoc.

voiceprint ships and documents adapters for the eight tools above (Pi was
formerly listed as Pi Coder). The upstream skills also document Devin
Desktop (formerly Windsurf), Cline, Continue, Zed, and Aider. Several of
those read `AGENTS.md` or `.github/copilot-instructions.md`, which voiceprint
ships, but voiceprint makes no support claim for them. The vendored skills'
frontmatter is upstream's, synced verbatim: humanizer no longer declares
`compatibility`, and authenticity-check lists its hosts under
`metadata.compatibility`. Neither is a claim that voiceprint provides an
adapter for those tools.

## Usage

Ask, in plain language, for the combined intent: clean this up and verify it,
make this authentic and tell me how it scored, de-slop this and show me what
is still flagged, or just "voiceprint this." You do not need to say the word
"voiceprint."

If you only want one half, use the standalone skill directly:

- Only a rewrite, no score: use [humanizer](https://github.com/hannsxpeter/humanizer).
- Only a score, no rewrite: use
  [authenticity-check](https://github.com/hannsxpeter/authenticity-check).

For voice-matched output, the same options humanizer supports apply: paste a
sample, name a well-known author, or keep a `VOICE.md` / `STYLE-GUIDE.md` in
the project. The vendored skills discover it automatically.

## Composition and the sync obligation

voiceprint is a thin orchestrator over vendored copies of both skills and the
shared detection criteria. The vendored copies are **not** the source of
truth. The sync is strictly one-directional.

- **Canonical upstream for detection and rewrite criteria** (humanizer's
  `SKILL.md` and references, including the shared `tell-patterns.md`,
  `do-not-flag.md`, and `voice-matching.md`) is the
  [humanizer](https://github.com/hannsxpeter/humanizer) repo.
- **Canonical upstream for scoring logic** (authenticity-check's `SKILL.md`
  and its native references, such as `scoring.md` and `provenance-signals.md`)
  is the [authenticity-check](https://github.com/hannsxpeter/authenticity-check)
  repo.
- **voiceprint never edits vendored content.** A fix belongs upstream in the
  canonical repo and is then re-vendored here. Editing a copy in place makes
  the product drift from the skills it claims to run.
- **Every vendored file carries a header stamp** recording its true upstream
  repo, the source commit, and a "synced copy, do not edit here, edit
  upstream" notice. The header is the contract.

### Sync procedure

The vendored tree under `vendor/` is produced and stamped entirely by the sync
script. It is never hand-copied.

1. Land the criteria or logic change in the canonical upstream repo and commit
   it there (humanizer for detection/rewrite criteria, authenticity-check for
   scoring logic).
2. From this repo's root, run the sync tool:

   ```sh
   scripts/sync-upstream
   ```

   By default it reads the sibling repos `../humanizer` and
   `../authenticity-check`. Override with arguments or the `HUMANIZER_REPO` and
   `AUTHENTICITY_CHECK_REPO` environment variables:

   ```sh
   scripts/sync-upstream /path/to/humanizer /path/to/authenticity-check
   ```

3. The script refuses to run outside a voiceprint checkout, or if either
   upstream working tree has uncommitted tracked changes or cannot report its
   status. It vendors each skill's `SKILL.md` and every tracked
   `references/*.md` file (regular files directly under `references/` only),
   reading the bytes from the upstream HEAD commit. Each file gets the sync
   header, which names the true canonical upstream (the shared criteria always
   point at humanizer even inside the authenticity-check tree), the source
   commit, and the upstream blob id of the body. The new tree is built beside
   `vendor/` and swapped in only after every file succeeded; if the script is
   killed outright during the swap, `git checkout -- vendor` restores the
   committed tree. The script warns when the commit is not on a
   remote-tracking branch and prints a summary.
4. Verify and commit the updated `vendor/`:

   ```sh
   scripts/check
   git add vendor && git commit
   ```

`scripts/check-vendor-headers` runs inside `scripts/check` and therefore in CI
(`.github/workflows/vendor-sync-check.yml`). It fails the build if any file
under `vendor/` is missing a valid sync header, if a vendored body is not
exactly the blob its header names (which catches an edit made here instead of
upstream; rewriting the stamp too shows in review as a `Source blob` change
with no `Source commit` change), or if a vendored `SKILL.md` names a
reference file that was not vendored. Re-syncing is an obligation,
not an option: when the upstream criteria change, the vendored copies must be
re-pulled or the product silently disagrees with the skills it advertises.
`scripts/check-upstream-freshness` compares each vendored skill's stamped
commit with its upstream's default branch and reports a re-sync as due when a
newer upstream commit changed `SKILL.md` or a `references/` file, or when the
stamped commit is not on that branch; commits that touch only an upstream's
CI, README, or other tooling do not count. A
scheduled `upstream-freshness` workflow runs it weekly and fails when a
re-sync is due, and every push reports the same staleness as a warning, so
this obligation does not depend on remembering. GitHub pauses scheduled workflows after 60 days without
repository activity, which is how the vendored copies missed every upstream
release after 1.1.1 until 1.5.0. If the Actions tab shows
`upstream-freshness` as disabled, re-enable it there or with
`gh workflow enable upstream-freshness.yml`.

## Checks

`scripts/check` runs everything CI runs: the hygiene and repository test
suites (exact hygiene fixtures, shell syntax, eval JSON, version consistency
across `SKILL.md`, this README, and `CHANGELOG.md`, adapter routing, pinned
workflow actions and credentials, the read-only tool grant, the dash policy,
and the vendored-content check itself), then `scripts/check-vendor-headers`.
CI runs it on Python 3.11, the documented minimum, and 3.14. Maintainer
guidance (opt-in checks, syncing, releases, and project state) is in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Scope

voiceprint improves prose quality and authentic voice, then gives an honest
read of what is left. It is not designed or tuned to defeat plagiarism
checkers or AI-detection systems, and it names no detector. Requests framed as
passing AI work off as a person's own for a graded or contractual assessment
are reframed toward the quality-and-voice use the tool actually serves. This
is the same boundary the vendored skills hold; voiceprint inherits it.
Unicode hygiene is reported as a deterministic code-point operation, not as
watermark discovery, provenance attribution, or detector-signal removal.

## Layout

```
SKILL.md                          orchestrator: the one-pass rule, output contract, scope
AGENTS.md                         cross-tool entry point (Codex, Antigravity, OpenCode, Pi)
GEMINI.md                         Gemini CLI context
.cursor/rules/voiceprint.mdc      Cursor project rule
.github/copilot-instructions.md   GitHub Copilot instructions
.github/workflows/                CI: every check on push and pull request, plus the weekly freshness run
vendor/humanizer/                 synced copy of the humanizer skill (canonical: humanizer)
vendor/authenticity-check/        synced copy of the authenticity-check skill
scripts/text_hygiene.py           deterministic Unicode inspection and cleanup
scripts/check                     every repository check, exactly as CI runs it
scripts/sync-upstream             re-pulls vendored files and stamps headers
scripts/check-vendor-headers      validates vendored headers, bodies, and referenced files
scripts/check-upstream-freshness  flags when a vendored skill is behind its upstream
tests/test_text_hygiene.py        exact API and CLI fixtures for the hygiene policy
tests/test_repository.py          consistency checks for versions, adapters, evals, scripts, and CI
evals/evals.json                  verification cases asserting hygiene and one-pass behavior
evals/files/VOICE.md              voice-mode fixture for the evals
CHANGELOG.md                      release history
CONTRIBUTING.md                   maintainer guide: checks, syncing, releases, project state
.godpowers/                       maintainer workflow state (plan, decisions, evidence)
```

## License

MIT. See [LICENSE](LICENSE). The vendored skills are MIT under the same
copyright; their canonical sources are the humanizer and authenticity-check
repos.
