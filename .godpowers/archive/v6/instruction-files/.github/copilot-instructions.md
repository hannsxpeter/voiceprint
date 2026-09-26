# voiceprint (GitHub Copilot instructions)

<!-- Implements: P-MUST-01, P-MUST-05, P-MUST-06, P-MUST-07, P-MUST-08, P-MUST-09 -->

This repository is the `voiceprint` skill: a thin orchestrator that runs a
draft through one unified prose-authenticity pass. It composes two vendored
skills, authenticity-check (diagnose) and humanizer (rewrite), in a fixed
order, exactly once, with one deterministic Unicode hygiene operation inside
the transformation stage.

When a request is the combined intent (clean this up and verify it, make this
authentic and tell me how it scored, de-slop this then check it, humanize and
then check, or "voiceprint this"), follow this skill. Apply it even when the
word "voiceprint" is not used. Do not apply it to a one-sided request: a pure
rewrite is the standalone humanizer skill, a pure score is the standalone
authenticity-check skill. voiceprint is the union, not a substitute. For a
half-request, serve only that half and stop: use the standalone skill if
installed, otherwise follow the matching vendored copy directly
(`vendor/humanizer/` for rewrite-only, `vendor/authenticity-check/` for
score-only), never a half-empty voiceprint pass.

Read `SKILL.md` at the repository root and follow it exactly. Run three steps
in order, once each: (1) diagnose the immutable original by reading
`vendor/authenticity-check/SKILL.md`, carrying out no target score; (2) run
`python3 scripts/text_hygiene.py clean --stats` once, preferring standard input
for pasted text, then pass its cleaned working copy to one invocation of
`vendor/humanizer/SKILL.md` (voice discovery, density pre-check, multi-pass
workflow, meaning check); (3) re-diagnose once on the after text,
fresh and cold, for residual reporting only. Emit the exact output contract:
Before / Authenticity read (before) / After / What changed / Residual / What
remains is a human's call. Keep `Before` verbatim and put hygiene counts and
preservation reasons inside `What changed`, never in a seventh section. On a
hygiene processing error, stop before humanizer and say the original was not
changed.

Hard rule: one pass, never a loop. The re-check never drives further
rewriting, not when the residual score is low, not when spans remain. One
diagnose, one rewrite, one re-diagnose, then stop and report. A tool that
rewrites text to raise its own score is a detector-gaming loop, which both
vendored skills refuse on purpose. voiceprint is not for defeating
AI-detection systems and names no detector; reframe such requests toward
quality and authentic voice. Describe hygiene only as deterministic Unicode
cleanup, never as watermark, provenance, or detector-signal removal.

Everything under `vendor/` is a synced copy, not the source of truth. Never
edit a vendored file. Detection and rewrite criteria are canonical in the
humanizer repo, scoring logic in the authenticity-check repo. Fixes go
upstream and are re-synced via `scripts/sync-upstream`; each file's header
stamp is the contract. See `README.md` for the full sync procedure.

<!-- godpowers:begin -->
## Godpowers project

This project uses Godpowers. See `AGENTS.md` for the project context.
<!-- godpowers:end -->
