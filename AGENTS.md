# voiceprint (agent instructions)

This repository is the `voiceprint` skill: a thin orchestrator that runs a
draft through one unified prose-authenticity pass. It composes two vendored
skills, authenticity-check (diagnose) and humanizer (rewrite), in a fixed
order, exactly once, with one deterministic Unicode hygiene operation inside
the transformation stage. It is the entry point for any AI coding tool that
reads `AGENTS.md` (Codex, OpenCode, Antigravity, Pi Coder, and others).

## When to apply this skill

Apply it when the user wants the combined intent in one step: fix the draft
and tell them how it reads now. Triggers include "clean this up and verify
it," "make this authentic and tell me how it scored," "de-slop this then check
it," "humanize this and then check it," or "voiceprint this." Apply it even
when they do not say "voiceprint."

Do not apply it to a one-sided request. A pure rewrite with no read-back is
the standalone humanizer skill. A pure score with no rewrite is the standalone
authenticity-check skill. voiceprint is the union of the two, not a substitute
for either. Serve a half-request as just that half and stop: use the standalone
skill when it is installed, otherwise follow the matching vendored copy
directly (`vendor/humanizer/` for rewrite-only, `vendor/authenticity-check/`
for score-only). Do not run a half-empty voiceprint pass.

## How to run it

Read `SKILL.md` in this repository and follow it exactly. Do not improvise a
shortcut. In brief, run these three steps in order, once each:

1. **Diagnose once.** Read `vendor/authenticity-check/SKILL.md` and follow it
   on the immutable original. This is the before read. Carry no target score
   out of it.
2. **Clean and rewrite once.** Run
   `python3 scripts/text_hygiene.py clean --stats` once at the start of Step 2,
   preferring standard input for pasted text, then pass its cleaned working
   copy to one invocation of `vendor/humanizer/SKILL.md`. Follow humanizer's
   voice discovery, density pre-check, text-hygiene preflight, multi-pass
   workflow, and meaning check. This is the after text.
3. **Re-diagnose once, for residual only.** Read
   `vendor/authenticity-check/SKILL.md` again and run it on the after text as
   a fresh, cold diagnosis. Report the residual. Do not act on it.

Emit the exact output contract from `SKILL.md`: Before / Authenticity read
(before) / After / What changed / Residual / What remains is a human's call.
The `Before` text remains verbatim. Report hygiene counts and preservation
reasons inside `What changed`, never as a seventh top-level section. If the
helper cannot process the input, stop before humanizer and state that the
original was not changed.

## Hard rule (one pass, never a loop)

The re-check never drives further rewriting. Not when the residual score is
low, not when spans remain, not "one more quick fix." One diagnose, one
rewrite, one re-diagnose, then stop and report. A tool that rewrites text to
raise its own score is a detector-gaming loop, which both vendored skills
refuse on purpose. If Step 3 came back unflattering and you are tempted to run
Step 2 again, that is precisely the failure this skill forbids. Stop. Report
the provenance signals in both authenticity reads without acting on them, and
do not emit either vendored skill's standalone Next step inside the pass.

## Scope

voiceprint improves prose quality and authentic voice, then gives an honest
read of what is left. It is not for defeating plagiarism or AI-detection
systems, and names no detector. Reframe such requests toward genuine quality
and voice (see `SKILL.md` "Scope and intended use"). This is the same boundary
the vendored skills hold. Describe hygiene only as deterministic Unicode
cleanup, never as proof that a watermark, provenance signal, or detector
signal was found or removed.

## Vendored content

Everything under `vendor/` is a synced copy, not the source of truth. The sync
is one-directional: detection and rewrite criteria are canonical in the
humanizer repo, scoring logic is canonical in the authenticity-check repo.
Never edit a vendored file. A fix belongs upstream and is then re-synced via
`scripts/sync-upstream`. Each vendored file's header stamp is the contract;
see `README.md` for the full procedure.

<!-- godpowers:begin -->
## Godpowers

Project state lives in `.godpowers/` (STATE.md, PLAN.md, DECISIONS.md). Before calling code work done,
run `npx -y godpowers@7 verify "<check command>"`. `/god` shows the next step.
<!-- godpowers:end -->
