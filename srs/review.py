import json
import os
import subprocess
import tempfile
from datetime import date, timedelta

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from srs.db import get_connection, init_db, get_due_cards, get_next_review_date, update_review
from srs.sync import get_config

console = Console()

_audio_cache: dict[str, str] = {}
_current_audio_proc: subprocess.Popen | None = None


def play_audio(url: str | None):
    """Download and play an MP3 URL using macOS afplay. Non-blocking."""
    global _current_audio_proc
    if not url:
        return

    # Kill previous playback if still running
    if _current_audio_proc and _current_audio_proc.poll() is None:
        _current_audio_proc.terminate()

    try:
        # Cache downloaded files for the session
        if url not in _audio_cache:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(resp.content)
            tmp.close()
            _audio_cache[url] = tmp.name

        _current_audio_proc = subprocess.Popen(
            ["afplay", _audio_cache[url]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Audio is best-effort, don't break review


def sm2(quality: int, ease_factor: float, interval: int, repetitions: int) -> tuple[float, int, int]:
    """
    SM-2 algorithm. Returns (new_ease, new_interval, new_repetitions).
    Quality mapping: 1=Again(0), 2=Hard(3), 3=Good(4), 4=Easy(5)
    """
    q_map = {1: 0, 2: 3, 3: 4, 4: 5}
    q = q_map.get(quality, 0)

    # Update ease factor
    new_ease = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ease = max(new_ease, 1.3)

    if q < 3:
        # Failed — reset
        new_interval = 1
        new_reps = 0
    else:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * new_ease)
        new_reps = repetitions + 1

    return new_ease, new_interval, new_reps


def build_question(card) -> Text:
    """Build the question text with hidden words replaced by underscores."""
    content = json.loads(card["content_json"])
    text = Text()
    for i, item in enumerate(content):
        if i > 0 and item["word"] not in (".", "!", "?", ",", ";", ":"):
            text.append(" ")
        if item["visible"]:
            text.append(item["word"])
        else:
            text.append("_" * item["letters"], style="bold yellow")
    return text


def build_answer(card) -> Text:
    """Build the answer text with revealed words highlighted."""
    content = json.loads(card["content_json"])
    text = Text()
    for i, item in enumerate(content):
        if i > 0 and item["word"] not in (".", "!", "?", ",", ";", ":"):
            text.append(" ")
        if item["visible"]:
            text.append(item["word"])
        else:
            text.append(item["word"], style="bold green")
    return text


def get_hidden_words(card) -> list[str]:
    """Return the list of hidden words in order."""
    content = json.loads(card["content_json"])
    return [item["word"] for item in content if not item["visible"]]


def build_word_hints(card) -> list[str]:
    """Build per-word translation hints for hidden words."""
    content = json.loads(card["content_json"])
    translations = json.loads(card["words_translations_json"]) if card["words_translations_json"] else {}

    hidden_words = [item["word"].lower() for item in content if not item["visible"]]
    hints = []

    for word in hidden_words:
        if word in translations:
            pairs = translations[word]
            meaning = ", ".join(p[1] for p in pairs)
            hints.append(f"  {pairs[0][0]} → {meaning}")

    return hints


def build_typed_result(card, typed_words: list[str]) -> Text:
    """Build the sentence with typed words filled in, color-coded green/red."""
    content = json.loads(card["content_json"])
    text = Text()
    hidden_idx = 0
    for i, item in enumerate(content):
        if i > 0 and item["word"] not in (".", "!", "?", ",", ";", ":"):
            text.append(" ")
        if item["visible"]:
            text.append(item["word"])
        else:
            expected = item["word"]
            typed = typed_words[hidden_idx] if hidden_idx < len(typed_words) else ""
            if typed == expected:
                text.append(typed, style="bold green")
            else:
                text.append(f"{typed}→{expected}", style="bold red")
            hidden_idx += 1
    return text


def prompt_typing(card) -> bool:
    """Prompt user to type hidden words. Returns True if quit requested."""
    hidden = get_hidden_words(card)
    if not hidden:
        return False

    typed_input = input(f"  Type {len(hidden)} word{'s' if len(hidden) > 1 else ''}: ").strip()
    if typed_input.lower() == "q":
        return True

    typed_words = typed_input.split()
    result = build_typed_result(card, typed_words)
    console.print(Panel(result, border_style="yellow", title="Your answer"))

    return False


def run_review():
    conn = get_connection()
    init_db(conn)

    config = get_config()
    typing_enabled = config.get("require_typing", False)
    skip_new_today = config.get("skip_new_today", False)

    cards = get_due_cards(conn, skip_new_today=skip_new_today)
    if not cards:
        next_date = get_next_review_date(conn)
        conn.close()
        if next_date:
            days = (date.fromisoformat(next_date) - date.today()).days
            console.print(f"\n[bold green]No cards due for review![/]")
            console.print(f"  Next review: [bold]{next_date}[/] ({days} day{'s' if days != 1 else ''} from now)\n")
        else:
            console.print("\n[bold green]No cards due for review! Come back later.[/]")
        return

    console.print(f"\n[bold]{len(cards)} cards due for review.[/] Press [bold]q[/] to quit.\n")

    reviewed = 0
    for i, card in enumerate(cards):
        # Question
        question = build_question(card)
        header = f"Card {i + 1}/{len(cards)}"
        require_typing = typing_enabled

        q_panel = Text()
        q_panel.append(question)
        q_panel.append("\n\n")
        if card["translation_words"]:
            q_panel.append(f"Translation: {card['translation_words']}", style="cyan")

        console.print(Panel(q_panel, title=header, border_style="blue"))

        if require_typing:
            quit_requested = prompt_typing(card)
            if quit_requested:
                break
        else:
            user_input = input("  [Enter to reveal, q to quit] ")
            if user_input.strip().lower() == "q":
                break

        # Answer — play audio on reveal
        play_audio(card["pronunciation_url"])
        answer = build_answer(card)
        hints = build_word_hints(card)

        a_panel = Text()
        a_panel.append(answer)
        a_panel.append("\n\n")
        if card["translation_words"]:
            a_panel.append(card["translation_words"], style="bold cyan")
            a_panel.append("\n")
        if card["translation_sentence"]:
            a_panel.append(f"({card['translation_sentence']})", style="dim cyan")
            a_panel.append("\n")
        if hints:
            a_panel.append("\n")
            for hint in hints:
                a_panel.append(hint + "\n", style="dim")

        a_panel.append("\n")
        a_panel.append("1: Again  ", style="bold red")
        a_panel.append("2: Hard  ", style="bold yellow")
        a_panel.append("3: Good  ", style="bold blue")
        a_panel.append("4: Easy  ", style="bold green")
        a_panel.append("r: Replay audio", style="dim")

        console.print(Panel(a_panel, title=header, border_style="green"))

        # Get rating
        while True:
            rating_input = input("  Rating (1-4, r=replay, q=quit): ").strip().lower()
            if rating_input == "q":
                conn.close()
                console.print(f"\n[bold]Session ended. Reviewed {reviewed} cards.[/]")
                return
            if rating_input == "r":
                play_audio(card["pronunciation_url"])
                continue
            if rating_input in ("1", "2", "3", "4"):
                rating = int(rating_input)
                break
            console.print("  [red]Enter 1, 2, 3, 4, r, or q[/]")

        # Update SM-2
        new_ease, new_interval, new_reps = sm2(
            rating,
            card["ease_factor"],
            card["interval_days"],
            card["repetitions"],
        )
        next_review = (date.today() + timedelta(days=new_interval)).isoformat()

        update_review(conn, card["id"], new_ease, new_interval, new_reps, next_review)
        reviewed += 1

        # Brief feedback
        console.print(f"  [dim]→ Next review in {new_interval} day{'s' if new_interval != 1 else ''}[/]\n")

    conn.close()
    console.print(f"\n[bold green]Session complete! Reviewed {reviewed} cards.[/]")
