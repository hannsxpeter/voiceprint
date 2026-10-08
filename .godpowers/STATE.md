---
godpowers: 7
project: voiceprint
stage: ship
verify: "sh scripts/check"
updated: 2026-10-07
---
# voiceprint

## Goal
Give writers and editors who use AI coding tools one honest pass over a draft: diagnose it, clean and rewrite it once, and report what is left. Success means the vendored skills stay current with their upstreams, the hygiene helper never alters valid text, and every document matches what the code and the vendored skills actually do.

## Now
- v1.5.0 passed the Godpowers ship gate on `claude/v1.5.0-maintenance`: vendored skills re-synced to humanizer 1.3.1 and authenticity-check 1.2.1, hygiene policy 2 stops emoji damage and reports every default-ignorable code point, upstream hygiene and provenance output folded into the six-section contract, the security pass's findings fixed, freshness made content-aware, Godpowers 6 and Pillars leftovers removed. See PLAN.md.

## Next
- Open the pull request, merge it once CI passes on Python 3.10 and 3.14, then tag v1.5.0, publish the GitHub release, and refresh the repository description and topics.
- Decide the open question in PLAN.md about no-break spaces and directional marks.
- Re-sync `vendor/` whenever upstream-freshness reports a re-sync as due.

## Risks
- [ ] low: hygiene normalizes every no-break space and removes every directional mark, including ones that locale typography or mixed right-to-left text needs, scripts/text_hygiene.py
- [ ] low: AGENTS.md doubles as the end-user adapter but carries the maintainer Godpowers block, whose `npx -y godpowers@7` returns 404 on public npm (latest published is 6.3.0), AGENTS.md
- [ ] low: `main` has no branch protection or required status checks, so CI cannot block a merge, GitHub repository settings
- [ ] low: Python 3.10, the documented minimum that CI tests, reaches end of life in October 2026, SKILL.md and .github/workflows/vendor-sync-check.yml
