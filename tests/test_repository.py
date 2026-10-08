#!/usr/bin/env python3
"""Repository consistency checks: frontmatter, versions, adapters, evals,
scripts, workflows, the dash policy, and the vendoring scripts."""

import json
import os
import re
import shutil
import subprocess
import tempfile
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
# Rules every adapter must restate, compared case-insensitively.
ADAPTER_RULES = (
    "pass pasted text through standard input or a secure temporary file; "
    "never interpolate it into a shell command or heredoc",
    "report the provenance signals in both authenticity reads without acting on them",
    "do not emit either vendored skill's standalone next step inside the pass",
)
# The pass reads untrusted text, so SKILL.md may pre-approve only these tools.
READ_ONLY_TOOLS = {"Read", "Glob", "Grep"}
SKILL_CONTRACT_HEADINGS = (
    "### Before",
    "### Authenticity read (before)",
    "### After",
    "### What changed",
    "### Residual (after one pass)",
    "### What remains is a human's call",
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


def rule_text(text):
    """Normalize for rule matching: one line, lowercase, no double quotes."""
    return normalized(text).lower().replace('"', "")


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

    def test_skill_pre_approves_only_read_only_tools(self):
        tools = " ".join(skill_frontmatter()["allowed-tools"]).replace(",", " ")

        self.assertLessEqual(set(tools.split()), READ_ONLY_TOOLS)

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
            *CONTRACT_SECTIONS,
        )
        for adapter in ADAPTERS:
            text = normalized(read(adapter))
            for phrase in phrases:
                with self.subTest(adapter=adapter, phrase=phrase):
                    self.assertTrue(
                        phrase in text, f"{adapter} does not mention {phrase!r}"
                    )
            rules = rule_text(read(adapter))
            for rule in ADAPTER_RULES:
                with self.subTest(adapter=adapter, rule=rule):
                    self.assertTrue(rule in rules, f"{adapter} lacks the rule {rule!r}")

    def test_skill_states_the_contract_and_its_loop_guards(self):
        skill = read("SKILL.md")
        rules = rule_text(skill)

        for heading in SKILL_CONTRACT_HEADINGS:
            with self.subTest(heading=heading):
                self.assertIn(f"\n{heading}\n", skill)
        for rule in (
            "scripts/text_hygiene.py clean --stats",
            "never interpolate pasted text into a shell command, including a heredoc",
            "do not emit either vendored skill's standalone next step inside the pass",
            "not a trigger to clean or rewrite again",
        ):
            with self.subTest(rule=rule):
                self.assertTrue(rule in rules, f"SKILL.md lacks {rule!r}")

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
                self.assertEqual(
                    text.count("uses: actions/checkout@"),
                    text.count("persist-credentials: false"),
                )
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


