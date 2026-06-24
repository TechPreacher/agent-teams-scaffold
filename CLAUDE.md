# agent-teams-scaffold — Development Context

This repo **is** a Claude Code plugin that scaffolds *other* repos for Agent Teams. Don't confuse
the two CLAUDE.md files: this one guides development **of the plugin**; the one the plugin emits
(`assets/CLAUDE.md.tmpl`) is for the **target** repos it scaffolds.

## What this is

A self-referential single-plugin marketplace. The plugin ships one skill, `agent-teams-scaffold`,
whose job is: given a target repo, lay down `.claude/` scaffolding for Claude Code Agent Teams
(a read-only security-review subagent, a `settings.json` with the experimental teams flag, a
`CLAUDE.md`, paste-ready team spawn prompts, and a fish/tmux launcher), then tailor those files to
the target's actual stack.

Core design split, and the single most important thing to preserve:

- **`scripts/scaffold.py` is deterministic.** It writes safe defaults and `TODO` markers. It must
  never need a model to run, and must never destroy user data.
- **`SKILL.md` carries the judgment.** After the script runs, the skill instructs Claude to read
  the target repo and replace the `TODO`s (real module boundaries, correct build/test/lint,
  stack-specific security focus). Boilerplate by script; tailoring by model.

## Layout

```
.claude-plugin/
  plugin.json          # plugin manifest (name is the only required field)
  marketplace.json     # catalog "techpreacher"; references this plugin via source "."
skills/agent-teams-scaffold/
  SKILL.md             # skill instructions + frontmatter (triggering lives in `description`)
  scripts/scaffold.py  # the generator
  assets/*.tmpl        # templates rendered into the TARGET repo
README.md  CHANGELOG.md  LICENSE  .gitignore
```

Hard structural rules (violating these makes Claude Code silently fail to load components):

- **Only the two manifests live in `.claude-plugin/`.** Components (the `skills/` tree) sit at the
  plugin root, never inside `.claude-plugin/`.
- In `plugin.json`, `repository` must be a **string URL**, not an object.
- The skill is namespaced `agent-teams-scaffold:agent-teams-scaffold` once installed.

## Generator internals (`scripts/scaffold.py`)

- `_find_assets()` resolves the template dir tolerantly (`../assets`, `./assets`, then the script's
  own dir). This exists because the repo history includes an accidental flatten; keep it tolerant.
- `detect_stack()` checks `MANIFESTS` (package.json, pyproject.toml, Cargo.toml, go.mod, etc.) and
  `*.csproj`, then falls back to `_detect_shell()`, then `Unknown`. **Shell detection is a fallback
  only** — a manifest always wins, so a Python repo with a helper `.sh` stays Python.
- `_detect_shell()` matches top-level `*.sh` or an extensionless top-level file whose shebang names
  a POSIX-family shell. **fish is deliberately excluded** (`shellcheck`/`bash -n` don't apply).
- `write_settings()` **merges** into an existing `.claude/settings.json` and falls back to
  `settings.local.json` if the existing file is invalid JSON. It never clobbers.
- The root `CLAUDE.md` of a target is **never overwritten** unless `--force`; otherwise the content
  goes to `.claude/CLAUDE.agent-teams.snippet.md` for the user to merge.
- `render()` is dumb `{{KEY}}` string substitution. **Placeholder names in a template and in the
  `render(...)` mapping must match exactly** — a typo silently leaves `{{KEY}}` in the output.

## Invariants — do not regress these

- The generator is **non-destructive**: merge settings, snippet-not-clobber CLAUDE.md, write TODO
  markers rather than guesses.
- The emitted security-reviewer is **read-only**: tools limited to Read/Grep/Glob/Bash, and Bash is
  for non-mutating analysis only. Don't add write tools to the reviewer template.
- The emitted launcher uses tmux's `-e` flag to inject the env var rather than embedding
  shell-specific syntax — keep it shell-agnostic.
- `SKILL.md` resolves the generator via `$CLAUDE_PLUGIN_ROOT/skills/agent-teams-scaffold/scripts/
  scaffold.py` when installed as a plugin (CWD is the user's target repo, not the skill dir).

## Facts baked into the templates and SKILL.md — re-verify on change

These describe Claude Code's Agent Teams feature and **can go stale**. If you touch them, confirm
against `https://code.claude.com/docs/en/agent-teams` and update `assets/*.tmpl` and the SKILL.md
"facts" section together:

- Agent Teams is experimental, off by default, enabled by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`;
  available since Claude Code **v2.1.32**.
- Lead session coordinates; teammates have their own context windows and message each other
  directly (the distinction from subagents, which only report back to the parent).
- Split-pane UX needs **tmux 3.2+** or iTerm2; in-process mode works anywhere.
- Teams cost ~**3–7×** the tokens of a single session; for **4+** teammates, use git worktrees.

## Verifying changes

The generator has an automated suite — `tests/test_scaffold.py`, pure-stdlib `unittest` (no pip
install needed). It runs in CI (`.github/workflows/ci.yml`) on every push/PR. Run it locally before
committing a generator change:

```bash
python3 -m unittest discover -s tests -v   # or: pytest -v
```

The suite already covers stack detection (JS, pnpm-beats-package.json, Python, a Python repo with a
helper `.sh` that must stay Python, a fish-only repo that must stay `Unknown`, shell fallback,
`LICENSE` not mistaken for a script), non-destructive writes (settings merge, invalid-JSON →
`settings.local.json`, CLAUDE.md snippet-not-clobber, `--force`, idempotent re-run), the read-only
reviewer tools line, scope selection/fallback, and that no `{{KEY}}` survives rendering. One test
shells out to `fish -n` on the rendered launcher and auto-skips when `fish` is absent.

**When you add a fixture case or invariant, add a test for it** — don't fall back to manual checks.
CI also runs these manifest/structure checks, which are worth running locally too:

- Syntax: `python3 -m py_compile skills/agent-teams-scaffold/scripts/scaffold.py`
- Manifests parse: `python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); json.load(open('.claude-plugin/marketplace.json'))"`
- Plugin structure: `claude plugin validate .` (add `--strict` to treat warnings as errors) — local
  only; the `claude` CLI is not available in CI.

## Extending

- **New language stack**: add a row to `MANIFESTS` (filename, label, build, test, lint). Order
  matters — more specific lockfiles before generic ones.
- **New security scope**: add an entry to `SCOPES`; it flows automatically into the reviewer's
  scope menu and the `TEAM_PROMPTS.md` teammate roster.
- **New generated file**: add a `.tmpl` to `assets/`, render it in `main()`, and document it in
  SKILL.md's "What gets generated" table.

## Release process

Versions live in **three** places and must move together: `plugin.json`, `marketplace.json` (both
the catalog `metadata.version` and the plugin entry `version`), and a new `CHANGELOG.md` entry. The
plugin cache is keyed by version (`cache/techpreacher/agent-teams-scaffold/<version>/`), so after
pushing a bump, refresh installs with `claude plugin marketplace update techpreacher` then
`claude plugin update agent-teams-scaffold@techpreacher`. Tag releases and pin fleet installs to a
tag or SHA for reproducibility.

## History worth knowing

- The repo was once committed flat (no `scripts/`/`assets/`), then restored; `_find_assets()` is
  the defense against that recurring.
- During plugin conversion, `git mv scripts <dest>/scripts` into an already-existing `scripts/`
  produced a double-nested `scripts/scripts/`, and a stale root `SKILL.md` lingered — both later
  removed. When restructuring, verify `git ls-files` shows the canonical tree before committing.

