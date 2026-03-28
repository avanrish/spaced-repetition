# srs — Speakly Spaced Repetition

A CLI tool that syncs your learned vocabulary from [Speakly](https://speakly.me) and provides spaced repetition review using the SM-2 algorithm.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv tool install -e .
```

This makes `srs` available globally. Man page and zsh completions are included — see setup below.

## Usage

### Sync words from Speakly

```bash
srs sync
```

On first run, you'll be prompted to paste a cURL command from your browser devtools:

1. Open Speakly in your browser, go to the word bank
2. Open devtools → Network tab
3. Right-click the `review/.../all` request → **Copy as cURL**
4. Paste into the prompt

Headers are saved for future syncs. If the session expires, you'll be prompted again automatically.

```bash
srs sync --full        # Re-fetch all pages (don't stop early)
srs sync --from-file words.json  # Import from exported JSON
```

### Review

```bash
srs review
```

- Cards due today are shown as flashcards with hidden words blanked out
- Press **Enter** to reveal the answer (audio plays automatically)
- Rate your recall: **1** (Again), **2** (Hard), **3** (Good), **4** (Easy)
- Press **r** to replay audio, **q** to quit
- Cards with the same due date are randomized to prevent serial order effects

When no cards are due, shows the next review date.

#### Typing mode

Opt-in to typing mode for active recall — instead of pressing Enter to reveal, you type the hidden words. Answers are shown inline with color-coded feedback (case-sensitive).

When typing mode is enabled, your rating is **auto-determined** from accuracy:
- **All correct** → Good (3)
- **Some correct** → Hard (2)
- **None correct** → Again (1)

You can override the auto-rating by pressing 1-4 instead of Enter.

```bash
srs config typing on   # Enable
srs config typing off  # Disable
```

### Stats & browsing

```bash
srs stats              # Learning statistics
srs browse             # List all cards
srs browse Freund      # Search cards
```

### Configuration

```bash
srs config                       # Show current settings
srs config typing on             # Enable typing mode
srs config typing off            # Disable typing mode
srs config skip-new-today on     # Skip cards added today in reviews
srs config skip-new-today off    # Include cards added today (default)
```

### Notifications

Opt-in to macOS notifications that remind you when reviews are due.

```bash
srs notify on                    # Enable (default: daily at 09:00)
srs notify on --at 09:00 --at 18:00  # Multiple reminder times
srs notify on --dry-run          # Fire the notification now to test
srs notify off                   # Disable
srs notify status                # Show current settings
```

Uses a macOS LaunchAgent — reminders persist across reboots with no terminal required.

## Man page & zsh completions

Run the install script to set up the man page and zsh completions:

```bash
./scripts/install-extras.sh        # Symlink (updates live as you edit)
./scripts/install-extras.sh --copy # Copy (standalone, no link to repo)
```

Add to `.zshrc` (before `source $ZSH/oh-my-zsh.sh` if using oh-my-zsh):

```bash
fpath=(~/.local/share/zsh/site-functions $fpath)
```

## Data

All data is stored in `~/.speakly-srs/`:

| File | Purpose |
|---|---|
| `srs.db` | SQLite database (cards + review state) |
| `headers.json` | Saved API headers from cURL |
| `config.json` | Optional config (language pair ID, limits, typing mode, skip-new-today) |
| `notify.json` | Notification schedule config |
| `notify.log` | Notification agent log output |
