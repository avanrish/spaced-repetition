# Speakly SRS — Spaced Repetition CLI

## Overview

A local CLI tool that syncs your learned words from Speakly and provides spaced repetition review using the SM-2 algorithm. Built for German-Polish language pair but adaptable.

## Tech Stack

- **Python CLI** with `rich` for terminal formatting
- **SQLite** via Python's built-in `sqlite3` (zero setup, single file DB)
- **requests** for API calls
- No other dependencies

## Commands

```
srs sync                  # Fetch words from Speakly, store locally
srs sync --from-file X    # Import from exported JSON file (fallback)
srs review                # Start review session (due cards)
srs stats                 # Show learning statistics
srs browse [query]        # Browse/search word bank
```

## Speakly API

### Endpoint

```
GET https://api.v4.speakly.me/api/v4/review/{language_pair_id}/all?page=1&page_size=100&order_by=true
```

- Paginated (Django REST Framework): `count`, `next`, `previous`, `results`
- Requires browser headers (Authorization + cookies/origin/etc.)
- Plain `curl` with just `Authorization: Token <token>` returns 403 — full browser headers are needed

### Response Shape (per item in `results`)

```json
{
  "id": 6236,
  "flang_id": 15,
  "position": 20,
  "pronunciation": "https://speakly-dev.s3.eu-north-1.amazonaws.com/media/....mp3",
  "pronunciation_duration": 1828,
  "phrase": "Ich spreche Englisch.",
  "content": [
    { "word": "Ich", "visible": false, "letters": 3 },
    { "word": "spreche", "visible": false, "letters": 7 },
    { "word": "Englisch", "visible": true, "letters": 8 },
    { "word": ".", "visible": true, "letters": 1 }
  ],
  "translation": {
    "words": "Mówię",
    "sentence": "Mówię po angielsku."
  },
  "is_favorite": false,
  "grammar": { "tips": { ... }, "table": { ... } },
  "words_translations": {
    "spreche": [["spreche", "mówię"]],
    "ich": [["ich", "ja"]]
  },
  "difficulty_level": "strong"
}
```

Key fields:
- `content[].visible: false` — words being learned (hidden in review)
- `content[].visible: true` — context words (already known)
- `translation.words` — short translation of hidden words
- `translation.sentence` — full sentence translation
- `words_translations` — per-word dictionary with multiple meanings

## Sync Flow

### cURL-based authentication

1. First `srs sync` — no saved headers — prompts: "Paste cURL command from browser devtools:"
2. User copies request as cURL from devtools Network tab
3. App parses cURL — extracts all headers + base URL — saves to `~/.speakly-srs/headers.json`
4. Subsequent `srs sync` — loads saved headers — fetches all pages
5. If sync gets 401/403 — "Session expired. Paste new cURL command:" — re-saves headers

### Sync logic

- Paginate through all pages (`page_size=100`)
- Upsert into `cards` table (update if exists, insert if new)
- New cards get a `reviews` entry with `next_review = today`
- Report: "Synced 150 words (12 new, 138 updated)"

### Fallback

`srs sync --from-file words.json` — import directly from a JSON file exported from devtools console.

## Data Model (SQLite)

Database stored at `~/.speakly-srs/srs.db`

### cards

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Speakly word ID |
| `position` | INTEGER | Speakly ordering (frequency rank) |
| `phrase` | TEXT | Full German sentence |
| `content_json` | TEXT | JSON array of word objects (visible/hidden) |
| `translation_words` | TEXT | Short Polish translation |
| `translation_sentence` | TEXT | Full Polish sentence |
| `words_translations_json` | TEXT | Per-word dictionary JSON |
| `pronunciation_url` | TEXT | MP3 URL |
| `difficulty_level` | TEXT | e.g. "strong" |
| `raw_json` | TEXT | Full original JSON (future-proofing) |
| `created_at` | TEXT | ISO timestamp |

### reviews

| Column | Type | Default |
|---|---|---|
| `card_id` | INTEGER FK → cards.id | |
| `ease_factor` | REAL | 2.5 |
| `interval_days` | INTEGER | 0 |
| `repetitions` | INTEGER | 0 |
| `next_review` | TEXT (ISO date) | today |
| `last_reviewed` | TEXT (ISO date) | null |

## Review Flow

### Card display

**Front (question):**
```
╭──────────────────────────────────────╮
│  Card 3/15                           │
│                                      │
│  _____ _______ Englisch.             │
│                                      │
│  Translation: Mówię                  │
│                                      │
│  [Press Enter to reveal]             │
╰──────────────────────────────────────╯
```

Hidden words (`visible: false`) are replaced with underscores matching letter count.

**Back (answer):**
```
╭──────────────────────────────────────╮
│  Card 3/15                           │
│                                      │
│  Ich spreche Englisch.               │
│                                      │
│  Mówię                               │
│  (Mówię po angielsku.)              │
│                                      │
│  spreche → mówię                     │
│  ich → ja                            │
│                                      │
│  1: Again  2: Hard  3: Good  4: Easy │
╰──────────────────────────────────────╯
```

Shows: full sentence, short translation, full sentence translation, per-word translations for hidden words.

### Session rules

- Query cards where `next_review <= today`, ordered by date (oldest first)
- Session ends when no more due cards or user quits with `q`
- Show progress: "Card X/Y"

## SM-2 Algorithm

Standard SM-2 with 4-button rating:

| Button | Quality (q) | Behavior |
|---|---|---|
| 1: Again | 0 | Reset: interval=1, repetitions=0 |
| 2: Hard | 3 | Advance but slower |
| 3: Good | 4 | Normal advance |
| 4: Easy | 5 | Fast advance |

### Interval calculation

- If q < 3: reset interval to 1, repetitions to 0
- If q >= 3:
  - repetitions 0 → interval = 1
  - repetitions 1 → interval = 6
  - repetitions 2+ → interval = interval × ease_factor
  - repetitions += 1

### Ease factor update

```
ease_factor += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
ease_factor = max(ease_factor, 1.3)
```

## Configuration

Stored at `~/.speakly-srs/config.json`:

```json
{
  "language_pair_id": 15,
  "daily_new_limit": 20,
  "daily_review_limit": 100
}
```

Headers stored at `~/.speakly-srs/headers.json` (auto-generated from cURL paste).

## Project Structure

```
spaced-repetition/
├── SPEC.md          # This file
├── main.py          # CLI entry point (argparse)
├── db.py            # SQLite schema + queries
├── sync.py          # Speakly API client + cURL parser
├── review.py        # Review session + SM-2 logic
├── stats.py         # Statistics display
└── requirements.txt # rich, requests
```

## Future Ideas (not in v1)

- Audio playback during review (pronunciation MP3s)
- Grammar tips display (parse HTML to terminal)
- Reverse cards (Polish → German)
- Export to Anki format
- Web UI frontend
- Multiple language pairs
