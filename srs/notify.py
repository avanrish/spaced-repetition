import json
import os
import plistlib
import subprocess
import sys
from datetime import time

from rich.console import Console

from srs.db import DB_DIR, get_connection, init_db, get_stats

console = Console()

PLIST_LABEL = "com.speakly-srs.notify"
PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
PLIST_PATH = os.path.join(PLIST_DIR, f"{PLIST_LABEL}.plist")
CONFIG_PATH = os.path.join(DB_DIR, "notify.json")


def _srs_executable() -> str:
    """Return the path to the srs executable."""
    # Use the same Python that's running this process
    return os.path.join(os.path.dirname(sys.executable), "srs")


def _send_notification(title: str, message: str):
    """Send a macOS notification using osascript."""
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _save_config(times: list[str]):
    os.makedirs(DB_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"times": times}, f, indent=2)


def _load_config() -> dict | None:
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _parse_time(s: str) -> time:
    """Parse HH:MM string into a time object."""
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {s!r} (expected HH:MM)")
    return time(int(parts[0]), int(parts[1]))


def _write_plist(times: list[str]):
    """Write a launchd plist that runs 'srs _notify-fire' at given times."""
    srs_bin = _srs_executable()

    calendar_intervals = []
    for t in times:
        parsed = _parse_time(t)
        calendar_intervals.append({"Hour": parsed.hour, "Minute": parsed.minute})

    plist = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [srs_bin, "notify", "on", "--dry-run"],
        "StartCalendarInterval": calendar_intervals,
        "StandardOutPath": os.path.join(DB_DIR, "notify.log"),
        "StandardErrorPath": os.path.join(DB_DIR, "notify.log"),
    }

    os.makedirs(PLIST_DIR, exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)


def _load_agent():
    """Load (register) the LaunchAgent."""
    subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True)


def _unload_agent():
    """Unload (unregister) the LaunchAgent."""
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)


def _is_loaded() -> bool:
    """Check if the LaunchAgent is currently loaded."""
    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def notify_on(times: list[str]):
    """Enable notifications at the given times."""
    # Validate all times first
    for t in times:
        _parse_time(t)

    # Unload old agent if present
    if os.path.exists(PLIST_PATH):
        _unload_agent()

    _save_config(times)
    _write_plist(times)
    _load_agent()

    times_str = ", ".join(times)
    console.print(f"\n[bold green]Notifications enabled![/]")
    console.print(f"  Reminder times: [bold]{times_str}[/]")
    console.print(f"  You'll get a macOS notification when reviews are due.\n")


def notify_off():
    """Disable notifications."""
    if os.path.exists(PLIST_PATH):
        _unload_agent()
        os.remove(PLIST_PATH)

    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)

    console.print(f"\n[bold yellow]Notifications disabled.[/]\n")


def notify_status():
    """Show current notification settings."""
    config = _load_config()
    loaded = _is_loaded()

    if not config and not loaded:
        console.print("\n[bold yellow]Notifications are not configured.[/]")
        console.print("  Run [bold]srs notify on[/] to enable.\n")
        return

    status = "[bold green]active[/]" if loaded else "[bold red]inactive[/]"
    console.print(f"\n[bold]Notification status:[/] {status}")

    if config:
        times_str = ", ".join(config.get("times", []))
        console.print(f"  Reminder times: [bold]{times_str}[/]")

    console.print(f"  Plist: {'exists' if os.path.exists(PLIST_PATH) else 'missing'}")
    console.print()


def fire_notification():
    """Check for due cards and send a notification if any are pending."""
    conn = get_connection()
    init_db(conn)
    stats = get_stats(conn)
    conn.close()

    due = stats["due_today"]
    if due > 0:
        word = "card" if due == 1 else "cards"
        _send_notification(
            "Speakly SRS",
            f"You have {due} {word} due for review. Run: srs review",
        )
