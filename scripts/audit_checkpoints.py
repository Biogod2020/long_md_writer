
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.types import AgentState
from src.orchestration.breakpoint_manager import SnapshotManager

console = Console()

def run_audit(job_id: str):
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if not workspace_path.exists():
        console.print(f"[bold red]Error:[/bold red] Workspace {job_id} not found.")
        return

    # Use a dummy state to initialize SnapshotManager
    dummy_state = AgentState(job_id=job_id, workspace_path=str(workspace_path))
    snm = SnapshotManager(dummy_state)
    
    snapshots = snm.list_snapshots()
    
    if not snapshots:
        console.print(Panel(f"No snapshots found for job: [bold cyan]{job_id}[/bold cyan]", title="Audit Report"))
        return

    table = Table(title=f"🔍 Breakpoint Audit: {job_id}")
    table.add_column("ID / Name", style="cyan", no_wrap=True)
    table.add_column("Breakpoint", style="magenta")
    table.add_column("Sections", justify="right")
    table.add_column("Assets", justify="right")
    table.add_column("Timestamp", style="green")

    for s in snapshots:
        table.add_row(
            s['id'],
            s['bp_id'],
            str(s['sections']),
            str(s['assets']),
            s['timestamp'] or "N/A"
        )

    console.print(table)
    console.print(f"\n[dim]Physical base: {workspace_path}/snapshots/[/dim]")

def main():
    parser = argparse.ArgumentParser(description="SOTA 2.0 Physical Audit Tool")
    parser.add_argument("--job-id", required=True, help="Job ID to audit")
    args = parser.parse_args()
    run_audit(args.job_id)

if __name__ == "__main__":
    main()
