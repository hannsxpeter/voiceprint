---
godpowers: 7
project: voiceprint
stage: done
verify: "sh scripts/check"
updated: 2026-11-23
---
# voiceprint

## Goal
Give writers and editors who use AI coding tools one honest pass over a draft: diagnose it, clean and rewrite it once, and report what is left. Success means the vendored skills stay current with their upstreams, the hygiene helper never alters valid text, and every document matches what the code and the vendored skills actually do.

## Now
- v1.7.0 ships the product surface: gamified README and SVG assets, `docs/hygiene.md` for the deep Unicode reference, and the public npm package `@hxp-tools/voiceprint` with an `npx` installer for Claude Code, Codex, Cursor, and Windsurf.
- Hygiene policy remains version 3 from v1.6.0. Vendored skills remain humanizer 1.3.1 and authenticity-check 1.2.3. `main` stays protected by the "Protect main" ruleset requiring both vendor-sync-check jobs.

## Next
- Re-sync `vendor/` whenever upstream-freshness reports a re-sync as due.

## Risks
- [x] low: hygiene normalizes every no-break space and removes every directional mark, including ones that locale typography or mixed right-to-left text needs, scripts/text_hygiene.py (fixed 2026-10-08: hygiene policy 3 keeps no-break spaces in numbers, units, and French punctuation, ideographic spaces beside CJK text, and a directional mark only where removing it would change the display; see DECISIONS.md)
- [x] low: AGENTS.md doubles as the end-user adapter but carries the maintainer Godpowers block, whose `npx -y godpowers@7` returns 404 on public npm (latest published is 6.3.0), AGENTS.md (fixed 2026-10-08: the guidance moved to CONTRIBUTING.md with the local Godpowers 7 CLI, AGENTS.md keeps a one-line pointer, and a test keeps every adapter free of Godpowers instructions)
- [x] low: `main` has no branch protection or required status checks, so CI cannot block a merge, GitHub repository settings (fixed 2026-10-07: ruleset "Protect main" mirrors humanizer's, blocking deletion and force pushes and requiring both vendor-sync-check jobs on an up-to-date branch)
- [x] low: Python 3.10, the documented minimum that CI tests, reaches end of life in October 2026, SKILL.md and .github/workflows/vendor-sync-check.yml (fixed 2026-10-08: 3.11 is the documented minimum, CI tests 3.11 and 3.14, and a test keeps the stated minimum the same in SKILL.md, README, CONTRIBUTING.md, and CI)
