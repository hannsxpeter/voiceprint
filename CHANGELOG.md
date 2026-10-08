# Changelog

All notable changes to this skill are documented here. This project adheres
to semantic versioning.

## [Unreleased]

## [1.5.0] - 2026-10-07

### Changed

- Re-synced the vendored skills to their latest upstream releases, humanizer
  1.3.1 (@ 09bf76d) and authenticity-check 1.2.1 (@ b20c10a), from the 1.1.1
  commits vendored in 1.2.0. This adds humanizer's prompt-level text-hygiene
  preflight (`references/text-hygiene.md`, with an exact codepoint search
  since 1.3.0) and authenticity-check's read-only Unicode provenance
  preflight (`references/provenance-signals.md`) with its
  `Provenance signals` report section. humanizer 1.3 also corrects its
  worked examples and the shared criteria (`tell-patterns.md`,
  `voice-matching.md`) that voiceprint vendors into both trees.
- The output contract now states how those upstream additions fit the single
  pass without adding a stage or a loop. Both authenticity reads carry
  authenticity-check's provenance signals, which are reported and never
  cleaned. Humanizer's `Text hygiene:` header line folds into `What changed`
  after the helper's manifest counts, which stay authoritative. Neither
  vendored skill's standalone `Next step` is emitted inside the pass; inside
  the residual, authenticity-check's would have sent the user back to a
  rewrite. Every adapter carries the same rule.
- Text hygiene policy version 2 (manifests report `"policy_version": 2`):
  - U+FE0E and U+FE0F are preserved only directly after one of the 371 bases
    in the pinned Unicode Emoji 17.0 variation-sequence data, and after `#`,
    `*`, or a digit only when U+20E3 follows. Selectors after other bases and
    repeated selectors are removed, including after emoji that have no
    variation sequence, such as U+1F600 U+FE0F, which policy 1 kept; those
    emoji already default to emoji presentation, so rendering is unchanged.
    Preservation reasons for these selectors now name the pinned variation
    data instead of an emoji range.
  - Tag characters are preserved only inside the three RGI emoji tag
    sequences.
  - Mongolian variation selectors are preserved only directly after a
    Mongolian letter, and the Mongolian vowel separator U+180E only between
    Mongolian letters.
  - Unassigned default-ignorable code points are removed. The seven
    default-ignorable letters and marks that render invisibly but have
    orthographic uses (U+034F, U+115F, U+1160, U+17B4, U+17B5, U+3164,
    U+FFA0) are preserved and reported, so every default-ignorable code point
    in the Unicode 17.0 data is at least reported.
- `scripts/sync-upstream` vendors every tracked `references/*.md` file at the
  stamped commit instead of a fixed list, reads file bytes from that commit
  rather than the working tree, stamps each header with the upstream blob id,
  and warns when the commit is not on a remote-tracking branch.
  `scripts/check-vendor-headers` fails when a vendored `SKILL.md` names a
  reference file that was not vendored. The fixed list would have silently
  skipped both reference files the upstreams added.
- `scripts/check-upstream-freshness` reports a re-sync as due only when an
  upstream commit since the stamp changed `SKILL.md` or a `references/` file,
  so commits that touch only an upstream's CI or documentation no longer
  raise false alarms.
- One entry point, `scripts/check`, runs every repository check, and CI runs
  it on Python 3.10 (the documented minimum) and 3.14. The new
  `tests/test_repository.py` covers frontmatter, version consistency, adapter
  rules, the `SKILL.md` contract, eval structure, shell syntax, workflow
  pinning and credentials, the dash policy across every tracked file outside
  `vendor/`, and `scripts/check-vendor-headers` itself. Pushes report stale
  vendored copies as a warning. The `upstream-freshness` workflow's checkout
  action is pinned to a full commit SHA like the validation workflow, and the
  workflow documents how to re-enable it after GitHub's inactivity pause.
- `SKILL.md` frontmatter adds `license: MIT`, lists `allowed-tools` in the
  space-separated form from the Agent Skills spec (as humanizer has since 1.3.0),
  and states the Python 3.10 requirement in `compatibility`.
- Added eval 12 (provenance signals and `Next step`) and eval 13 (a draft
  that tries to close a heredoc).

### Fixed

