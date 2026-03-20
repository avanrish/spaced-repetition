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

When no cards are due, shows the next review date.

### Stats & browsing

```bash
srs stats              # Learning statistics
srs browse             # List all cards
srs browse Freund      # Search cards
```

## Man page

```bash
mkdir -p ~/.local/share/man/man1
cp man/srs.1 ~/.local/share/man/man1/
man srs
```

## Zsh completions

```bash
mkdir -p ~/.local/share/zsh/site-functions
cp completions/_srs ~/.local/share/zsh/site-functions/
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
| `config.json` | Optional config (language pair ID, limits) |