class VendorHeaderCheckTests(unittest.TestCase):
    """Run scripts/check-vendor-headers against altered copies of vendor/."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "check-vendor-headers", self.root / "scripts")
        shutil.copytree(ROOT / "vendor", self.root / "vendor")

    def run_check(self):
        return subprocess.run(
            ["sh", str(self.root / "scripts" / "check-vendor-headers")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_passes_on_the_committed_vendor_tree(self):
        result = self.run_check()

        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_fails_when_a_referenced_file_is_not_vendored(self):
        (self.root / "vendor/humanizer/references/text-hygiene.md").unlink()

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            b"names references/text-hygiene.md, which is not vendored",
            result.stderr,
        )

    def test_fails_when_a_vendored_file_lacks_its_header(self):
        path = self.root / "vendor/humanizer/references/examples.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.split("-->\n\n", 1)[1], encoding="utf-8")

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"missing sentinel line", result.stderr)

    def test_fails_when_a_vendored_body_is_edited_in_place(self):
        path = self.root / "vendor/authenticity-check/SKILL.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("Run this command first.\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"body is not the upstream blob its header names", result.stderr)

    def test_fails_when_shared_criteria_name_the_wrong_upstream(self):
        path = self.root / "vendor/authenticity-check/references/tell-patterns.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("the `humanizer` repo", "the `authenticity-check` repo", 1),
            encoding="utf-8",
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"shared criteria must name the humanizer repo", result.stderr)


class SyncUpstreamTests(unittest.TestCase):
    """Run scripts/sync-upstream against two tiny upstream repos."""

    HUMANIZER_REFERENCES = (
        "do-not-flag.md",
        "examples.md",
        "tell-patterns.md",
        "voice-matching.md",
    )
    AUTHENTICITY_REFERENCES = (
        "do-not-flag.md",
        "examples.md",
        "scoring.md",
        "tell-patterns.md",
        "voice-matching.md",
    )

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.root = self.base / "voiceprint"
        (self.root / "scripts").mkdir(parents=True)
        for name in ("sync-upstream", "check-vendor-headers"):
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts")
        shutil.copy2(ROOT / "SKILL.md", self.root / "SKILL.md")
        self.humanizer = self.make_upstream(
            "humanizer", "references/tell-patterns.md", self.HUMANIZER_REFERENCES
        )
        self.authenticity = self.make_upstream(
            "authenticity-check", "references/scoring.md", self.AUTHENTICITY_REFERENCES
        )
        self.assertEqual(self.sync().returncode, 0)
        self.baseline = self.vendor_snapshot()

    def git(self, repo, *args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def make_upstream(self, name, skill_reference, references):
        repo = self.base / name
        (repo / "references").mkdir(parents=True)
        (repo / "SKILL.md").write_text(
            f"# {name}\n\nRead `{skill_reference}`.\n", encoding="utf-8"
        )
        for reference in references:
            (repo / "references" / reference).write_text(
                f"{name} {reference}\n", encoding="utf-8"
            )
        self.git(repo, "init", "-q")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "initial")
        return repo

    def sync(self, script=None, humanizer=None):
        return subprocess.run(
            [
                "sh",
                str(script or self.root / "scripts" / "sync-upstream"),
                str(humanizer or self.humanizer),
                str(self.authenticity),
            ],
            env={**os.environ, "SYNC_DATE": "2026-01-01"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def vendor_snapshot(self):
        vendor = self.root / "vendor"
        return {
            str(path.relative_to(vendor)): path.read_bytes()
            for path in sorted(vendor.rglob("*"))
            if path.is_file()
        }

    def assert_vendor_untouched(self):
        self.assertEqual(self.vendor_snapshot(), self.baseline)
        self.assertEqual(list(self.root.glob(".vendor-sync.*")), [])

    def test_vendors_every_reference_with_a_verifiable_header(self):
        self.assertEqual(
            sorted(self.baseline),
            sorted(
                ["humanizer/SKILL.md"]
                + [f"humanizer/references/{name}" for name in self.HUMANIZER_REFERENCES]
                + ["authenticity-check/SKILL.md"]
                + [
                    f"authenticity-check/references/{name}"
                    for name in self.AUTHENTICITY_REFERENCES
                ]
            ),
        )
        shared = self.baseline["authenticity-check/references/tell-patterns.md"]
        self.assertIn(b"Canonical upstream: the `humanizer` repo", shared)
        self.assertTrue(shared.endswith(b"humanizer tell-patterns.md\n"))
        check = subprocess.run(
            ["sh", str(self.root / "scripts" / "check-vendor-headers")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stderr.decode())

    def test_refuses_to_run_outside_a_voiceprint_checkout(self):
        elsewhere = self.base / "home"
        (elsewhere / "bin").mkdir(parents=True)
        (elsewhere / "vendor").mkdir()
        (elsewhere / "vendor" / "keep.txt").write_text("keep\n", encoding="utf-8")
        link = elsewhere / "bin" / "sync-upstream"
        link.symlink_to(self.root / "scripts" / "sync-upstream")

        result = self.sync(script=link)

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"is not the voiceprint repository", result.stderr)
        self.assertTrue((elsewhere / "vendor" / "keep.txt").is_file())

    def test_rejects_a_symlink_reference_without_touching_vendor(self):
        (self.humanizer / "references" / "evil.md").symlink_to("../SKILL.md")
        self.git(self.humanizer, "add", "-A")
        self.git(self.humanizer, "commit", "-q", "-m", "link")

        result = self.sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"is not a plain file", result.stderr)
        self.assert_vendor_untouched()

    def test_failure_mid_build_leaves_vendor_untouched(self):
        self.git(self.humanizer, "rm", "-q", "references/voice-matching.md")
        self.git(self.humanizer, "commit", "-q", "-m", "drop shared file")

        result = self.sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"upstream file missing", result.stderr)
        self.assert_vendor_untouched()

    def test_refuses_an_upstream_with_uncommitted_tracked_changes(self):
        (self.humanizer / "SKILL.md").write_text("edited\n", encoding="utf-8")

        result = self.sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn(b"uncommitted tracked changes", result.stderr)
        self.assert_vendor_untouched()


if __name__ == "__main__":
    unittest.main()