- Text hygiene no longer alters valid emoji. Policy 1 kept presentation
  selectors only after bases in two hard-coded emoji blocks, which broke 40
  basic emoji presentation sequences (such as U+00A9 U+FE0F and U+2B05
  U+FE0F), all 12 keycap sequences, and the two head-shaking ZWJ sequences,
  and it stripped the tag characters from the England, Scotland, and Wales
  flags. That contradicted the 1.4.0 README, which said every pinned ZWJ
  sequence passes unchanged. An opt-in test class
  (`VOICEPRINT_UNICODE_DATA_DIR`) now checks the pinned tables and the
  cleanup result against local copies of the official Unicode files.
- Policy 1 never reported 3,776 of the 4,174 default-ignorable code points,
  among them U+034F and the Hangul fillers. U+2065 and the reserved code
  points of the tag block were listed for removal, but the check only ran
  for assigned format characters, so they were never removed.
- Any number of Mongolian variation selectors after one Mongolian letter
  were all kept, an unbounded hidden channel.
- The Mongolian vowel separator was removed as a hidden control even between
  Mongolian letters, where it selects the separated form of a final vowel.
- README: the eight supported tools were described as the subset both
  upstream skills share, but the upstreams document more (Devin Desktop,
  formerly Windsurf; Cline; Continue; Zed; and Aider). The note on vendored
  frontmatter now matches upstream (humanizer dropped `compatibility`;
  authenticity-check moved it under `metadata`), and Pi Coder is now called
  Pi, as upstream renamed it.
- GitHub had disabled the scheduled `upstream-freshness` workflow after 60
  days without repository activity, so the vendored copies missed every
  upstream release after 1.1.1 without notice. The workflow is re-enabled,
  and every push now reports staleness as well.

### Security

- `SKILL.md` pre-approves only read-only tools (`Read Glob Grep`). It used to
  pre-approve `Bash`, `Write`, and `Edit` for the turn that runs the pass,
  which reads untrusted text, so injected instructions could run commands or
  write files without a prompt. `SKILL.md` and every adapter now forbid
  passing pasted text through a shell command or heredoc, where a draft line
  matching the delimiter would run whatever follows it (eval 13).
- `scripts/sync-upstream` refuses to run outside a voiceprint checkout, fails
  closed when upstream `git status` fails, vendors only regular files
  directly under `references/`, and builds the new tree in a private work
  directory before swapping it in, with signals ignored during the swap and
  the old tree restored if it fails. A crafted upstream or a symlinked
  invocation can no longer write outside `vendor/`, delete another `vendor/`
  directory, or leave `vendor/` half rebuilt.
- `scripts/check-vendor-headers` verifies each vendored body against the
  upstream blob id stamped in its header, so an edit made here instead of
  upstream fails CI unless the stamp is rewritten too, which shows in review
  as a `Source blob` change with no `Source commit` change. `.gitattributes`
  keeps git from converting line endings in `vendor/` and in `scripts/`.
- CI checkout no longer persists credentials, and the freshness warning step
  runs on pushes only, so code from a pull request cannot read the token.

### Removed

- `agents/`: unfilled Pillars stub pillars, orphaned since the Godpowers 7
  migration removed the instruction block that loaded them.
- `.godpowers/archive/v6/`: Godpowers 6 state kept during that migration. Its
  lasting decisions are recorded in `.godpowers/DECISIONS.md`, and the files
  remain in git history.
- The `Implements:` requirement tags in `SKILL.md`, the adapters, the hygiene
  helper, its tests, and the workflow, which pointed only at that archive.

## [1.4.0] - 2026-08-15

### Added

- Added a dependency-free deterministic Unicode hygiene stage, inspired by
  [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover),
  at the start of Voiceprint Step 2. The original remains verbatim for
  `Before` and the before diagnosis; one cleaned working copy reaches the
  existing single humanizer invocation.
- Added `scripts/text_hygiene.py` with importable inspection and cleanup APIs,
  `inspect` and `clean` CLI operations, deterministic code-point manifests,
  same-family script preservation, Unicode Emoji 17.0 ZWJ pair data, exact
  UTF-8 output, a 4 MiB input cap, exact unit and CLI fixtures, and CI coverage.
- Added hygiene behavior evals for positive findings, zero findings,
  load-bearing Unicode preservation, and detector-framed requests.

### Changed

- The six-section result now reports detected, removed, normalized, and
  deliberately preserved hygiene counts inside `What changed`. The residual
  remains report-only and cannot trigger another cleanup or rewrite.
- Clarified that Unicode cleanup does not establish watermark presence,
  vendor provenance, or a detector signal. Statistical watermark rewriting,
  metadata removal, media processing, NFKC normalization, confusable mapping,
  and detector optimization remain outside Voiceprint's scope.
