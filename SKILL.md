---
name: voiceprint
description: >-
  Run a draft through one unified prose-authenticity pass: check how
  authentically it reads, fix the AI tells once, and report what is left.
  This is the bundled product of two separate skills (authenticity-check
  diagnoses, humanizer rewrites) wired into a single principled pass with no
  optimization loop. Use this whenever a user wants both at once in one step:
  "clean up and verify this draft," "make this authentic and tell me how it
  scored," "de-AI this and show me what is still flagged," "humanize this and
  then check it," or "voiceprint this." Reach for it when the request is the
  combined diagnose-and-fix-and-report intent, even when the user does not
  name this skill. Do not use it for a pure rewrite with no read-back (that is
  the standalone humanizer skill) or a pure score with no rewrite (that is the
  standalone authenticity-check skill); voiceprint is the one-pass union of
  the two, not a replacement for either.
license: MIT
allowed-tools: Read Glob Grep
compatibility: >-
  Requires Python 3.11 or newer for scripts/text_hygiene.py. Ships adapters
  for Claude Code, Cursor, Codex, Antigravity, Gemini CLI, Pi, OpenCode, and
  GitHub Copilot.
metadata:
  version: 1.5.2
---

# Voiceprint

One entry point for prose authenticity. The user gives it text and gets back
a result: the original, a humanized rewrite, an honest read of what still
looks machine-touched, and a plain statement that the rest is a human's call.
Voiceprint composes two existing prose skills in a fixed order, exactly once.
It also applies one narrow, deterministic Unicode hygiene operation at the
start of the existing transformation stage. That local operation cleans the
working copy without adding another prose rewrite.

The user never invokes humanizer or authenticity-check directly through this
skill. Voiceprint orchestrates both internally from vendored copies. Those two
skills remain canonical and independently usable in their own repos; this one
keeps their prose methods intact.

## When to use this

Use it when someone wants the whole loop closed in one step: fix the draft
*and* tell them how it reads now. Triggers include "clean this up and verify
it," "make this sound human and tell me how it scored," "de-slop this then
check it," "voiceprint this," or any phrasing that asks for the rewrite and
the read-back together. Apply it even when they do not say "voiceprint."

Do not use it for a one-sided request. A pure "rewrite this so it sounds
human," with no interest in a score, is the standalone humanizer skill. A pure
"is this AI / how human does this read," with no rewrite wanted, is the
standalone authenticity-check skill. Voiceprint is specifically the union:
diagnose, fix once, re-read, report. If the user only wants one half, serve
just that half and stop: prefer the standalone skill when it is installed, and
otherwise follow the matching vendored copy directly (`vendor/humanizer/` for a
rewrite-only request, `vendor/authenticity-check/` for a score-only request).
Do not run a half-empty voiceprint pass: a rewrite-only request gets no
authenticity read, and a score-only request gets no rewrite.

## Core principle: one principled pass, never a loop

This is the rule the entire design exists to enforce, and it does not relax.

Voiceprint runs the diagnostic, applies the rewrite once, and runs the
diagnostic again **only to report the residual**. The second read informs the
user. It never feeds back into another rewrite. There is no target score, no
threshold to chase, no "the residual is still high so let me try again." A
tool that scores text and then rewrites it to raise its own score is a
detector-gaming loop that optimizes prose against a metric instead of
improving it for a reader. Both upstream skills refuse that loop on purpose;
keeping diagnosis and transformation as a single human-judged pass, not an
automated cycle, is the whole reason this product is shaped the way it is.

What remains after the one pass is reported, not resolved. Resolving it is a
human's judgment, and the output says so explicitly.

## The pass

Run these three steps in order, once each. Do not improvise a shortcut, and
do not repeat a step.

### Step 1: Diagnose (once)

