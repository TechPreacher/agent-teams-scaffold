---
name: agent-teams-scaffold
description: >-
  Generate Claude Code Agent Teams scaffolding for a repository: a read-only security-review
  subagent, a settings.json with the experimental teams flag, a CLAUDE.md project-context file,
  ready-to-paste team spawn prompts, and a bash/tmux launcher. Use this whenever the user wants to
  set up multi-agent / Agent Teams work in a repo, "scaffold .claude", create a security review
  team or swarm, prepare a repo for parallel agents, or points the skill at a folder containing a
  repo — even if they don't say the words "Agent Teams". Re-runnable across any repo.
---

# Agent Teams Scaffold

Turns a plain repository into one that's ready for Claude Code Agent Teams (Level 7 multi-agent
work). A deterministic generator lays down the files; then you tailor them to the actual codebase.

## Inputs

- **Target repo**: a path the user gives you, or the current working directory if they just say
  "this repo". Resolve it before running.
- **Scopes** (optional): which security review scopes to wire up. Default
  `auth,input,supplychain`; full set is `auth,input,supplychain,secrets`.

## Workflow

### 1. Locate the generator

The generator is `scripts/scaffold.py` inside this skill's own directory. Resolve its absolute path
based on how the skill is loaded:

- **Installed as a plugin**: `"$CLAUDE_PLUGIN_ROOT/skills/agent-teams-scaffold/scripts/scaffold.py"`
- **Cloned standalone** into a skills directory: `scripts/scaffold.py` relative to this SKILL.md.

Do not assume the current working directory is the skill directory — it is usually the user's
target repo. Always invoke the script by an absolute path.

### 2. Run the generator

```bash
python3 <resolved-path-to-scaffold.py> --repo <TARGET_REPO> [--scopes auth,input,supplychain,secrets] [--team-name NAME] [--force]
```

It auto-detects the stack (build/test/lint), writes safe defaults and `TODO` markers, and is
non-destructive: it **merges** into an existing `.claude/settings.json` rather than overwriting,
and if a root `CLAUDE.md` already exists it writes `.claude/CLAUDE.agent-teams.snippet.md` for the
user to merge instead of clobbering. Read the generator's printed summary.

### 3. Tailor the generated files (this is the part only you can do)

The generator can only guess. Now actually read the repo and replace the `TODO` markers:

- **CLAUDE.md** — fill in real **module boundaries** (what each top-level dir owns, so teammates
  don't edit the same files), correct the **build/test/lint** commands if detection was wrong or
  incomplete, and add project **conventions** a fresh teammate would otherwise get wrong.
- **security-reviewer.md** — if the stack implies specific risk areas (e.g. an HTTP API → focus
  authn middleware and request validation; a published package → focus the supply-chain scope),
  note them so each spawned reviewer knows where to look.
- **TEAM_PROMPTS.md** — adjust the teammate roster if the repo warrants different or additional
  scopes.

Keep edits surgical. Don't remove the Agent Teams notes or the launch instructions.

### 4. Report

Tell the user exactly what was written (paths), what you tailored, and how to start:

- Launch: `.claude/launch-team.sh` (or `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1; claude`).
- Then paste a prompt from `.claude/TEAM_PROMPTS.md` to the lead and press `Shift+Tab` to lock the
  lead into coordination-only mode.

## What gets generated

| File | Purpose |
|------|---------|
| `.claude/agents/security-reviewer.md` | Read-only reviewer subagent; assigned one scope per spawn |
| `.claude/settings.json` | Merged with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| `.claude/TEAM_PROMPTS.md` | Ready-to-paste security-swarm spawn prompts |
| `.claude/launch-team.sh` | bash/zsh + tmux launcher (executable) |
| `CLAUDE.md` | Project-context scaffold (or a snippet if one already exists) |

## Facts baked into the templates (keep accurate)

- Agent Teams is **experimental**, off by default, enabled by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
  in `settings.json` or the environment; available since Claude Code **v2.1.32**.
- One session is the **team lead**; teammates run in their own context windows and message each
  other directly (the difference from subagents, which only report back to the parent).
- Split-pane UX needs **tmux 3.2+** or iTerm2; in-process mode works anywhere.
- Teams cost roughly **3–7× the tokens** of a single session; for 4+ teammates use **git
  worktrees** to avoid file collisions.

If Claude Code's teams interface changes, update `assets/*.tmpl` and this section together.

## Requirements

- Python 3.8+ (generator)
- bash or zsh + tmux 3.2+ (only for the launcher; everything else is shell-agnostic)
- Claude Code v2.1.32+ (to actually run teams)