- Manifests now report the Python Unicode database version and pinned Emoji
  ZWJ version. Unknown format controls are preserved conservatively with a
  reason instead of being removed as a class.
- The 200 ms p95 release benchmark is opt-in through
  `VOICEPRINT_RELEASE_BENCHMARK=1`; routine CI remains timing-independent.

### Security

- Restricted path input to unchanged regular, non-symbolic-link files using
  pre-open and post-open identity checks, no-follow behavior where available,
  and nonblocking open behavior where available. Symlinks, FIFOs, and
  check-then-open replacements fail without exposing input or blocking.
- Narrowed variation-selector and emoji-joiner preservation claims to the
  evidence the pinned policy actually establishes. The validation workflow
  now uses read-only repository permissions and immutable action revisions.

## [1.3.0] - 2026-05-29

### Added

- `scripts/check-upstream-freshness` and a scheduled `upstream-freshness`
  workflow (weekly, plus manual dispatch) that compare each vendored skill's
  stamped source commit against its canonical upstream's latest commit and fail
  when a re-sync is due. Closes the gap that let the vendored copies drift a
  full version behind: the one-directional sync obligation no longer depends on
  a maintainer remembering to re-pull. The check is read-only (GitHub API via
  `gh` / `GH_TOKEN`), distinguishes stale (exit 1) from could-not-check
  (exit 2), and is covered by the existing CI script syntax-lint.

## [1.2.0] - 2026-05-29

### Changed

- Re-synced the vendored skills to their upstream 1.1.1 releases (humanizer
  @ 17c544e, authenticity-check @ 71c3ec9), refreshing content vendored from
  the earlier 1.0.0-era commits. Pulls in the upstream 1.1.x work (expanded
  worked examples, SKILL.md refinements, scoring additions); the vendored
  frontmatter now reads version 1.1.1. voiceprint adds no method of its own,
  so this is purely a refresh of the bundled behavior, re-stamped and
  validated by `scripts/check-vendor-headers`.

### Fixed

- Resolved the `Scriven` -> `Scriveno` naming drift the documentation audit
  surfaced in `vendor/`. humanizer had already corrected it upstream; a missed
  occurrence in authenticity-check's `SKILL.md` was fixed upstream and pulled
  in by this re-sync. No bare `Scriven` remains in `vendor/`.

## [1.1.1] - 2026-05-29

### Fixed

- README Layout: the `.github/workflows/` descriptor now reflects the full CI
  scope as of 1.1.0 (sync-header gate plus sync-script lint and an evals.json
  parse check), instead of naming only the sync-header gate.
- README compatibility note: names the specific tools authenticity-check
  declares beyond voiceprint's eight-adapter set (windsurf, cline, continue,
  zed, aider) instead of an imprecise "a few," from a full documentation audit.

## [1.1.0] - 2026-05-29

### Changed

- Clarified one-sided-request handling in `SKILL.md` and every tool adapter: a
  rewrite-only or score-only request is served as just that half (the
  standalone skill when installed, otherwise the matching vendored copy under
  `vendor/`), never a half-empty voiceprint pass. The verification cases for
  those two requests now assert that observable behavior instead of naming a
  routing target that may not be installed.
- Stated that voiceprint's output contract supersedes the vendored skills' own
  output wrappers: humanizer's `Voice:` / `Density:` header folds into "What
  changed," and its standalone "Next step" file-write offer is not emitted
  inside the pass. An optional, user-initiated write of the "After" text is the
  only reason the skill lists `Write` and `Edit`; the pass is otherwise
  read-only.
- Noted in `README.md` that voiceprint ships adapters for the eight tools both
  upstreams share, and that a vendored skill's own broader `compatibility:`
  frontmatter is upstream's, synced verbatim, not a voiceprint adapter claim.
- Added the missing `examples` reference to the authenticity-check entry in the
  `SKILL.md` reference-file list.

### Tooling

- `scripts/check-vendor-headers` now iterates vendored files with a
  here-doc-fed `while read` loop, tolerating spaces in a path while keeping the
  fail flag in the current shell.
- CI (`vendor-sync-check`) additionally syntax-checks both sync scripts and
  validates that `evals/evals.json` parses, so a broken script or malformed
  eval spec fails the build instead of landing silently.

## [1.0.0] - 2026-05-15

First stable release.

### Added

- Thin-orchestrator `voiceprint` skill: `SKILL.md` plus vendored copies of
  the two upstream skills. It adds no method of its own; the behavior lives
  entirely in the vendored content.
