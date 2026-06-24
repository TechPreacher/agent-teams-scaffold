#!/usr/bin/env python3
"""Tests for the agent-teams-scaffold generator.

Pure-stdlib (`unittest`) so they run anywhere `python3` does, with no pip install. They are also
discovered by `pytest` if you have it. Run from the repo root:

    python3 -m unittest discover -s tests -v
    # or, if pytest is installed:
    pytest -v

The suite codifies the invariants in CLAUDE.md: deterministic stack detection (manifest beats
shell, shell beats Unknown, fish stays Unknown), non-destructive writes (settings merge, CLAUDE.md
snippet-not-clobber), the read-only reviewer, the shell-agnostic launcher, and that no `{{KEY}}`
placeholder survives rendering.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make the generator importable. It lives next to the templates it renders.
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "skills" / "agent-teams-scaffold" / "scripts"
SCAFFOLD_PY = SCRIPT_DIR / "scaffold.py"
sys.path.insert(0, str(SCRIPT_DIR))

import scaffold  # noqa: E402


def write(repo: Path, rel: str, content: str = "") -> Path:
    """Create a file (with parents) inside a temp repo."""
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


class TempRepoTest(unittest.TestCase):
    """Base class giving each test a throwaway repo directory."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "demo-repo"
        self.repo.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------- helpers / pure fns


class HelperFunctionTests(unittest.TestCase):
    def test_slug_normalizes(self):
        self.assertEqual(scaffold.slug("My Repo!"), "my-repo")
        self.assertEqual(scaffold.slug("a__b  c"), "a-b-c")
        self.assertEqual(scaffold.slug("Trailing--"), "trailing")

    def test_slug_empty_falls_back_to_team(self):
        self.assertEqual(scaffold.slug("!!!"), "team")
        self.assertEqual(scaffold.slug(""), "team")

    def test_assets_dir_resolved(self):
        # _find_assets must have located the template dir at import time.
        self.assertTrue((scaffold.ASSETS / "security-reviewer.md.tmpl").exists())


# --------------------------------------------------------------------------- stack detection


class StackDetectionTests(TempRepoTest):
    def test_javascript_npm(self):
        write(self.repo, "package.json", "{}")
        langs, build, test, lint = scaffold.detect_stack(self.repo)
        self.assertIn("JavaScript/TypeScript", langs)
        self.assertEqual(test, "npm test")
        self.assertEqual(lint, "npm run lint")

    def test_pnpm_lockfile_wins_over_package_json(self):
        # More specific lockfile listed first in MANIFESTS must take priority.
        write(self.repo, "package.json", "{}")
        write(self.repo, "pnpm-lock.yaml", "")
        langs, _, test, _ = scaffold.detect_stack(self.repo)
        self.assertTrue(langs.startswith("JavaScript/TypeScript (pnpm)"))
        self.assertEqual(test, "pnpm test")

    def test_python_pyproject(self):
        write(self.repo, "pyproject.toml", "[project]\nname='x'\n")
        langs, _, test, lint = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Python")
        self.assertEqual(test, "pytest")
        self.assertEqual(lint, "ruff check .")

    def test_rust(self):
        write(self.repo, "Cargo.toml", "")
        langs, build, test, _ = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Rust")
        self.assertEqual(build, "cargo build")
        self.assertEqual(test, "cargo test")

    def test_go(self):
        write(self.repo, "go.mod", "module x\n")
        langs, build, test, _ = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Go")
        self.assertEqual(test, "go test ./...")

    def test_csharp_csproj_top_level(self):
        write(self.repo, "App.csproj", "<Project/>")
        langs, build, test, _ = scaffold.detect_stack(self.repo)
        self.assertIn("C#/.NET", langs)
        self.assertEqual(build, "dotnet build")

    def test_csharp_csproj_nested(self):
        # Common .NET layout: project files under src/<Project>/ — must be detected (rglob).
        write(self.repo, "src/App/App.csproj", "<Project/>")
        langs, build, _, _ = scaffold.detect_stack(self.repo)
        self.assertIn("C#/.NET", langs)
        self.assertEqual(build, "dotnet build")

    def test_csharp_csproj_in_build_output_ignored(self):
        # A .csproj only under bin/ or obj/ (build output) must NOT trigger detection.
        write(self.repo, "obj/App.csproj", "<Project/>")
        write(self.repo, "bin/Debug/Other.csproj", "<Project/>")
        langs, _, _, _ = scaffold.detect_stack(self.repo)
        self.assertTrue(langs.startswith("Unknown"))

    def test_manifest_beats_helper_shell_script(self):
        # A Python repo that also ships a helper .sh must stay Python (manifest wins).
        write(self.repo, "pyproject.toml", "[project]\nname='x'\n")
        write(self.repo, "helper.sh", "#!/bin/bash\necho hi\n")
        langs, _, test, _ = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Python")
        self.assertEqual(test, "pytest")

    def test_shell_fallback_on_sh_file(self):
        write(self.repo, "run.sh", "#!/bin/bash\necho hi\n")
        langs, build, test, lint = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Shell (bash)")
        self.assertEqual(test, "bash -n run.sh")
        self.assertEqual(lint, "shellcheck run.sh")

    def test_shell_fallback_extensionless_shebang(self):
        p = write(self.repo, "deploy", "#!/usr/bin/env bash\necho hi\n")
        scaffold.make_executable(p)
        langs, _, test, _ = scaffold.detect_stack(self.repo)
        self.assertEqual(langs, "Shell (bash)")
        self.assertEqual(test, "bash -n deploy")

    def test_fish_only_stays_unknown(self):
        # fish is deliberately excluded from shell detection.
        write(self.repo, "build.fish", "#!/usr/bin/env fish\necho hi\n")
        langs, build, test, lint = scaffold.detect_stack(self.repo)
        self.assertTrue(langs.startswith("Unknown"))
        self.assertEqual(build, "TODO: build")

    def test_license_not_treated_as_shell_script(self):
        # An extensionless LICENSE must never be picked up as a shell entrypoint.
        write(self.repo, "LICENSE", "MIT License ...\n")
        langs, _, _, _ = scaffold.detect_stack(self.repo)
        self.assertTrue(langs.startswith("Unknown"))

    def test_empty_repo_unknown(self):
        langs, build, test, lint = scaffold.detect_stack(self.repo)
        self.assertTrue(langs.startswith("Unknown"))
        self.assertEqual((build, test, lint), ("TODO: build", "TODO: test", "TODO: lint"))