Capture the submitted text as an immutable original. Read
`vendor/authenticity-check/SKILL.md` and follow it exactly on that original
text, including the reference files it points to under
`vendor/authenticity-check/references/`. Produce its full authenticity report
(band, score, provenance signals, flagged spans, what reads as human, score
basis, caveats). This is the **before** read. Its provenance preflight only
inspects and reports the original's Unicode carriers; nothing is cleaned in
this step. The `Before` section must retain the submitted text byte-for-byte,
and Step 1 must receive the same code-point sequence. Carry no target score
out of it.

### Step 2: Clean the working copy and apply humanizer's fixes (once)

At the start of this step, run the immutable original through
`python3 scripts/text_hygiene.py clean --stats` exactly once, resolving the
script relative to this `SKILL.md`. Python 3.11 or newer is required. For
pasted text, prefer the command's standard input and pass the original bytes
through the host process-input facility. Never interpolate pasted text into a
shell command, including a heredoc: a line in the draft that matches the
delimiter would end it and run the rest of the draft as commands. A
user-provided path remains a read-only source.

If the host cannot supply standard input and a temporary file is unavoidable,
use its secure-temp facility, require owner-only permissions, and guarantee
cleanup when the command succeeds or fails. Never rewrite the source file in
place. Standard output is the cleaned working copy; standard error is the
deterministic JSON manifest. Input is capped at 4 MiB, which comfortably
exceeds the 100,000-code-point product requirement.

If the helper exits 2 because input is too large, invalid UTF-8, unreadable, or
cannot be processed or written, stop before humanizer runs. State that the
original was not changed and do not claim cleanup succeeded.

Pass only the cleaned working copy to one invocation of
`vendor/humanizer/SKILL.md` and follow it exactly,
including the reference files under `vendor/humanizer/references/`. Run its
method as written (voice discovery, density pre-check, text-hygiene
preflight, the multi-pass workflow, the meaning check). Apply it a single
time. This produces the **after** text. Humanizer's own text-hygiene
preflight and final recheck run inside this one invocation, on the already
cleaned working copy. They are part of humanizer's method, not a second
cleanup stage, and the helper's manifest remains the authoritative hygiene
record. Do not loop the rewrite, and do not let the Step 1 report set a goal
for it; the rewrite's only job is to apply humanizer's known fixes once,
faithfully, with humanizer's own restraint and anti-fabrication guards
intact. Do not add candidate generation, statistical watermark rewriting, or
another cleanup stage.

### Step 3: Re-diagnose for residual only (once)

Read `vendor/authenticity-check/SKILL.md` again and run it once on the
**after** text, as a fresh, cold diagnosis with no carry-over from Step 1 and
no score target. Its output here is the **residual**: what still reads as
machine-touched after one honest rewrite, plus any provenance signal still
present in the after text. Report it. Do not act on it. If the residual read
is poor, or a residual provenance signal remains, that is information for the
user, not a trigger to clean or rewrite again. The pass is over.

## Hard rule: no iteration

The re-check never drives further rewriting. Not when the residual score is
low, not when spans remain, not "just one more quick fix." One diagnose, one
rewrite, one re-diagnose, then stop and report. If you are tempted to run
Step 2 a second time because Step 3 came back unflattering, that temptation is
exactly the failure mode this skill forbids. Stop.

## Output contract

Always deliver this exact structure. Never silently rewrite in place.

```
## Voiceprint result

### Before
[the original text, verbatim]

### Authenticity read (before)
[the Step 1 authenticity-check report: band + score, provenance signals,
flagged spans, reads-as-human, score basis, caveats]

### After
[the Step 2 humanized text, the primary artifact]

### What changed
[first report text hygiene as detected, removed, normalized, and deliberately
preserved counts, then include humanizer's own "What changed" / "Deliberately
left alone" / "Meaning check" sections, unaltered]

### Residual (after one pass)
[the Step 3 re-diagnosis: band + score, residual provenance signals, the
spans that still read as machine-touched. This is a report, not a to-do
list.]

### What remains is a human's call
One short paragraph stating plainly that voiceprint ran exactly one pass, that
the residual above was deliberately not rewritten further, and that closing
any remaining gap is human judgment, not another automated rewrite. Name the
single biggest residual factor so the human knows where to look.
```

