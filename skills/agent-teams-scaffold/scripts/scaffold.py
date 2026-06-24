#!/usr/bin/env python3
"""
agent-teams-scaffold — generate Claude Code Agent Teams scaffolding for a repository.

Lays down (into the target repo):
  .claude/agents/security-reviewer.md   a read-only, scope-assignable reviewer subagent
  .claude/settings.json                 merged with CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
  .claude/TEAM_PROMPTS.md               ready-to-paste team spawn prompts
  .claude/launch-team.sh                bash/zsh + tmux launcher (chmod +x)
  CLAUDE.md                             project-context scaffold (or a snippet if one exists)

The script writes safe defaults and TODO markers. The skill's SKILL.md instructs Claude to read
the repo afterward and replace the TODOs (real module boundaries, correct build/test/lint, scopes
tailored to the actual stack).
"""
from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from datetime import date
from pathlib import Path

def _find_assets() -> Path:
    """Locate the template directory, tolerating both nested and flat layouts."""
    here = Path(__file__).resolve().parent
    candidates = [here.parent / "assets", here / "assets", here]
    for c in candidates:
        if (c / "security-reviewer.md.tmpl").exists():
            return c
    raise SystemExit(
        "error: could not find template assets (*.tmpl). Looked in:\n  "
        + "\n  ".join(str(c) for c in candidates)
    )


ASSETS = _find_assets()

# (manifest filename, language label, build, test, lint)
MANIFESTS = [
    ("pnpm-lock.yaml", "JavaScript/TypeScript (pnpm)", "pnpm build", "pnpm test", "pnpm lint"),
    ("package.json", "JavaScript/TypeScript", "npm run build", "npm test", "npm run lint"),
    ("pyproject.toml", "Python", "python -m build", "pytest", "ruff check ."),
    ("requirements.txt", "Python", "TODO: build", "pytest", "ruff check ."),
    ("Cargo.toml", "Rust", "cargo build", "cargo test", "cargo clippy --all-targets"),
    ("go.mod", "Go", "go build ./...", "go test ./...", "golangci-lint run"),
    ("pom.xml", "Java (Maven)", "mvn -q package", "mvn -q test", "mvn -q checkstyle:check"),
    ("build.gradle.kts", "Kotlin (Gradle)", "./gradlew build", "./gradlew test", "./gradlew check"),
    ("build.gradle", "Java/Kotlin (Gradle)", "./gradlew build", "./gradlew test", "./gradlew check"),
    ("Gemfile", "Ruby", "TODO: build", "bundle exec rspec", "bundle exec rubocop"),
]

SCOPES = {
    "auth": "Authentication & authorization — token issuance/validation, session lifecycle, "
            "access-control checks, and privilege-escalation paths.",
    "input": "Input validation & injection — untrusted input handling, SQL/command/template "
             "injection, unsafe deserialization, and path traversal.",
    "supplychain": "Dependencies & supply chain — lockfile integrity, known-vulnerable "
                   "dependencies, post-install scripts, version pinning, and provenance.",
    "secrets": "Secrets & configuration — hardcoded credentials, secrets committed to history, "
               "insecure defaults, and logging of sensitive data.",
}

IGNORE_DIRS = {
    ".git", "node_modules", "target", "dist", "build", "out", "__pycache__",
    ".venv", "venv", ".idea", ".vscode", ".claude", ".mypy_cache", ".pytest_cache",
}


SHEBANG_RE = re.compile(r"#!.*\b(bash|sh|dash|ksh|zsh)\b")


def _detect_shell(repo: Path):
    """Fallback for shell/bash projects, which have no manifest or package manager.

    Detects top-level `*.sh` files, or extensionless top-level files whose shebang names a
    POSIX-family shell (bash/sh/dash/ksh/zsh; fish is intentionally excluded — shellcheck and
    `bash -n` don't apply to it).
    """
    scripts = sorted(repo.glob("*.sh"))
    for p in sorted(repo.iterdir()):
        if p.is_file() and p.suffix == "" and p.name != "LICENSE":
            try:
                first = p.open("rb").readline(256).decode("utf-8", "ignore").splitlines()[:1]
            except OSError:
                continue
            if first and SHEBANG_RE.match(first[0]):
                scripts.append(p)
    if not scripts:
        return None
    primary = scripts[0].name
    return ("Shell (bash)", "none — interpreted", f"bash -n {primary}", f"shellcheck {primary}")


def _find_csproj(repo: Path) -> bool:
    """True if the repo contains a .NET project file anywhere, ignoring build output.

    .NET solutions commonly nest `*.csproj` under `src/<Project>/`, so a top-level glob misses
    them. rglob walks the whole tree, so skip the standard noise dirs (IGNORE_DIRS) plus .NET's
    `bin/`/`obj/` build output, which can contain generated/copied project files.
    """
    skip = IGNORE_DIRS | {"bin", "obj"}
    for p in repo.rglob("*.csproj"):
        if any(part in skip for part in p.relative_to(repo).parts):
            continue
        return True
    return False


