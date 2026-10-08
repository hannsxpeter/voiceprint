# Decisions

Append-only. Newest last. To change a decision, add an entry that supersedes it.

## 2026-09-26: Move to the Godpowers 7 layout
Context: Godpowers 7 keeps one state file, a plan, this decision log, and an evidence ledger.
Decision: Archived the 6.x files under `.godpowers/archive/v6/`.
Why: Less state to keep in sync; gates are enforced by code instead of instructions.

## 2026-10-07: Remove the Godpowers 6 archive and the Pillars stubs
Context: `.godpowers/archive/v6/` held Godpowers 6 state kept for reference during the 7 migration, and `agents/` held unfilled Pillars stubs whose loading block the migration removed. The `Implements:` tags in shipped instruction files pointed only at requirement IDs in that archive.
Decision: Deleted both directories and every `Implements:` tag. The lasting 1.4.0 decisions are carried forward in the next entry. Recover the files with `git checkout 987d5a9 -- .godpowers/archive agents`.
Why: Nothing read them anymore, and dead references in instruction files cost every agent context for no benefit.

## 2026-10-07: Carry forward the 1.4.0 text hygiene decisions
Context: The archived 1.4.0 requirements and security review recorded why text hygiene works the way it does.
Decision: These stay standing rules. `Before` stays byte-for-byte and is diagnosed before any cleanup. One deterministic cleanup feeds exactly one humanizer invocation, and the residual never triggers another. Hygiene reports only observable code-point actions, never provenance, watermark, or detector claims. The helper stays dependency-free and offline, reads only regular non-symbolic-link files or standard input, caps input at 4 MiB, and never rewrites a source file. The 200 ms p95 benchmark for 100,000 code points stays opt-in for release runs. A machine-readable manifest in voiceprint's own output stays deferred until two host integrations ask for it.
Why: These were reviewed, released decisions, and deleting the archive must not lose them.

## 2026-10-07: Discover vendored reference files instead of listing them
Context: The fixed file list in `scripts/sync-upstream` would have skipped `references/text-hygiene.md` and `references/provenance-signals.md`, which the upstreams added in 1.2.0, while the vendored SKILL.md files already point at them.
Decision: Vendor every tracked `references/*.md` file at the stamped commit, read the bytes from that commit, and make `scripts/check-vendor-headers` fail when a vendored SKILL.md names a reference that was not vendored.
Why: The sync obligation should not depend on someone noticing a new upstream file.

## 2026-10-07: Pin emoji presentation and tag preservation to Unicode data (hygiene policy 2)
Context: Policy 1 kept presentation selectors only after two hard-coded emoji blocks and removed every tag character, which broke 132 official variation sequences (including all keycaps), two ZWJ sequences, and the three subdivision flags.
Decision: Preserve U+FE0E and U+FE0F only directly after one of the 371 Unicode Emoji 17.0 variation bases (keycap bases only before U+20E3), and tag characters only inside the three RGI tag sequences. Manifests report policy version 2.
Why: Preservation should follow the published data the documentation cites, and a data-backed rule can be checked against the official files.

## 2026-10-07: Fold upstream hygiene and provenance output into the six sections
Context: humanizer 1.2.x adds a `Text hygiene:` header line, and authenticity-check 1.2.x adds a `Provenance signals` section and keeps a `Next step` that routes the user back to a rewrite.
Decision: Provenance signals appear in both authenticity reads and are never acted on. humanizer's `Text hygiene:` line folds into `What changed` after the helper manifest, which stays authoritative. Neither vendored `Next step` is emitted inside the pass.
Why: This runs both skills as written while keeping the six-section contract and the no-loop rule intact.

## 2026-10-07: Pre-approve only read-only tools in SKILL.md
Context: The security pass showed that `allowed-tools` pre-approved `Bash`, `Write`, and `Edit` for the turn that runs the pass, while the pass reads untrusted pasted text; a draft line matching a heredoc delimiter could run the rest of the draft. Claude Code documents that Bash rules constraining arguments are fragile, so a narrower Bash pattern would not be a real boundary.
Decision: `allowed-tools: Read Glob Grep`. Running the hygiene helper and writing a temporary input file go through the host's normal permission prompt. `SKILL.md` and every adapter forbid passing pasted text through a shell command or heredoc, and a repository test keeps the grant read-only.
Why: One permission prompt per pass is a small price for never pre-approving shell commands or file writes during a pass over untrusted text.

## 2026-10-07: Stamp vendored blob ids and harden the sync
Context: Vendored headers were checked but bodies were not, so an in-place edit passed CI. `scripts/sync-upstream` also trusted `dirname "$0"`, failed open when `git status` failed, accepted any reference name, and deleted `vendor/` before rebuilding it.
Decision: Each header records the upstream blob id of its body and `scripts/check-vendor-headers` verifies it with `git hash-object`. The sync refuses to run outside a voiceprint checkout, fails closed on `git status`, vendors only regular files directly under `references/`, and swaps in a fully built staging tree. `vendor/` is marked `-text` so line endings never change.
Why: The vendoring contract (synced copy, never edited here) is now enforced by a check instead of a comment, and the one script that deletes files can only touch this repository's `vendor/`.

