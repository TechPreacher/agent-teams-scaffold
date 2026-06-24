# Changelog

## Unreleased
- Add a stdlib `unittest` test suite for the generator plus GitHub Actions CI (no runtime change).

## 0.1.1
- Generator now detects shell/bash projects (top-level `*.sh` or a POSIX-shell shebang) and
  baselines `bash -n` / `shellcheck` instead of returning `Unknown`. fish scripts are excluded.

## 0.1.0
- Initial release as a Claude Code plugin.
- `agent-teams-scaffold` skill: generates Agent Teams scaffolding for a target repo
  (security-review subagent, `settings.json` teams flag, `CLAUDE.md`, spawn prompts,
  fish/tmux launcher), then tailors the files to the codebase.
- Generator tolerates both nested and flat asset layouts.
