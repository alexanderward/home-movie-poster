# Codex

## Repository integration

- VS Code recommends the official extension with identifier `OpenAI.chatgpt`.
- Codex automatically discovers the root [AGENTS.md](../../AGENTS.md).
- Add nested `AGENTS.md` files only when a directory needs genuinely different, scoped instructions.
- Project-local Codex configuration belongs in `.codex/config.toml` only when the project needs settings beyond the shared defaults.

## Local setup

1. Install the recommended extension.
2. Sign in through the extension.
3. Trust the repository only after reviewing its instructions and configuration.

Do not commit authentication data or copy personal Codex configuration into this repository.

