# Plan

Status: done. This plan shipped as voiceprint 1.5.0 (PR hannsxpeter/voiceprint#4). Later work, including hygiene policy 3 and the move to Python 3.11, is tracked in STATE.md and DECISIONS.md.

## Goal
Release voiceprint 1.5.0: bring the vendored skills current with their
latest upstream releases (humanizer 1.3.1, authenticity-check 1.2.1), make
the six-section contract account for what those releases now emit, stop text
hygiene from altering valid emoji, and leave the repository with no obsolete
files and no documentation drift.

## Requirements
- R1: The vendored skills match the latest published upstream releases (humanizer 1.3.1 @ 09bf76d, authenticity-check 1.2.1 @ b20c10a). Done when: `scripts/check-upstream-freshness` reports both skills current and every vendored body matches its upstream blob byte for byte.
- R2: A reference file added upstream cannot be silently left out of `vendor/`. Done when: `scripts/check-vendor-headers` fails on the previous sync script's output for the 1.2.1 upstreams and passes on the new sync output.
- R3: The contract covers the upstream additions without a new stage, section, or loop. Done when: `SKILL.md` and every adapter say provenance signals are reported without acting on them and neither vendored `Next step` is emitted, and `tests/test_repository.py` checks every adapter for it.
- R4: Hygiene leaves every valid emoji sequence in the pinned Unicode 17.0 data unchanged while still removing unsupported selectors and tags. Done when: `UnicodeEmojiDataTests` passes against the official files and the policy 2 fixtures pass.
- R5: No obsolete files or dead references remain. Done when: `agents/`, the Godpowers 6 archive, and every `Implements:` tag are gone, and the archive's lasting decisions are in DECISIONS.md.
- R6: Documentation matches behavior. Done when: README, CHANGELOG, `SKILL.md`, and the adapters describe the shipped behavior and the version consistency test passes.
- R7: Local checks and CI run the same checks. Done when: CI runs `sh scripts/check` on Python 3.10 and 3.14 and both pass.
- R8: The security pass's findings are closed. Done when: `SKILL.md` pre-approves only read-only tools and every adapter forbids heredocs for pasted text, `scripts/sync-upstream` rejects symlinked invocation, failed status, non-regular or nested reference entries, and mid-build failures without touching `vendor/`, vendored bodies are verified against their stamped blob ids, CI keeps no checkout credentials, and each guard has a test or a recorded probe.

## Non-goals
- Changing how hygiene treats no-break spaces and directional controls (an open risk for the maintainer to decide).
- Adding adapters for Devin Desktop (formerly Windsurf), Cline, Continue, Zed, or Aider.
- Editing anything under `vendor/` by hand, or vendoring unpublished upstream commits.
- Restructuring `vendor/` so the skill can be uploaded as a single claude.ai skill package.

## Design
- `scripts/sync-upstream` lists `references/*.md` with `git ls-tree` at the stamped commit and reads bytes with `git show`; the shared criteria still come from humanizer. `scripts/check-vendor-headers` resolves every `references/` path a vendored `SKILL.md` names.
- `scripts/text_hygiene.py` pins three Unicode Emoji 17.0 tables (ZWJ pairs, variation bases, RGI tag sequences). A presentation selector must directly follow a pinned base, keycap bases also need U+20E3, and manifests report policy version 2.
- `scripts/check` runs `python3 -m unittest discover -s tests` and `scripts/check-vendor-headers`; `tests/test_repository.py` holds the drift guards; CI calls `scripts/check`.
- `scripts/check-upstream-freshness` reports a re-sync as due only when an upstream commit since the stamp changed `SKILL.md` or `references/`, using one compare-API call per upstream.

## Slices
- [x] 1. Re-sync `vendor/` with reference discovery: byte comparison against the upstream blobs, freshness check, guard proof against the previous script.
- [x] 2. Hygiene policy 2: exact fixtures plus the opt-in Unicode data tests.
- [x] 3. One check entry point and repository consistency tests: `sh scripts/check` locally, plus mutation runs proving the drift guards fail when they should (the CI matrix runs in slice 6).
- [x] 4. Contract, adapters, README, CHANGELOG, and eval 12: repository tests and a read-through.
- [x] 5. Remove obsolete files and tags and record decisions: a leftover grep and Godpowers lint.
- [x] 6. Independent review and security pass, then ship v1.5.0: Godpowers ship gate, pull request CI on Python 3.10 and 3.14, tag, and GitHub release (PR #4 merged as d9c27a9, tag v1.5.0, release published).

## Open questions
- Resolved 2026-10-08: hygiene policy 3 preserves no-break spaces where locale typography depends on them and directional marks where mixed-direction display does (see DECISIONS.md), closing the low risk this plan left open.
