# voiceprint (agent instructions)

<!-- Implements: P-MUST-01, P-MUST-05, P-MUST-06, P-MUST-07, P-MUST-08, P-MUST-09 -->

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
   voice discovery, density pre-check, multi-pass workflow, and meaning check.
   This is the after text.
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
Step 2 again, that is precisely the failure this skill forbids. Stop.

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

<!-- pillars:begin -->
# Godpowers Project Context

This is a Godpowers project. Godpowers uses the Pillars standard as its native project context layer.
Coding agents read project context from `./agents/*.md` before changing code, while `.godpowers/` remains the Godpowers workflow state and artifact layer.

This project follows Pillars 1.1.0. Coding agents read project pillar files before acting.

## At the start of any task

1. Resolve scopes from repository root to the task target. A scope contains both `AGENTS.md` and `agents/`. Apply outer scopes first and let the nearest scope win conflicts.
2. Inventory pillar frontmatter recursively, local exclusions, and optional `agents/catalog.yaml` absent concerns in each scope.
3. Load every pillar whose frontmatter has `always_load: true`. Match remaining `triggers` with the Pillars portable ASCII token matcher to select primaries and absent concerns.
4. Add each primary pillar direct `must_read_with` dependencies, depth 1 only. Path-qualified sub-pillars use identities such as `auth/agent-registration`.
5. Add a selected pillar `see_also` target only when the task matches the target identity, triggers, or covers. Do not follow soft references recursively.
6. Read every selected body. Follow Rules, apply Workflows, heed Watchouts, and ask before deciding open Gaps.

## Handling missing pillars

| State | Action |
|---|---|
| `status: present` | Load and comply. |
| `status: stub` | Treat the concern as acknowledged but undecided. Ask before making domain decisions. |
| Name in `excluded:` | Treat as intentionally not applicable in that scope. |
| Trigger matches local `agents/catalog.yaml` entry | Infer from code, state the assumption, and recommend authoring the pillar. |
| No local file, exclusion, or catalog entry | Make no Pillars-specific claim about that concern. |

If `context.md` or `repo.md` is missing and not explicitly excluded, pause and ask the human to create a stub or record an exclusion.

## Excluded pillars

```yaml
excluded: []
```
<!-- pillars:end -->

<!-- godpowers:begin -->
## Godpowers project

This project uses Godpowers. The on-disk state is the source of truth;
conversation memory is not.

- Project: voiceprint
- Mode: B    Scale: small
- State: `.godpowers/state.json` is authority; `.godpowers/PROGRESS.mdx` is generated for humans

### Quarterback rule

There is exactly one orchestrator: `god-orchestrator`. It owns writes to
`state.json`, `intent.yaml`, and `events.jsonl`; `PROGRESS.mdx` is regenerated from state. Skills like
`/god`, `/god-next`, `/god-status` read state without writing.

### Useful commands

- `/god-status` - re-derive state from disk
- `/god-next` - what to run next, with reason
- `/god-mode` - run the full autonomous project run
- `/god-sync` - refresh artifacts, context, and source-system sync-back
- `/god-migrate` - import or sync legacy planning, BMAD, or Superpowers context
- `/god-context refresh` - refresh AI-tool awareness for this project

### Linkage status

- Coverage: 91%
- Orphans: 1

### Active artifacts

- orchestration: `prep/INITIAL-FINDINGS.mdx`
- prd: `features/text-hygiene/PRD.mdx`
- arch: `features/text-hygiene/ARCH-DELTA.mdx`
- build: `features/text-hygiene/PLAN.mdx`
- harden: `features/text-hygiene/HARDEN-FINDINGS.mdx`

See `.godpowers/state.json` for authority and `.godpowers/PROGRESS.mdx` for the generated tier table.
<!-- godpowers:end -->
