---
godpowers: 7
project: voiceprint
stage: done
verify: "sh scripts/check"
updated: 2026-10-07
---
# voiceprint

## Goal
Give writers and editors who use AI coding tools one honest pass over a draft: diagnose it, clean and rewrite it once, and report what is left. Success means the vendored skills stay current with their upstreams, the hygiene helper never alters valid text, and every document matches what the code and the vendored skills actually do.

## Now
- v1.5.1 is released: PR hannsxpeter/voiceprint#7 merged as 3062890, tag v1.5.1 and its GitHub release are published. It re-syncs authenticity-check to its v1.2.2 release (hannsxpeter/authenticity-check#1), so voiceprint vendors humanizer 1.3.1 and authenticity-check 1.2.2 and both skills use the same pattern names. v1.5.0 (PR hannsxpeter/voiceprint#4) shipped the larger maintenance release; `main` is protected by the "Protect main" ruleset.

## Next
- Decide the open question in PLAN.md about no-break spaces and directional marks.
- Re-sync `vendor/` whenever upstream-freshness reports a re-sync as due.
- Consider the remaining low risks below.

## Risks
- [ ] low: hygiene normalizes every no-break space and removes every directional mark, including ones that locale typography or mixed right-to-left text needs, scripts/text_hygiene.py
- [ ] low: AGENTS.md doubles as the end-user adapter but carries the maintainer Godpowers block, whose `npx -y godpowers@7` returns 404 on public npm (latest published is 6.3.0), AGENTS.md
- [x] low: `main` has no branch protection or required status checks, so CI cannot block a merge, GitHub repository settings (fixed 2026-10-07: ruleset "Protect main" mirrors humanizer's, blocking deletion and force pushes and requiring both vendor-sync-check jobs on an up-to-date branch)
- [ ] low: Python 3.10, the documented minimum that CI tests, reaches end of life in October 2026, SKILL.md and .github/workflows/vendor-sync-check.yml
