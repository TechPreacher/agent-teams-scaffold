# agent-teams-scaffold

[![CI](https://github.com/TechPreacher/agent-teams-scaffold/actions/workflows/ci.yml/badge.svg)](https://github.com/TechPreacher/agent-teams-scaffold/actions/workflows/ci.yml)

A reusable [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) **skill** that turns
any repository into one ready for **Agent Teams** (multi-agent parallel work). Point it at a repo
folder and it generates the `.claude/` scaffolding — a read-only security-review subagent, a
`settings.json` with the experimental teams flag, a `CLAUDE.md` project-context file, ready-to-paste
team spawn prompts, and a bash/tmux launcher — then has Claude tailor those files to the actual
codebase.

## What it generates

| File | Purpose |
|------|---------|
| `.claude/agents/security-reviewer.md` | Read-only reviewer subagent, assigned one scope per spawn |
| `.claude/settings.json` | Merged with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| `.claude/TEAM_PROMPTS.md` | Ready-to-paste security-swarm spawn prompts |
| `.claude/launch-team.sh` | bash/zsh + tmux launcher (executable) |
| `CLAUDE.md` | Project-context scaffold (or a mergeable snippet if one already exists) |

It is **non-destructive**: existing `settings.json` is merged (not overwritten), and an existing
root `CLAUDE.md` is preserved with a snippet written alongside for you to merge.

## Install

### As a plugin (recommended)

```bash
claude plugin marketplace add TechPreacher/agent-teams-scaffold
claude plugin install agent-teams-scaffold@techpreacher
```

The repo is a self-referential marketplace: `.claude-plugin/marketplace.json` (catalog named
`techpreacher`) and `.claude-plugin/plugin.json` (the plugin) both live at the root, and the skill
ships under `skills/agent-teams-scaffold/`. The skill is namespaced as
`agent-teams-scaffold:agent-teams-scaffold`. Pin to a tag or commit for reproducible installs.

### As a standalone skill (no plugin system)

```bash
git clone https://github.com/TechPreacher/agent-teams-scaffold /tmp/ats
cp -r /tmp/ats/skills/agent-teams-scaffold ~/.claude/skills/agent-teams-scaffold
```

> Skills are consulted by their `description`; you can always just ask Claude to "use the
> agent-teams-scaffold skill on `<path>`", or run the generator directly (below).

## Usage

In Claude Code:

> Use the agent-teams-scaffold skill on `~/code/my-service`.

Claude runs the generator, then reads the repo and fills in the real module boundaries,
build/test/lint commands, and stack-specific security focus.

Or run the generator directly (skips the tailoring step):

```bash
python3 skills/agent-teams-scaffold/scripts/scaffold.py --repo ~/code/my-service \
  --scopes auth,input,supplychain,secrets \
  --team-name my-service
```

Then start a team:

```bash
~/code/my-service/.claude/launch-team.sh
```

Paste a prompt from `.claude/TEAM_PROMPTS.md` to the lead, then press `Shift+Tab` to lock the lead
into coordination-only (delegate) mode.

## Tests

The generator has a pure-`unittest` suite (no pip install needed) covering stack detection,
non-destructive writes, the read-only reviewer, and placeholder rendering. From the repo root:

```bash
python3 -m unittest discover -s tests -v
```

If you have `pytest`, it discovers the same tests:

```bash
pytest -v
```

The suite verifies the invariants in [CLAUDE.md](CLAUDE.md): a manifest beats a helper shell
script (a Python repo with a `.sh` stays Python), shell beats Unknown, a fish-only repo stays
Unknown, `settings.json` is merged (and falls back to `settings.local.json` on invalid JSON), an
existing root `CLAUDE.md` is preserved as a snippet, and no `{{KEY}}` placeholder survives
rendering. One test shells out to `bash -n` to syntax-check the rendered launcher; it is skipped
automatically when `bash` is not installed.

## Caveats

- **Agent Teams is experimental** and off by default. Requires Claude Code **v2.1.32+**. There is
  no session resume for in-process teammates — closing the terminal loses them.
- Teams cost roughly **3–7× the tokens** of a single session. Plan in plan mode first (cheap), then
  hand the approved plan to the team. For 4+ teammates, use **git worktrees** to avoid file
  collisions.
- Split-pane UX needs **tmux 3.2+** or iTerm2; otherwise teammates run in-process in one terminal.

## Repo layout

```
agent-teams-scaffold/                 # marketplace + plugin root
├── .claude-plugin/
│   ├── plugin.json                   # plugin manifest
│   └── marketplace.json              # self-referential catalog (source ".")
├── skills/
│   └── agent-teams-scaffold/         # the skill (a plugin component)
│       ├── SKILL.md
│       ├── scripts/scaffold.py       # deterministic generator
│       └── assets/                   # templates rendered into the target repo
│           ├── security-reviewer.md.tmpl
│           ├── CLAUDE.md.tmpl
│           ├── TEAM_PROMPTS.md.tmpl
│           └── launch-team.sh.tmpl
├── tests/
│   └── test_scaffold.py             # unittest suite for the generator
├── CHANGELOG.md
├── README.md
└── LICENSE
```

> Only the manifests live in `.claude-plugin/`. Components (the skill) sit at the plugin root —
> putting them inside `.claude-plugin/` makes Claude Code fail to discover them.

## License

MIT — see [LICENSE](LICENSE).
