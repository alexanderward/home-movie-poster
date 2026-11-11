# Claude Code

## Repository integration

- VS Code recommends the official extension with identifier `Anthropic.claude-code`.
- Claude Code reads the root [CLAUDE.md](../../CLAUDE.md), which routes to the canonical [AGENTS.md](../../AGENTS.md) index.
- Shared Claude Code settings may be added under `.claude/` when the project has a concrete need.
- Personal overrides belong in `.claude/settings.local.json`, which is ignored by Git.

## Local setup

1. Install the recommended extension.
2. Sign in through the extension or Claude Code CLI.
3. Review the repository instructions before approving commands or edits.

Do not commit authentication data or machine-specific permission rules.

