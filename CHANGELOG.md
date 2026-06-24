# Changelog

## 0.1.0
- Initial release as a Claude Code plugin.
- `agent-teams-scaffold` skill: generates Agent Teams scaffolding for a target repo
  (security-review subagent, `settings.json` teams flag, `CLAUDE.md`, spawn prompts,
  fish/tmux launcher), then tailors the files to the codebase.
- Generator tolerates both nested and flat asset layouts.
