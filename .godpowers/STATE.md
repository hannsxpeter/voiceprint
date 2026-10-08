---
godpowers: 7
project: voiceprint
stage: review
verify: "sh scripts/check"
updated: 2026-10-08
---
# voiceprint

## Goal
Give writers and editors who use AI coding tools one honest pass over a draft: diagnose it, clean and rewrite it once, and report what is left. Success means the vendored skills stay current with their upstreams, the hygiene helper never alters valid text, and every document matches what the code and the vendored skills actually do.

## Now
- The three remaining low risks are fixed on branch `claude/fix-low-risks` (PR hannsxpeter/voiceprint#11), unreleased (the changelog's `[Unreleased]` section): hygiene policy 3 keeps typographic spaces and the directional marks that change the display, Python 3.11 is the documented and tested minimum, and maintainer guidance moved from `AGENTS.md` to the new `CONTRIBUTING.md`. After five review and security rounds, the mark rule applies the bidi algorithm itself, resolves bracket pairs exactly, and charges every check to its budget; checked against ICU and GNU FriBidi, every kept mark changes the display and crafted inputs keep no hidden mark.
- v1.5.2 is the latest release (PR hannsxpeter/voiceprint#9, merged as 527b6e5), vendoring humanizer 1.3.1 and authenticity-check 1.2.3. `main` is protected by the "Protect main" ruleset.

## Next
- Merge the pull request once the maintainer approves moving the ruleset's required check from the 3.10 job to the 3.11 job; CI passes on Python 3.11 and 3.14.
- Cut 1.6.0 when the maintainer asks.
- Re-sync `vendor/` whenever upstream-freshness reports a re-sync as due.

## Risks
- [x] low: hygiene normalizes every no-break space and removes every directional mark, including ones that locale typography or mixed right-to-left text needs, scripts/text_hygiene.py (fixed 2026-10-08: hygiene policy 3 keeps no-break spaces in numbers, units, and French punctuation, ideographic spaces beside CJK text, and a directional mark only where removing it would change the display; see DECISIONS.md)
- [x] low: AGENTS.md doubles as the end-user adapter but carries the maintainer Godpowers block, whose `npx -y godpowers@7` returns 404 on public npm (latest published is 6.3.0), AGENTS.md (fixed 2026-10-08: the guidance moved to CONTRIBUTING.md with the local Godpowers 7 CLI, AGENTS.md keeps a one-line pointer, and a test keeps every adapter free of Godpowers instructions)
- [x] low: `main` has no branch protection or required status checks, so CI cannot block a merge, GitHub repository settings (fixed 2026-10-07: ruleset "Protect main" mirrors humanizer's, blocking deletion and force pushes and requiring both vendor-sync-check jobs on an up-to-date branch)
- [x] low: Python 3.10, the documented minimum that CI tests, reaches end of life in October 2026, SKILL.md and .github/workflows/vendor-sync-check.yml (fixed 2026-10-08: 3.11 is the documented minimum, CI tests 3.11 and 3.14, and a test keeps the stated minimum the same in SKILL.md, README, CONTRIBUTING.md, and CI)
