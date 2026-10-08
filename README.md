# voiceprint

![version](https://img.shields.io/badge/version-1.5.0-blue)
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
space and removes soft hyphens, U+200B, invalid or free-floating joiners,
directional controls, tag characters outside the pinned emoji tag sequences,
BOM, interlinear annotation controls, invisible operators, the Mongolian
vowel separator outside Mongolian words, and unsupported variation selectors.
Other format controls are preserved conservatively and reported with a
reason. Tabs, line breaks, fullwidth letters, and confusable visible letters
remain unchanged.

Script joiners are preserved only between letters in the same supported
script family, and the Mongolian vowel separator only between Mongolian
letters. Mongolian variation selectors are preserved only after a Mongolian
base. Emoji preservation uses three tables pinned from the official Unicode
Emoji 17.0 data:

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

Under this policy (version 2, since voiceprint 1.5.0), cleanup leaves every
sequence in the pinned data unchanged: 1,400 basic emoji, 12 keycap, 259 flag,
3 tag, 665 modifier, and 1,614 ZWJ sequences, plus all 742 emoji variation
sequences (keycap bases checked inside their keycap sequence). Policy version
1, shipped in 1.4.0, removed the selector from 132 of those variation
sequences, which broke 40 basic emoji, all 12 keycaps, and two ZWJ sequences,
and it stripped the tag characters from all three tag sequences. To reproduce
the check against the official files:

```sh
DATA=$(mktemp -d)
for f in emoji/emoji-sequences.txt emoji/emoji-zwj-sequences.txt ucd/emoji/emoji-variation-sequences.txt; do
  curl -fsSL -o "$DATA/$(basename "$f")" "https://www.unicode.org/Public/17.0.0/$f"
done
VOICEPRINT_UNICODE_DATA_DIR="$DATA" python3 -m unittest -v tests.test_text_hygiene.UnicodeEmojiDataTests
```

The helper is dependency-free, offline, and never writes a source file in
place. It requires Python 3.10 or newer, accepts at most 4 MiB (4,194,304
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
emitted inside the pass. The helper is deliberately stricter than humanizer's
prompt-level guidance in two places: it normalizes every Unicode space
variant and removes every directional control, including no-break spaces
that carry locale typography and directional marks that mixed right-to-left
and left-to-right text needs. Review the hygiene counts in `What changed` for
such text.

## Supported tools

| Tool | File it reads | Install |
|---|---|---|
| Claude Code | `SKILL.md` | `cp -r` this repo to `~/.claude/skills/voiceprint/`, or use the repo in-project |
| Cursor | `.cursor/rules/voiceprint.mdc` | Open this repo in Cursor, or copy `.cursor/rules/voiceprint.mdc` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` into your project |
| Codex | `AGENTS.md` | Clone this repo into (or beside) your project; Codex reads `AGENTS.md` |
| Antigravity | `AGENTS.md` | Same as Codex: keep `AGENTS.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` in the workspace |
| Gemini CLI | `GEMINI.md` | Keep `GEMINI.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` in the project Gemini runs in |
| Pi Coder | `AGENTS.md` | Point Pi Coder at this repo / its `AGENTS.md` |
| OpenCode | `AGENTS.md` or `SKILL.md` | Copy the skill into OpenCode's skills directory, or keep `AGENTS.md` in the project |
| GitHub Copilot | `.github/copilot-instructions.md` | Copy `.github/copilot-instructions.md` + `SKILL.md` + `scripts/text_hygiene.py` + `vendor/` into the target repository |

Every adapter points the agent at the same `SKILL.md`, deterministic hygiene
helper, and vendored skills under `vendor/`, so the one-pass behavior is
identical across tools.

voiceprint ships adapters for the eight tools above. Both upstream skills
also ship adapters for Windsurf, Cline, Continue, Zed, and Aider, which
voiceprint does not provide yet. The vendored skills' frontmatter is
upstream's, synced verbatim: humanizer no longer declares `compatibility`,
and authenticity-check lists its hosts under `metadata.compatibility`.
Neither is a claim that voiceprint provides an adapter for those tools.

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

3. The script refuses to run if either upstream working tree has uncommitted
   tracked changes. It vendors each skill's `SKILL.md` and every tracked
   `references/*.md` file, reading the bytes from the upstream HEAD commit so
   the stamped commit always reproduces them. It prepends the sync header
   (naming the true canonical upstream per file: the shared criteria always
   point at humanizer even inside the authenticity-check tree), warns when
   that commit is not on a remote-tracking branch, and prints a summary.
4. Verify and commit the updated `vendor/`:

   ```sh
   scripts/check
   git add vendor && git commit
   ```

`scripts/check-vendor-headers` runs inside `scripts/check` and therefore in CI
(`.github/workflows/vendor-sync-check.yml`). It fails the build if any file
under `vendor/` is missing a valid sync header, or if a vendored `SKILL.md`
names a reference file that was not vendored. Re-syncing is an obligation,
not an option: when the upstream criteria change, the vendored copies must be
re-pulled or the product silently disagrees with the skills it advertises.
`scripts/check-upstream-freshness` compares each vendored skill's stamped
commit with its upstream's default branch. A scheduled `upstream-freshness`
workflow runs it weekly and fails when a re-sync is due, and every push
reports the same staleness as a warning, so this obligation does not depend
on remembering. GitHub pauses scheduled workflows after 60 days without
repository activity, which is how the vendored copies fell two upstream
releases behind before 1.5.0. If the Actions tab shows `upstream-freshness`
as disabled, re-enable it there or with
`gh workflow enable upstream-freshness.yml`.

## Checks

`scripts/check` runs everything CI runs: the hygiene and repository test
suites (exact hygiene fixtures, shell syntax, eval JSON, version consistency
across `SKILL.md`, this README, and `CHANGELOG.md`, adapter routing, pinned
workflow actions, and the dash policy), then `scripts/check-vendor-headers`.
CI runs it on Python 3.10, the documented minimum, and 3.14.

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
AGENTS.md                         cross-tool entry point (Codex, Antigravity, OpenCode, Pi Coder)
GEMINI.md                         Gemini CLI context
.cursor/rules/voiceprint.mdc      Cursor project rule
.github/copilot-instructions.md   GitHub Copilot instructions
.github/workflows/                CI: every check on push and pull request, plus the weekly freshness run
vendor/humanizer/                 synced copy of the humanizer skill (canonical: humanizer)
vendor/authenticity-check/        synced copy of the authenticity-check skill
scripts/text_hygiene.py           deterministic Unicode inspection and cleanup
scripts/check                     every repository check, exactly as CI runs it
scripts/sync-upstream             re-pulls vendored files and stamps headers
scripts/check-vendor-headers      validates vendored headers and referenced files
scripts/check-upstream-freshness  flags when a vendored skill is behind its upstream
tests/test_text_hygiene.py        exact API and CLI fixtures for the hygiene policy
tests/test_repository.py          consistency checks for versions, adapters, evals, scripts, and CI
evals/evals.json                  verification cases asserting hygiene and one-pass behavior
evals/files/VOICE.md              voice-mode fixture for the evals
CHANGELOG.md                      release history
.godpowers/                       maintainer workflow state (plan, decisions, evidence)
```

## License

MIT. See [LICENSE](LICENSE). The vendored skills are MIT under the same
copyright; their canonical sources are the humanizer and authenticity-check
repos.