def detect_stack(repo: Path):
    found = []
    for fname, lang, b, t, l in MANIFESTS:
        if (repo / fname).exists():
            found.append((lang, b, t, l))
    if _find_csproj(repo):
        found.append(("C#/.NET", "dotnet build", "dotnet test", "dotnet format --verify-no-changes"))
    if found:
        langs = ", ".join(dict.fromkeys(f[0] for f in found))  # de-dup, keep order
        _, b, t, l = found[0]
        return (langs, b, t, l)
    # No language manifest — fall back to shell detection before giving up.
    shell = _detect_shell(repo)
    if shell:
        return shell
    return ("Unknown — fill in manually", "TODO: build", "TODO: test", "TODO: lint")


def module_list(repo: Path) -> str:
    dirs = sorted(
        p.name for p in repo.iterdir()
        if p.is_dir() and p.name not in IGNORE_DIRS and not p.name.startswith(".")
    )
    if not dirs:
        return "- TODO: list the top-level module directories and what each owns"
    return "\n".join(f"- `{d}/` — TODO: describe what this owns" for d in dirs)


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "team"


def render(tmpl_name: str, mapping: dict) -> str:
    text = (ASSETS / tmpl_name).read_text()
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def make_executable(p: Path) -> None:
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_settings(repo: Path) -> Path:
    path = repo / ".claude" / "settings.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"  ! {path} is not valid JSON; leaving it and writing settings.local.json instead")
            path = repo / ".claude" / "settings.local.json"
            data = {}
    env = data.get("env") or {}
    env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
    data["env"] = env
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Claude Code Agent Teams scaffolding.")
    ap.add_argument("--repo", required=True, help="path to the target repository")
    ap.add_argument("--team-name", help="tmux session / team name (default: repo slug)")
    ap.add_argument("--scopes", default="auth,input,supplychain",
                    help="comma list from: auth,input,supplychain,secrets")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing root CLAUDE.md instead of writing a snippet")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2

    repo_name = repo.name
    team_name = slug(args.team_name or repo_name)
    langs, build_cmd, test_cmd, lint_cmd = detect_stack(repo)

    selected = [s.strip() for s in args.scopes.split(",") if s.strip() in SCOPES]
    if not selected:
        selected = ["auth", "input", "supplychain"]

    scope_block = "\n".join(f"- **{s}**: {SCOPES[s]}" for s in selected)
    teammate_block = "\n".join(f"> - `{s}-reviewer`: {SCOPES[s]}" for s in selected)

    (repo / ".claude" / "agents").mkdir(parents=True, exist_ok=True)

    written = []

    # security-reviewer subagent
    p = repo / ".claude" / "agents" / "security-reviewer.md"
    p.write_text(render("security-reviewer.md.tmpl", {
        "REPO_NAME": repo_name, "LANGUAGES": langs, "SCOPE_BLOCK": scope_block,
    }))
    written.append(p)

    # team prompts
    p = repo / ".claude" / "TEAM_PROMPTS.md"
    p.write_text(render("TEAM_PROMPTS.md.tmpl", {
        "REPO_NAME": repo_name, "TEAMMATE_BLOCK": teammate_block,
        "TEST_CMD": test_cmd, "LINT_CMD": lint_cmd,
    }))
    written.append(p)

    # launcher
    p = repo / ".claude" / "launch-team.sh"
    p.write_text(render("launch-team.sh.tmpl", {
        "REPO_NAME": repo_name, "TEAM_NAME": team_name,
    }))
    make_executable(p)
    written.append(p)

    # settings.json (merge)
    written.append(write_settings(repo))

    # CLAUDE.md (never clobber unless --force)
    claude_md = render("CLAUDE.md.tmpl", {
        "REPO_NAME": repo_name, "DATE": date.today().isoformat(), "LANGUAGES": langs,
        "BUILD_CMD": build_cmd, "TEST_CMD": test_cmd, "LINT_CMD": lint_cmd,
        "MODULE_LIST": module_list(repo),
    })
    root_claude = repo / "CLAUDE.md"
    if root_claude.exists() and not args.force:
        snippet = repo / ".claude" / "CLAUDE.agent-teams.snippet.md"
        snippet.write_text(claude_md)
        written.append(snippet)
        claude_note = (f"CLAUDE.md already exists — wrote a snippet to {snippet.relative_to(repo)} "
                       f"for you to merge (or re-run with --force to overwrite).")
    else:
        root_claude.write_text(claude_md)
        written.append(root_claude)
        claude_note = "Wrote CLAUDE.md."

    print(f"Scaffolded Agent Teams config for '{repo_name}'  (stack: {langs})")
    print(f"Team/tmux session name: {team_name}")
    print(f"Security scopes: {', '.join(selected)}\n")
    for w in written:
        print(f"  + {w.relative_to(repo)}")
    print(f"\n{claude_note}")
    print("\nNext: have Claude read the repo and replace the TODO markers (module boundaries, "
          "build/test/lint commands, stack-specific security focus). Then launch with "
          ".claude/launch-team.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
