#!/usr/bin/env python3
"""Repository consistency checks: frontmatter, versions, adapters, evals,
scripts, workflows, and the dash policy."""

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (
    "AGENTS.md",
    "GEMINI.md",
    ".cursor/rules/voiceprint.mdc",
    ".github/copilot-instructions.md",
)
CONTRACT_SECTIONS = (
    "Before",
    "Authenticity read (before)",
    "After",
    "What changed",
    "Residual",
    "What remains is a human's call",
)
SHELL_SCRIPTS = (
    "scripts/check",
    "scripts/check-upstream-freshness",
    "scripts/check-vendor-headers",
    "scripts/sync-upstream",
)
WORKFLOWS = (
    ".github/workflows/upstream-freshness.yml",
    ".github/workflows/vendor-sync-check.yml",
)
# The frontmatter keys the Agent Skills spec and the skill validator accept.
ALLOWED_FRONTMATTER_KEYS = {
    "allowed-tools",
    "compatibility",
    "description",
    "license",
    "metadata",
    "name",
}
DISALLOWED_DASHES = {chr(0x2013): "U+2013", chr(0x2014): "U+2014"}


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def normalized(text):
    """Collapse whitespace so a phrase wrapped across lines still matches."""
    return " ".join(text.split())


def skill_frontmatter():
    """Return each top-level SKILL.md frontmatter key with its value lines."""
    match = re.match(r"---\n(.*?)\n---\n", read("SKILL.md"), re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md has no frontmatter block")
    fields = {}
    key = None
    for line in match.group(1).splitlines():
        top_level = re.match(r"([A-Za-z][A-Za-z0-9-]*):\s*(.*)$", line)
        if top_level:
            key, value = top_level.groups()
            fields[key] = [] if value in ("", ">", ">-", "|", "|-") else [value]
        elif key is not None and line.startswith(" "):
            fields[key].append(line.strip())
    return fields


def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise unittest.SkipTest("listing tracked files needs a git checkout")
    return [name for name in result.stdout.decode("utf-8").split("\0") if name]


class RepositoryConsistencyTests(unittest.TestCase):
    def test_skill_frontmatter_follows_the_agent_skills_spec(self):
        fields = skill_frontmatter()

        self.assertLessEqual(set(fields), ALLOWED_FRONTMATTER_KEYS)
        self.assertEqual(fields["name"], ["voiceprint"])
        description = " ".join(fields["description"])
        self.assertLessEqual(len(description), 1024)
        self.assertNotRegex(description, "[<>]")
        self.assertLessEqual(len(" ".join(fields.get("compatibility", []))), 500)

    def test_version_matches_across_skill_readme_and_changelog(self):
        metadata = dict(
            line.split(": ", 1) for line in skill_frontmatter()["metadata"]
        )
        version = metadata["version"]
        released = re.findall(
            r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.MULTILINE
        )

        self.assertIn(f"badge/version-{version}-", read("README.md"))
        self.assertEqual(released[0], version)

    def test_adapters_route_to_the_same_contract(self):
        phrases = (
            "SKILL.md",
            "vendor/authenticity-check/SKILL.md",
            "vendor/humanizer/SKILL.md",
            "scripts/text_hygiene.py clean --stats",
            "Next step",
            *CONTRACT_SECTIONS,
        )
        for adapter in ADAPTERS:
            text = normalized(read(adapter))
            for phrase in phrases:
                with self.subTest(adapter=adapter, phrase=phrase):
                    self.assertTrue(
                        phrase in text, f"{adapter} does not mention {phrase!r}"
                    )

    def test_evals_are_well_formed(self):
        evals = json.loads(read("evals/evals.json"))
        ids = [case["id"] for case in evals["evals"]]

        self.assertEqual(evals["skill_name"], "voiceprint")
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        for case in evals["evals"]:
            with self.subTest(eval_id=case["id"]):
                self.assertTrue(case["prompt"])
                self.assertTrue(case["expected_output"])
                self.assertTrue(case["expectations"])
                for path in case["files"]:
                    self.assertTrue((ROOT / path).is_file(), path)

    def test_shell_scripts_parse(self):
        for script in SHELL_SCRIPTS:
            with self.subTest(script=script):
                result = subprocess.run(
                    ["sh", "-n", str(ROOT / script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_workflows_use_read_only_permissions_and_pinned_actions(self):
        for workflow in WORKFLOWS:
            text = read(workflow)
            actions = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)", text, re.MULTILINE)
            with self.subTest(workflow=workflow):
                self.assertIn("permissions:\n  contents: read\n", text)
                self.assertTrue(actions)
            for action in actions:
                with self.subTest(workflow=workflow, action=action):
                    self.assertRegex(action, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")

    def test_tracked_text_has_no_disallowed_dashes(self):
        failures = []
        for name in tracked_files():
            path = ROOT / name
            if name.startswith("vendor/") or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                for character, label in DISALLOWED_DASHES.items():
                    if character in line:
                        failures.append(f"{name}:{line_number}: contains {label}")

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