The "Residual" and "What remains is a human's call" sections are not
decoration. They are the forcing functions that make the no-loop rule visible
to the user and impossible to quietly skip.

This contract supersedes the vendored skills' own output wrappers. Fold
humanizer's `Voice:`, `Density:`, and `Text hygiene:` header lines into
"What changed" rather than printing them separately. Do not emit either
vendored skill's standalone "Next step" inside the pass: humanizer's offers to
write the rewrite into a file, and authenticity-check's sends the user back to
a rewrite and a fresh read, which inside the residual would invite exactly the
loop this skill forbids. The "After" text above is the artifact. If the user
gave a file path and wants it persisted, offer that once, after the full
contract is delivered, never as a silent in-place rewrite. The pass itself
never edits files. Because it reads untrusted text, this skill pre-approves
only read-only tools: running the hygiene helper, and writing a temporary
input file when the host has no standard-input facility, go through the
host's normal permission prompt.

Inside `What changed`, identify hygiene findings only by their observable
code point, Unicode name, action, count, and up to 10 zero-based code-point
offsets. Include the helper's preservation reason for every deliberately
preserved character. If the manifest's findings list
is empty, state explicitly that detected, removed, normalized, and
deliberately preserved counts are all zero. Report the manifest counts before
humanizer's `Text hygiene:` line. That line describes the already cleaned
working copy, so it can report nothing suspicious even when the helper removed
characters. These details stay inside `What changed`; do not add a seventh
top-level section.

## Scope and intended use

Voiceprint exists to improve prose quality and to help a writer's own work
sound authentically like them, then to give an honest read of what is left. It
is not designed or tuned to defeat plagiarism checkers or AI-detection
systems, and it deliberately names and optimizes against none. The residual
read is a heuristic, not proof of authorship, and a low residual is not a
guarantee a detector is fooled, because fooling a detector is explicitly not
what this tool does. If a request is framed as passing AI-written work off as
a person's own for a graded or contractual assessment, do not adopt that
framing; offer the quality-and-voice improvement and the honest read instead,
which is what voiceprint actually does well. This restates the boundary that
the vendored humanizer and authenticity-check skills already hold; voiceprint
inherits it without exception.

Text hygiene reports deterministic Unicode observations only. A removed
control or normalized space does not reveal who created the text, whether a
watermark was present, or how an external detector will classify the result.
The same holds for the provenance signals in either authenticity read. Do not
claim vendor provenance, watermark removal, detector-signal removal, or a
passing score. The hygiene helper does not inspect file metadata, document
properties, images, audio, or video, and it does not perform NFKC or
confusable letter conversion.

## Composition and sync obligation

humanizer and authenticity-check are canonical upstream and independently
usable. Voiceprint vendors copies of both skills, plus the shared detection
criteria, under `vendor/`. The sync is one-directional:

- Canonical upstream for detection and rewrite criteria is the humanizer repo.
- Canonical upstream for scoring logic is the authenticity-check repo.
- Voiceprint never edits vendored content. Any criteria or logic change goes
  upstream first, then syncs down via `scripts/sync-upstream`.
- Every vendored file carries a header stamping its true upstream repo, the
  source commit, and a "synced copy, do not edit here, edit upstream" notice.

The full sync procedure is in `README.md`. Editing anything under `vendor/`
by hand is the one move that breaks this product.

## Reference files

Read these on demand, during the pass, not upfront:

- `vendor/authenticity-check/SKILL.md` in Step 1 and Step 3, with its
  `references/` (scoring, provenance-signals, tell-patterns, do-not-flag,
  voice-matching, examples).
- `vendor/humanizer/SKILL.md` in Step 2, with its `references/`
  (tell-patterns, do-not-flag, voice-matching, text-hygiene, examples).