# --------------------------------------------------------------------------- module listing


class ModuleListTests(TempRepoTest):
    def test_lists_visible_dirs_ignores_noise(self):
        (self.repo / "src").mkdir()
        (self.repo / "lib").mkdir()
        (self.repo / "node_modules").mkdir()  # in IGNORE_DIRS
        (self.repo / ".git").mkdir()          # dotdir
        out = scaffold.module_list(self.repo)
        self.assertIn("`lib/`", out)
        self.assertIn("`src/`", out)
        self.assertNotIn("node_modules", out)
        self.assertNotIn(".git", out)

    def test_no_dirs_emits_todo(self):
        out = scaffold.module_list(self.repo)
        self.assertIn("TODO", out)


# --------------------------------------------------------------------------- settings merge


class SettingsTests(TempRepoTest):
    def _claude(self) -> Path:
        d = self.repo / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def test_creates_settings_with_flag(self):
        self._claude()
        path = scaffold.write_settings(self.repo)
        self.assertEqual(path.name, "settings.json")
        data = json.loads(path.read_text())
        self.assertEqual(data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")

    def test_merges_into_existing_settings(self):
        c = self._claude()
        existing = {"env": {"FOO": "bar"}, "permissions": {"allow": ["Bash"]}}
        (c / "settings.json").write_text(json.dumps(existing))
        scaffold.write_settings(self.repo)
        data = json.loads((c / "settings.json").read_text())
        # Preserves untouched keys and the pre-existing env var.
        self.assertEqual(data["permissions"], {"allow": ["Bash"]})
        self.assertEqual(data["env"]["FOO"], "bar")
        self.assertEqual(data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")

    def test_invalid_json_falls_back_to_local(self):
        c = self._claude()
        (c / "settings.json").write_text("{ not valid json ")
        path = scaffold.write_settings(self.repo)
        # Original left untouched; flag written to settings.local.json instead.
        self.assertEqual(path.name, "settings.local.json")
        self.assertEqual((c / "settings.json").read_text(), "{ not valid json ")
        data = json.loads(path.read_text())
        self.assertEqual(data["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")


# --------------------------------------------------------------------------- rendering


class RenderTests(unittest.TestCase):
    def test_no_unresolved_placeholders_when_keys_match(self):
        out = scaffold.render("CLAUDE.md.tmpl", {
            "REPO_NAME": "x", "DATE": "2026-01-01", "LANGUAGES": "Python",
            "BUILD_CMD": "b", "TEST_CMD": "t", "LINT_CMD": "l", "MODULE_LIST": "- m",
        })
        self.assertNotIn("{{", out)
        self.assertNotIn("}}", out)

    def test_reviewer_template_renders_clean(self):
        out = scaffold.render("security-reviewer.md.tmpl", {
            "REPO_NAME": "x", "LANGUAGES": "Go", "SCOPE_BLOCK": "- auth",
        })
        self.assertNotIn("{{", out)


# --------------------------------------------------------------------------- end-to-end via main()


def run_main(repo: Path, *extra: str) -> int:
    argv = ["scaffold.py", "--repo", str(repo), *extra]
    old = sys.argv
    sys.argv = argv
    try:
        return scaffold.main()
    finally:
        sys.argv = old


class EndToEndTests(TempRepoTest):
    def setUp(self):
        super().setUp()
        write(self.repo, "go.mod", "module demo\n")
        (self.repo / "cmd").mkdir()

    def test_generates_all_files(self):
        rc = run_main(self.repo)
        self.assertEqual(rc, 0)
        for rel in [
            ".claude/agents/security-reviewer.md",
            ".claude/settings.json",
            ".claude/TEAM_PROMPTS.md",
            ".claude/launch-team.sh",
            "CLAUDE.md",
        ]:
            self.assertTrue((self.repo / rel).exists(), f"missing {rel}")

    def test_no_placeholders_leak_into_outputs(self):
        run_main(self.repo)
        for rel in [
            ".claude/agents/security-reviewer.md",
            ".claude/TEAM_PROMPTS.md",
            ".claude/launch-team.sh",
            "CLAUDE.md",
        ]:
            text = (self.repo / rel).read_text()
            self.assertNotIn("{{", text, f"unresolved placeholder in {rel}")

    def test_reviewer_is_read_only(self):
        run_main(self.repo)
        text = (self.repo / ".claude/agents/security-reviewer.md").read_text()
        # The tools line must grant only read-only tools — no Write/Edit.
        tools_line = next(l for l in text.splitlines() if l.startswith("tools:"))
        self.assertEqual(tools_line, "tools: Read, Grep, Glob, Bash")
        for forbidden in ("Write", "Edit", "NotebookEdit"):
            self.assertNotIn(forbidden, tools_line)

    def test_launcher_is_executable_and_shell_agnostic(self):
        run_main(self.repo)
        launcher = self.repo / ".claude/launch-team.sh"
        self.assertTrue(launcher.stat().st_mode & stat.S_IXUSR)
        text = launcher.read_text()
        # Env var injected via tmux -e (shell-agnostic), not embedded shell syntax.
        self.assertIn("-e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1", text)

    def test_claude_md_not_clobbered_without_force(self):
        original = "# Existing project memory\nkeep me\n"
        (self.repo / "CLAUDE.md").write_text(original)
        run_main(self.repo)
        # Root CLAUDE.md untouched; scaffold lands in a snippet for manual merge.
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), original)
        snippet = self.repo / ".claude/CLAUDE.agent-teams.snippet.md"
        self.assertTrue(snippet.exists())
        self.assertIn("Project Context", snippet.read_text())

    def test_force_overwrites_claude_md(self):
        (self.repo / "CLAUDE.md").write_text("# old\n")
        run_main(self.repo, "--force")
        self.assertIn("Project Context", (self.repo / "CLAUDE.md").read_text())
        self.assertFalse((self.repo / ".claude/CLAUDE.agent-teams.snippet.md").exists())

    def test_idempotent_rerun_preserves_user_settings(self):
        # First run, then a user edits settings, then a second run must merge not clobber.
        run_main(self.repo)
        sp = self.repo / ".claude/settings.json"
        data = json.loads(sp.read_text())
        data.setdefault("permissions", {})["allow"] = ["Bash(go test:*)"]
        sp.write_text(json.dumps(data))
        run_main(self.repo)
        data2 = json.loads(sp.read_text())
        self.assertEqual(data2["permissions"]["allow"], ["Bash(go test:*)"])
        self.assertEqual(data2["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")

    def test_scopes_select_subset(self):
        run_main(self.repo, "--scopes", "secrets,auth")
        reviewer = (self.repo / ".claude/agents/security-reviewer.md").read_text()
        self.assertIn("Secrets & configuration", reviewer)
        self.assertIn("Authentication & authorization", reviewer)
        self.assertNotIn("Dependencies & supply chain", reviewer)

    def test_invalid_scopes_fall_back_to_default(self):
        run_main(self.repo, "--scopes", "bogus,nonsense")
        reviewer = (self.repo / ".claude/agents/security-reviewer.md").read_text()
        # Falls back to auth,input,supplychain.
        self.assertIn("Authentication & authorization", reviewer)
        self.assertIn("Dependencies & supply chain", reviewer)

    def test_nonexistent_repo_returns_error(self):
        rc = run_main(self.tmp / "does-not-exist")
        self.assertEqual(rc, 2)


# --------------------------------------------------------------------------- launcher syntax (bash)


@unittest.skipUnless(shutil.which("bash"), "bash not installed")
class LauncherSyntaxTests(TempRepoTest):
    def test_rendered_launcher_passes_bash_syntax_check(self):
        write(self.repo, "go.mod", "module demo\n")
        run_main(self.repo)
        launcher = self.repo / ".claude/launch-team.sh"
        # The .tmpl still has {{...}}; only the rendered file is valid bash.
        proc = subprocess.run(["bash", "-n", str(launcher)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
