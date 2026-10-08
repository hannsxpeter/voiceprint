# Contributing to voiceprint

This guide is for changing voiceprint itself. To use the skill, read the
[README](README.md).

## Checks

Run every check CI runs before you push:

```sh
sh scripts/check
```

It runs the hygiene and repository test suites, then
`scripts/check-vendor-headers`. CI runs the same command on Python 3.11, the
documented minimum, and 3.14. The "Protect main" ruleset accepts a change
only when the `vendor-sync-check (3.11)` and `vendor-sync-check (3.14)` jobs
pass on a branch that is up to date with `main`. If you change the Python
versions CI tests, update the ruleset's required checks to the new job names
before merging, or the pull request cannot merge.

Three checks are opt-in because they need extra files, an extra tool, or a
quiet machine:

- The Unicode data check compares the pinned emoji tables and
  default-ignorable handling with the official Unicode 17.0 files. The
  README's "Deterministic text hygiene" section has the commands.
- The bidirectional check compares directional-mark decisions with GNU
  FriBidi:

  ```sh
  VOICEPRINT_FRIBIDI=1 python3 -m unittest -v tests.test_text_hygiene.BidiReferenceTests
  ```

- The release benchmark holds cleanup of 100,000 code points to a 200 ms
  p95 (`VOICEPRINT_RELEASE_BENCHMARK=1`, also in the README).

## Changing hygiene behavior

A change to what `scripts/text_hygiene.py` removes, normalizes, or keeps
bumps `POLICY_VERSION`, comes with exact fixtures in
`tests/test_text_hygiene.py`, and is described in the README and the
changelog. Write invisible characters in source as escapes, never as literal
characters; a repository test fails if tracked text outside `vendor/`
contains anything the helper would act on.

## Vendored skills

Never edit anything under `vendor/`. Land the change in the upstream repo,
then re-sync with `scripts/sync-upstream` as the README's "Sync procedure"
describes. `scripts/check-upstream-freshness` reports when a re-sync is due.

## Releases

1. Set the new version in `SKILL.md` (`metadata.version`) and in the README
   badge, and move the `[Unreleased]` changelog entries under it with the
   release date and a compare link.
2. Merge the release pull request once CI passes.
3. Tag the merge commit and push the tag:

   ```sh
   git tag -a vX.Y.Z -m "voiceprint vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. Publish a GitHub release for the tag from the changelog entry.
5. Record the release in `.godpowers/STATE.md` in a follow-up pull request.

## Project state

Maintainer state lives in `.godpowers/`, kept with Godpowers 7. `STATE.md`
holds the goal, current work, and open risks; `PLAN.md` the latest plan; and
`DECISIONS.md` an append-only log of lasting decisions. Before calling code
work done, record the project check against the code on disk:

```sh
node ~/.claude/godpowers/bin/godpowers.js verify "sh scripts/check"
```

Godpowers 7 is not on the public npm registry (as of October 2026 the latest
published version is 6.3.0), so `npx godpowers@7` fails. Use the CLI that the
Godpowers installation puts in `~/.claude/godpowers/`.
