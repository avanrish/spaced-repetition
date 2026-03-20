import json
import os
import re
import shlex
import sys
import time

import requests
from rich.console import Console

from srs.db import get_connection, init_db, upsert_card

HEADERS_PATH = os.path.expanduser("~/.speakly-srs/headers.json")
CONFIG_PATH = os.path.expanduser("~/.speakly-srs/config.json")

console = Console()


def parse_curl(curl_command: str) -> dict:
    """Parse a cURL command into url and headers dict."""
    curl_command = curl_command.strip()
    if curl_command.startswith("$"):
        curl_command = curl_command[1:].strip()

    # Normalize line continuations
    curl_command = curl_command.replace("\\\n", " ").replace("\\\r\n", " ")

    try:
        tokens = shlex.split(curl_command)
    except ValueError:
        # Try removing trailing backslashes
        curl_command = curl_command.rstrip("\\").strip()
        tokens = shlex.split(curl_command)

    url = None
    headers = {}

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "curl":
            i += 1
            continue
        if token in ("-H", "--header"):
            i += 1
            if i < len(tokens):
                header = tokens[i]
                if ":" in header:
                    key, value = header.split(":", 1)
                    headers[key.strip()] = value.strip()
        elif token.startswith("http"):
            url = token
        elif token in ("--compressed", "--insecure", "-k", "-s", "--silent", "-v", "--verbose"):
            pass  # skip flags without args
        elif token in ("-X", "--request", "--data", "-d", "--data-raw", "--data-binary", "--user-agent", "-A", "--referer", "-e"):
            i += 1  # skip flag + its argument
        elif not token.startswith("-") and url is None:
            url = token
        i += 1

    if not url:
        raise ValueError("Could not find URL in cURL command")

    return {"url": url, "headers": headers}


def save_headers(parsed: dict):
    os.makedirs(os.path.dirname(HEADERS_PATH), exist_ok=True)
    with open(HEADERS_PATH, "w") as f:
        json.dump(parsed, f, indent=2)


def load_headers() -> dict | None:
    if not os.path.exists(HEADERS_PATH):
        return None
    with open(HEADERS_PATH) as f:
        return json.load(f)


def get_config() -> dict:
    defaults = {"language_pair_id": 15, "daily_review_limit": 100}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            defaults.update(json.load(f))
    return defaults


def prompt_curl() -> dict:
    console.print("\n[bold yellow]Paste cURL command from browser devtools:[/]")
    console.print("[dim](In devtools Network tab, right-click the review/all request → Copy as cURL)[/]")
    console.print("[dim](Paste and press Enter twice when done)[/]\n")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            break
        lines.append(line)

    curl_str = " ".join(lines)
    parsed = parse_curl(curl_str)
    save_headers(parsed)
    console.print(f"[green]Saved {len(parsed['headers'])} headers.[/]")
    return parsed


def fetch_all_words(parsed: dict, full: bool = False, existing_ids: set[int] | None = None) -> list[dict] | None:
    """Fetch words from Speakly API, paginating as needed.

    If full=False (default), stops early when an entire page contains
    only cards we already have. full=True fetches everything.
    """
    config = get_config()
    lang_id = config["language_pair_id"]

    # Build base URL from saved URL or construct default
    base_url = parsed.get("url", "")
    # Replace page params to control pagination
    base_url = re.sub(r"page=\d+", "page={page}", base_url)
    base_url = re.sub(r"page_size=\d+", "page_size=100", base_url)
    if "{page}" not in base_url:
        base_url = f"https://api.v4.speakly.me/api/v4/review/{lang_id}/all?page={{page}}&page_size=100&order_by=true"

    all_results = []
    page = 1

    while True:
        url = base_url.format(page=page)
        console.print(f"[dim]Fetching page {page}...[/]")

        resp = requests.get(url, headers=parsed["headers"], timeout=30)

        if resp.status_code in (401, 403):
            return None  # Signal auth failure

        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        all_results.extend(results)

        # Early stop: if not full sync and every card on this page already exists
        if not full and existing_ids is not None and results:
            new_on_page = sum(1 for r in results if r["id"] not in existing_ids)
            if new_on_page == 0:
                console.print(f"[dim]No new cards on page {page}, stopping early. Use --full to fetch all.[/]")
                break

        if data.get("next") is None:
            break

        page += 1
        time.sleep(1)  # Rate limit: 1 second between pages

    return all_results


def sync_from_api(full: bool = False):
    parsed = load_headers()
    if parsed is None:
        parsed = prompt_curl()

    # Load existing card IDs for early-stop detection
    conn = get_connection()
    init_db(conn)
    existing_ids = {row[0] for row in conn.execute("SELECT id FROM cards").fetchall()}

    words = fetch_all_words(parsed, full=full, existing_ids=existing_ids)

    if words is None:
        console.print("[bold red]Authentication failed (401/403). Session may have expired.[/]")
        parsed = prompt_curl()
        words = fetch_all_words(parsed, full=full, existing_ids=existing_ids)
        if words is None:
            console.print("[bold red]Still failing. Check that you copied the right request.[/]")
            conn.close()
            sys.exit(1)

    new_count = 0
    updated_count = 0
    for item in words:
        is_new = upsert_card(conn, item)
        if is_new:
            new_count += 1
        else:
            updated_count += 1

    conn.commit()
    conn.close()

    console.print(f"\n[bold green]Synced {len(words)} words ({new_count} new, {updated_count} updated)[/]")


def sync_from_file(filepath: str):
    if not os.path.exists(filepath):
        console.print(f"[bold red]File not found: {filepath}[/]")
        sys.exit(1)

    with open(filepath) as f:
        data = json.load(f)

    # Support both raw results array and full API response
    if isinstance(data, list):
        words = data
    elif isinstance(data, dict) and "results" in data:
        words = data["results"]
    else:
        console.print("[bold red]Unexpected JSON format. Expected array or {results: [...]}[/]")
        sys.exit(1)

    conn = get_connection()
    init_db(conn)

    new_count = 0
    updated_count = 0
    for item in words:
        is_new = upsert_card(conn, item)
        if is_new:
            new_count += 1
        else:
            updated_count += 1

    conn.commit()
    conn.close()

    console.print(f"\n[bold green]Imported {len(words)} words ({new_count} new, {updated_count} updated)[/]")
