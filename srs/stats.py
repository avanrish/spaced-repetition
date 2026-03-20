from rich.console import Console
from rich.table import Table

from srs.db import get_connection, init_db, get_stats

console = Console()


def show_stats():
    conn = get_connection()
    init_db(conn)

    s = get_stats(conn)
    conn.close()

    if s["total"] == 0:
        console.print("\n[bold yellow]No cards yet. Run 'srs sync' first.[/]")
        return

    console.print(f"\n[bold]Speakly SRS Stats[/]\n")
    console.print(f"  Total cards:      [bold]{s['total']}[/]")
    console.print(f"  Due today:        [bold yellow]{s['due_today']}[/]")
    console.print(f"  Reviewed today:   [bold green]{s['reviewed_today']}[/]")
    console.print(f"  Never reviewed:   [bold red]{s['never_reviewed']}[/]")
    console.print(f"  Mature (21+ days):[bold cyan] {s['mature']}[/]")

    if s["upcoming"]:
        console.print(f"\n[bold]Upcoming reviews:[/]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Date")
        table.add_column("Cards", justify="right")
        for d, count in s["upcoming"].items():
            table.add_row(d, str(count))
        console.print(table)

    console.print()