## 2026-10-07: Detect every default-ignorable code point (hygiene policy 2)
Context: Policy 1 reported none of 3,776 of the 4,174 Unicode 17.0 default-ignorable code points, and its removal list for U+2065 and reserved tag-block code points never ran because it sat behind a format-character check. Repeated Mongolian selectors after one letter were all kept.
Decision: Remove unassigned default-ignorable code points, report the seven assigned invisible letters and marks with orthographic uses without removing them, check explicit removals before the format-character branch, and keep a Mongolian selector only directly after a Mongolian letter. This stays within the unreleased policy 2.
Why: Every default-ignorable code point is now at least visible in the manifest, and no preservation rule can repeat without bound.

## 2026-10-07: Judge vendored freshness by changed paths, not commits
Context: humanizer published two CI-only commits after v1.3.0. The freshness check compared commit SHAs, so it would have warned on every push and failed the weekly run although no vendored byte would change, and re-syncing for that only churns stamps.
Decision: When upstream has moved, `scripts/check-upstream-freshness` asks the compare API which files changed since the stamp and reports a re-sync as due only if `SKILL.md` or a `references/` file changed, renames included (a truncated file list counts as changed), or if the stamp is not an ancestor of the branch. Re-syncs follow real content changes, such as the version line in humanizer v1.3.1.
Why: The guard should fire exactly when the vendored content would change, so its warnings stay worth reading.

## 2026-10-08: Keep typographic spaces only in fixed contexts (hygiene policy 3)
Context: Policy 2 normalized every no-break and ideographic space, which breaks French punctuation, thousands separators, number and unit pairs, and CJK spacing. A no-break space at an arbitrary word gap, though, looks like any other space and is a known way to hide a mark.
Decision: Keep U+00A0 and U+202F inside a number, between a number and the unit, symbol, or word after it, before French closing punctuation, and after French opening guillemets; keep U+2007 only inside a number; keep U+3000 only in a run that touches CJK text, where invisible Hangul fillers do not count. Normalize every other no-break or width-specific space, including spaces after one-letter words in Czech or Polish.
Why: These are the places where typography visibly depends on the character, and limiting preservation to them bounds how much a hidden mark could carry.

## 2026-10-08: Keep a directional mark only where removing it changes the display (hygiene policy 3)
Context: Policy 2 removed every left-to-right, right-to-left, and Arabic letter mark, which breaks mixed-direction text. Keeping every mark would leave an invisible channel, and a first rule that kept marks beside neutral characters let no-op marks survive at most word boundaries in right-to-left text.
Decision: The helper judges only marks in a paragraph with right-to-left letters, and only the first mark of each run not followed by a combining mark. The helper applies bidi rules P2, L2, N1, and N2 against the letters and the remaining marks, and removes a mark whose removal shows no change. Judging repeats in alternating directions until a pass removes nothing, capped at 8 passes. A mark sharing the stretch between two letters with a number, bracket, or tab stays, because rules W1 to W7, N0, and L1 are not modeled. Every mark in a paragraph without right-to-left letters is removed.
Why: Each removal leaves the display unchanged, so cleanup never alters how a paragraph displays apart from collapsing runs and dropping marks before combining marks. GNU FriBidi agreed on all 52,828 random mixed-direction paragraphs, and an opt-in test repeats the check. Invisible marks survive only where they do visible work or where the helper cannot rule that out.

## 2026-10-08: Always remove directional embeddings, overrides, and isolates
Context: humanizer's text-hygiene guidance preserves isolates that make mixed-direction text display correctly, and policy 3 now keeps load-bearing marks.
Decision: Policy 3 still removes U+202A to U+202E and U+2066 to U+2069 everywhere.
Why: They reorder whole spans, which is how Trojan Source attacks make text display in a different order from the one it is stored in, and judging an isolate pair needs isolating run sequences the helper does not model. A directional mark covers the common mixed-direction needs.

## 2026-10-08: Raise the documented Python minimum to 3.11
Context: Python 3.10, the documented minimum that CI tested, reaches end of life in October 2026.
Decision: SKILL.md, README, and CONTRIBUTING.md state 3.11, CI tests 3.11 and 3.14, the "Protect main" ruleset requires both jobs, and a repository test keeps every statement of the minimum the same as the CI matrix.
Why: The documented minimum should be a supported Python that CI actually tests, and the test stops the documents and CI from drifting apart again.

## 2026-10-08: Keep maintainer workflow out of the end-user adapter
Context: AGENTS.md is the file Codex, Antigravity, OpenCode, and Pi read when they run the skill, but it carried the Godpowers block, whose `npx -y godpowers@7` returns 404 because Godpowers 7 is not on public npm.
Decision: Maintainer guidance (checks, opt-in checks, syncing, releases, project state) lives in CONTRIBUTING.md and uses the locally installed Godpowers 7 CLI. AGENTS.md keeps a one-line pointer, and a repository test keeps every adapter free of Godpowers instructions so a future `godpowers init` cannot quietly add the block back.
Why: Users' tools should see only the skill's instructions, and maintainers get a command that works.
