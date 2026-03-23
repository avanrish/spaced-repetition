# CLAUDE.md — Spaced Repetition CLI

## Project Overview

A CLI tool (`srs`) that syncs learned words from Speakly and provides spaced repetition review using the SM-2 algorithm. German-Polish language pair. Installed as an editable package via `uv`.

## Tech Stack

- Python 3.13, managed with `uv`
- `rich` for terminal UI (panels, tables, styled text)
- `requests` for HTTP
- `sqlite3` (stdlib) for persistence at `~/.speakly-srs/srs.db`
- `argparse` for CLI (no click/typer)
- macOS-specific: `afplay` for audio, `launchctl` for scheduled notifications

## Project Structure

```
srs/             # Package directory (all source code lives here)
  main.py        # CLI entry point, argparse setup, command dispatch
  db.py          # SQLite schema, queries, connection management
  sync.py        # Speakly API client, cURL parser, config
  review.py      # Review session loop, SM-2 algorithm, card rendering
  stats.py       # Statistics display
  notify.py      # macOS notification scheduling via LaunchAgents
```

Entry point: `srs.main:main` (defined in `pyproject.toml [project.scripts]`).

## Code Conventions

### Style

- No type checker or linter configured — keep code clean manually
- Use type hints for function signatures (`def foo(x: str) -> int:`)
- Use `X | None` union syntax (Python 3.10+), not `Optional[X]`
- Use `list[T]`, `dict[K, V]`, `set[T]` (lowercase builtins), not `typing.List` etc.
- Double quotes for strings
- 4-space indentation
- No docstrings on every function — only where the purpose is non-obvious
- Imports: stdlib first, then third-party, then local (`from srs.xxx import ...`)
- Lazy imports inside command functions (`cmd_sync`, `cmd_review`, etc.) to keep CLI startup fast

### Patterns

- **Module-level `console`**: Each module creates its own `console = Console()` for rich output
- **DB connection pattern**: `conn = get_connection()` → `init_db(conn)` → use → `conn.close()`. Connection uses `row_factory = sqlite3.Row` for dict-like access
- **Config/state files**: Stored in `~/.speakly-srs/` — use `os.makedirs(..., exist_ok=True)` before writes
- **JSON storage in SQLite**: Complex nested data stored as JSON text columns (`content_json`, `words_translations_json`, `raw_json`), parsed with `json.loads()` when needed
- **Error handling**: Minimal — `sys.exit(1)` for fatal errors, `pass` for best-effort operations (e.g., audio playback)
- **User interaction**: Use `input()` for prompts, not rich's `Prompt`. Check for `"q"` to quit
- **Private functions**: Prefix with `_` for module-internal helpers (see `notify.py`)

### Adding a New Command

1. Add `cmd_<name>(args)` function in `main.py` with lazy imports
2. Add subparser in `main()` with `.set_defaults(func=cmd_<name>)`
3. Implement logic in the appropriate module under `srs/`

### Adding a New Config Toggle

1. Add a subparser under `config_sub` in `main.py` with `choices=["on", "off"]`
2. Handle the new `config_action` in `cmd_config()` — read/write via `get_config()` and save to `CONFIG_PATH`
3. Display the setting's current value in the `config_action is None` branch
4. Read the setting in the consuming module via `config.get("key", False)`

### Adding a New DB Query

Add to `db.py`. Use parameterized queries (`?` placeholders). Return `list[sqlite3.Row]` or scalar values.

## Running

```sh
uv run srs <command>       # Run via uv
srs <command>              # If installed in active venv
```

## After Feature Changes

Every time a command is added, removed, or its flags/behavior change, update all three:

1. **`README.md`** — usage docs and command reference
2. **`man/srs.1`** — man page (roff format)
3. **`completions/_srs`** — zsh completions

## No Tests

There is no test suite. The project is a personal tool — manual testing only.

## Self-Maintenance

After completing each task, evaluate whether this CLAUDE.md needs updating (e.g., new patterns introduced, conventions changed, new modules added, workflow changes) and update it accordingly.
