import argparse
import sys

from rich.console import Console
from rich.table import Table

from srs.db import get_connection, init_db, search_cards


console = Console()


def cmd_sync(args):
    from srs.sync import sync_from_api, sync_from_file
    if args.from_file:
        sync_from_file(args.from_file)
    else:
        sync_from_api(full=args.full)


def cmd_review(args):
    from srs.review import run_review
    run_review()


def cmd_stats(args):
    from srs.stats import show_stats
    show_stats()


def cmd_notify(args):
    from srs.notify import notify_on, notify_off, notify_status, fire_notification
    action = args.notify_action
    if action == "on":
        if args.dry_run:
            fire_notification()
            return
        times = args.at if args.at else ["09:00"]
        notify_on(times)
    elif action == "off":
        notify_off()
    elif action == "status":
        notify_status()



def cmd_config(args):
    from srs.sync import get_config, CONFIG_PATH
    import json, os

    config = get_config()

    if args.config_action == "typing":
        if args.value == "on":
            config["require_typing"] = True
            console.print("[bold green]Typing mode enabled.[/] Cards with ease ≤ 2.5 will require typing.")
        elif args.value == "off":
            config["require_typing"] = False
            console.print("[bold]Typing mode disabled.[/]")
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)

    elif args.config_action == "skip-new-today":
        if args.value == "on":
            config["skip_new_today"] = True
            console.print("[bold green]Skip new today enabled.[/] Cards added today won't appear in reviews.")
        elif args.value == "off":
            config["skip_new_today"] = False
            console.print("[bold]Skip new today disabled.[/]")
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)

    elif args.config_action is None:
        typing_status = "on" if config.get("require_typing", False) else "off"
        skip_new_status = "on" if config.get("skip_new_today", False) else "off"
        console.print(f"  require_typing:  [bold]{typing_status}[/]")
        console.print(f"  skip_new_today:  [bold]{skip_new_status}[/]")


def cmd_browse(args):
    conn = get_connection()
    init_db(conn)

    query = " ".join(args.query) if args.query else ""
    if not query:
        cards = conn.execute("""
            SELECT c.*, r.next_review, r.interval_days
            FROM cards c JOIN reviews r ON c.id = r.card_id
            ORDER BY c.position ASC LIMIT 50
        """).fetchall()
    else:
        cards = search_cards(conn, query)

    conn.close()

    if not cards:
        console.print("\n[bold yellow]No cards found.[/]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Phrase")
    table.add_column("Translation", style="cyan")
    table.add_column("Next Review", style="yellow")
    table.add_column("Interval", justify="right")

    for card in cards:
        interval = f"{card['interval_days']}d" if card["interval_days"] else "new"
        table.add_row(
            str(card["position"]),
            card["phrase"],
            card["translation_words"] or "",
            card["next_review"],
            interval,
        )

    console.print(f"\n[bold]{len(cards)} cards{'  (showing first 50)' if len(cards) == 50 else ''}[/]\n")
    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        prog="srs",
        description="Speakly Spaced Repetition System",
    )
    subparsers = parser.add_subparsers(dest="command")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync words from Speakly")
    sync_parser.add_argument("--from-file", help="Import from JSON file instead of API")
    sync_parser.add_argument("--full", action="store_true", help="Fetch all pages (don't stop early on known cards)")
    sync_parser.set_defaults(func=cmd_sync)

    # review
    review_parser = subparsers.add_parser("review", help="Start review session")
    review_parser.set_defaults(func=cmd_review)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show learning statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # browse
    browse_parser = subparsers.add_parser("browse", help="Browse/search word bank")
    browse_parser.add_argument("query", nargs="*", help="Search query")
    browse_parser.set_defaults(func=cmd_browse)

    # config
    config_parser = subparsers.add_parser("config", help="Manage settings")
    config_sub = config_parser.add_subparsers(dest="config_action")
    typing_parser = config_sub.add_parser("typing", help="Toggle typing mode for low-ease cards")
    typing_parser.add_argument("value", choices=["on", "off"], help="Enable or disable typing mode")
    skip_new_parser = config_sub.add_parser("skip-new-today", help="Skip cards added today during review")
    skip_new_parser.add_argument("value", choices=["on", "off"], help="Enable or disable skipping new cards")
    config_parser.set_defaults(func=cmd_config)

    # notify
    notify_parser = subparsers.add_parser("notify", help="Manage review reminders")
    notify_sub = notify_parser.add_subparsers(dest="notify_action")
    notify_on_parser = notify_sub.add_parser("on", help="Enable notifications")
    notify_on_parser.add_argument(
        "--at", action="append", metavar="HH:MM",
        help="Reminder time (can be repeated, default: 09:00)",
    )
    notify_on_parser.add_argument(
        "--dry-run", action="store_true",
        help="Fire the notification now without installing the schedule",
    )
    notify_sub.add_parser("off", help="Disable notifications")
    notify_sub.add_parser("status", help="Show notification settings")
    notify_parser.set_defaults(func=cmd_notify)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "config" and not getattr(args, "config_action", None):
        args.func(args)
        sys.exit(0)

    if args.command == "notify" and not getattr(args, "notify_action", None):
        notify_parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