- The one-pass guarantee: run authenticity-check once on the input, apply
  humanizer's fixes once, run authenticity-check again only to report the
  residual. No iteration toward a score threshold. The re-check informs the
  user and never drives further rewriting. A silent score-optimization loop
  is exactly what this design forbids.
- Output contract: before text, before authenticity read, humanized after
  text with humanizer's own what-changed / deliberately-left-alone /
  meaning-check report, the residual read after the single pass, and an
  explicit statement that what remains is human judgment, not another
  automated rewrite.
- Scope and intended-use boundary inherited verbatim in spirit from the
  vendored skills: not designed or tuned to defeat plagiarism or
  AI-detection systems, names and targets no detector, reframes
  assessment-evasion requests toward genuine quality and voice.
- Non-colliding trigger description: fires on the combined diagnose-fix-report
  intent ("clean up and verify," "make this authentic and tell me how it
  scored," "voiceprint this") and explicitly defers pure-rewrite requests to
  the standalone humanizer skill and pure-score requests to the standalone
  authenticity-check skill.
- Vendored humanizer skill, synced from the canonical
  [humanizer](https://github.com/hannsxpeter/humanizer) repo:
  `vendor/humanizer/SKILL.md` and its `references/` (tell-patterns,
  do-not-flag, voice-matching, examples). Last synced 2026-05-16 from
  humanizer commit `ddb4b6f`.
- Vendored authenticity-check skill, synced from the canonical
  [authenticity-check](https://github.com/hannsxpeter/authenticity-check) repo:
  `vendor/authenticity-check/SKILL.md` and its native `references/`
  (scoring, examples). Last synced 2026-05-16 from authenticity-check commit
  `119f666`.
- Shared detection criteria (`tell-patterns.md`, `do-not-flag.md`,
  `voice-matching.md`) re-vendored through the authenticity-check tree to keep
  its `SKILL.md` paths intact; their header names the true canonical upstream,
  the humanizer repo, not authenticity-check. Last synced 2026-05-16 from
  humanizer commit `ddb4b6f`.
- Sync tooling: `scripts/sync-upstream` re-pulls the vendored runtime files
  from the two upstream repos and stamps every file with its sync header. It
  refuses to run when an upstream working tree is dirty, so the stamped
  commit always reproduces the vendored bytes. `scripts/check-vendor-headers`
  validates every file under `vendor/` carries a well-formed header.
- CI sync-header gate (`.github/workflows/vendor-sync-check.yml`): the build
  fails if any vendored file is missing a valid sync header.
- **Vendored-content sync obligation (recorded here as a standing
  commitment):** every file under `vendor/` is a synced copy, not the source
  of truth. The sync is one-directional: detection and rewrite criteria are
  canonical in the humanizer repo, scoring logic is canonical in the
  authenticity-check repo. When upstream criteria or logic change, the
  vendored copies must be re-synced via `scripts/sync-upstream`. They must
  never be edited in this repo independently, or voiceprint silently disagrees
  with the skills it advertises. The header stamp on each file is the
  contract.
- Multi-tool support mirroring humanizer: Claude Code, Cursor, Codex,
  Antigravity, Gemini CLI, Pi Coder, OpenCode, and GitHub Copilot, via
  `SKILL.md`, `AGENTS.md`, `.cursor/rules/voiceprint.mdc`, `GEMINI.md`, and
  `.github/copilot-instructions.md`. Every adapter points the agent at the
  same `SKILL.md` and the same vendored skills.
- Verification eval set (`evals/evals.json`) asserting the one-pass behavior
  and that no iteration toward a score occurs, with a voice-mode fixture
  (`evals/files/VOICE.md`). MIT license.

### Deviations from the upstream repos

- `voiceprint` adds a `scripts/` directory and a `.github/workflows/` CI
  check. The upstream humanizer and authenticity-check skills are pure-prompt
  with no scripts and no CI. These additions are required: voiceprint carries
  a vendoring sync obligation that the standalone skills do not, so it needs a
  sync tool and a check that the obligation is being met.

[Unreleased]: https://github.com/hannsxpeter/voiceprint/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/hannsxpeter/voiceprint/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/hannsxpeter/voiceprint/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/hannsxpeter/voiceprint/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/hannsxpeter/voiceprint/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/hannsxpeter/voiceprint/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/hannsxpeter/voiceprint/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hannsxpeter/voiceprint/releases/tag/v1.0.0
