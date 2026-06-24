# agent-teams-scaffold

A reusable [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) **skill** that turns
any repository into one ready for **Agent Teams** (multi-agent parallel work). Point it at a repo
folder and it generates the `.claude/` scaffolding — a read-only security-review subagent, a
`settings.json` with the experimental teams flag, a `CLAUDE.md` project-context file, ready-to-paste
team spawn prompts, and a fish/tmux launcher — then has Claude tailor those files to the actual
codebase.

## What it generates

| File | Purpose |
|------|---------|
| `.claude/agents/security-reviewer.md` | Read-only reviewer subagent, assigned one scope per spawn |
| `.claude/settings.json` | Merged with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| `.claude/TEAM_PROMPTS.md` | Ready-to-paste security-swarm spawn prompts |
| `.claude/launch-team.fish` | fish/tmux launcher (executable) |
| `CLAUDE.md` | Project-context scaffold (or a mergeable snippet if one already exists) |

It is **non-destructive**: existing `settings.json` is merged (not overwritten), and an existing
root `CLAUDE.md` is preserved with a snippet written alongside for you to merge.

## Install

As a personal skill (available in every session):

```bash
git clone https://github.com/<you>/agent-teams-scaffold ~/.claude/skills/agent-teams-scaffold
```

Or per-project:

```bash
git clone https://github.com/<you>/agent-teams-scaffold .claude/skills/agent-teams-scaffold
```

> Skills are consulted by their `description`. Depending on your Claude Code version you may also
> be able to invoke a skill explicitly by name (e.g. an invocable flag in the frontmatter) — check
> your version's skills docs. You can always just ask Claude to "use the agent-teams-scaffold skill
> on `<path>`", or run the generator directly (below).

## Usage

In Claude Code:

> Use the agent-teams-scaffold skill on `~/code/my-service`.

Claude runs the generator, then reads the repo and fills in the real module boundaries,
build/test/lint commands, and stack-specific security focus.

Or run the generator directly (skips the tailoring step):

```bash
python3 scripts/scaffold.py --repo ~/code/my-service \
  --scopes auth,input,supplychain,secrets \
  --team-name my-service
```

Then start a team:

```fish
~/code/my-service/.claude/launch-team.fish
```

Paste a prompt from `.claude/TEAM_PROMPTS.md` to the lead, then press `Shift+Tab` to lock the lead
into coordination-only (delegate) mode.

## Caveats

- **Agent Teams is experimental** and off by default. Requires Claude Code **v2.1.32+**. There is
  no session resume for in-process teammates — closing the terminal loses them.
- Teams cost roughly **3–7× the tokens** of a single session. Plan in plan mode first (cheap), then
  hand the approved plan to the team. For 4+ teammates, use **git worktrees** to avoid file
  collisions.
- Split-pane UX needs **tmux 3.2+** or iTerm2; otherwise teammates run in-process in one terminal.

## Repo layout

```
agent-teams-scaffold/
├── SKILL.md              # skill instructions + frontmatter
├── scripts/scaffold.py   # deterministic generator
└── assets/               # templates rendered into the target repo
    ├── security-reviewer.md.tmpl
    ├── CLAUDE.md.tmpl
    ├── TEAM_PROMPTS.md.tmpl
    └── launch-team.fish.tmpl
```

## License

MIT — see [LICENSE](LICENSE).
