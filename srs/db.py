import sqlite3
import json
import os
from datetime import date, datetime

DB_DIR = os.path.expanduser("~/.speakly-srs")
DB_PATH = os.path.join(DB_DIR, "srs.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY,
            position INTEGER,
            phrase TEXT NOT NULL,
            content_json TEXT NOT NULL,
            translation_words TEXT,
            translation_sentence TEXT,
            words_translations_json TEXT,
            pronunciation_url TEXT,
            difficulty_level TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            card_id INTEGER PRIMARY KEY REFERENCES cards(id),
            ease_factor REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetitions INTEGER NOT NULL DEFAULT 0,
            next_review TEXT NOT NULL,
            last_reviewed TEXT
        );
    """)
    conn.commit()


def upsert_card(conn: sqlite3.Connection, item: dict) -> bool:
    """Upsert a card from Speakly API response. Returns True if new."""
    existing = conn.execute("SELECT id FROM cards WHERE id = ?", (item["id"],)).fetchone()

    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO cards (id, position, phrase, content_json, translation_words,
                          translation_sentence, words_translations_json,
                          pronunciation_url, difficulty_level, raw_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            position=excluded.position,
            phrase=excluded.phrase,
            content_json=excluded.content_json,
            translation_words=excluded.translation_words,
            translation_sentence=excluded.translation_sentence,
            words_translations_json=excluded.words_translations_json,
            pronunciation_url=excluded.pronunciation_url,
            difficulty_level=excluded.difficulty_level,
            raw_json=excluded.raw_json
    """, (
        item["id"],
        item.get("position"),
        item["phrase"],
        json.dumps(item.get("content", []), ensure_ascii=False),
        item.get("translation", {}).get("words"),
        item.get("translation", {}).get("sentence"),
        json.dumps(item.get("words_translations", {}), ensure_ascii=False),
        item.get("pronunciation"),
        item.get("difficulty_level"),
        json.dumps(item, ensure_ascii=False),
        now,
    ))

    is_new = existing is None
    if is_new:
        conn.execute("""
            INSERT INTO reviews (card_id, next_review)
            VALUES (?, ?)
        """, (item["id"], date.today().isoformat()))

    return is_new


def get_due_cards(conn: sqlite3.Connection, limit: int = 100,
                   skip_new_today: bool = False) -> list[sqlite3.Row]:
    today = date.today().isoformat()
    if skip_new_today:
        return conn.execute("""
            SELECT c.*, r.ease_factor, r.interval_days, r.repetitions, r.next_review, r.last_reviewed
            FROM cards c
            JOIN reviews r ON c.id = r.card_id
            WHERE r.next_review <= ?
              AND DATE(c.created_at) != ?
            ORDER BY r.next_review ASC, RANDOM()
            LIMIT ?
        """, (today, today, limit)).fetchall()
    return conn.execute("""
        SELECT c.*, r.ease_factor, r.interval_days, r.repetitions, r.next_review, r.last_reviewed
        FROM cards c
        JOIN reviews r ON c.id = r.card_id
        WHERE r.next_review <= ?
        ORDER BY r.next_review ASC, RANDOM()
        LIMIT ?
    """, (today, limit)).fetchall()


def get_next_review_date(conn: sqlite3.Connection) -> str | None:
    """Return the earliest next_review date that is after today, or None."""
    row = conn.execute(
        "SELECT MIN(next_review) FROM reviews WHERE next_review > ?",
        (date.today().isoformat(),)
    ).fetchone()
    return row[0] if row else None


def update_review(conn: sqlite3.Connection, card_id: int,
                  ease_factor: float, interval_days: int,
                  repetitions: int, next_review: str):
    conn.execute("""
        UPDATE reviews
        SET ease_factor = ?, interval_days = ?, repetitions = ?,
            next_review = ?, last_reviewed = ?
        WHERE card_id = ?
    """, (ease_factor, interval_days, repetitions, next_review,
          date.today().isoformat(), card_id))
    conn.commit()


def get_stats(conn: sqlite3.Connection, skip_new_today: bool = False) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    today = date.today().isoformat()
    if skip_new_today:
        due_today = conn.execute(
            "SELECT COUNT(*) FROM reviews r JOIN cards c ON c.id = r.card_id "
            "WHERE r.next_review <= ? AND DATE(c.created_at) != ?",
            (today, today)
        ).fetchone()[0]
    else:
        due_today = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE next_review <= ?",
            (today,)
        ).fetchone()[0]
    reviewed_today = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE last_reviewed = ?",
        (date.today().isoformat(),)
    ).fetchone()[0]
    never_reviewed = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE last_reviewed IS NULL"
    ).fetchone()[0]
    mature = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE interval_days >= 21"
    ).fetchone()[0]

    upcoming = {}
    rows = conn.execute("""
        SELECT next_review, COUNT(*) as cnt FROM reviews
        WHERE next_review > ?
        GROUP BY next_review ORDER BY next_review LIMIT 7
    """, (date.today().isoformat(),)).fetchall()
    for row in rows:
        upcoming[row["next_review"]] = row["cnt"]

    return {
        "total": total,
        "due_today": due_today,
        "reviewed_today": reviewed_today,
        "never_reviewed": never_reviewed,
        "mature": mature,
        "upcoming": upcoming,
    }


def search_cards(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    pattern = f"%{query}%"
    return conn.execute("""
        SELECT c.*, r.next_review, r.interval_days, r.repetitions
        FROM cards c
        JOIN reviews r ON c.id = r.card_id
        WHERE c.phrase LIKE ? OR c.translation_words LIKE ? OR c.translation_sentence LIKE ?
        ORDER BY c.position ASC
        LIMIT 50
    """, (pattern, pattern, pattern)).fetchall()
