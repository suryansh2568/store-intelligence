"""
Live dashboard for store metrics.

Terminal-based dashboard using rich library.
"""
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any

import requests
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text


API_URL = os.getenv("API_URL", "http://localhost:8000")
REFRESH_INTERVAL = 2  # seconds


class StoreDashboard:
    """Live dashboard for store intelligence."""
    
    def __init__(self, store_id: str):
        self.store_id = store_id
        self.console = Console()
        self.last_update = None
        
    def fetch_metrics(self) -> Optional[Dict[str, Any]]:
        """Fetch metrics from API."""
        try:
            response = requests.get(
                f"{API_URL}/stores/{self.store_id}/metrics",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            return None
    
    def fetch_anomalies(self) -> Optional[Dict[str, Any]]:
        """Fetch anomalies from API."""
        try:
            response = requests.get(
                f"{API_URL}/stores/{self.store_id}/anomalies",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            return None
    
    def create_metrics_table(self, metrics: Dict[str, Any]) -> Table:
        """Create metrics display table."""
        table = Table(title=f"Store Metrics - {self.store_id}", show_header=True)
        
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="green", width=20)
        
        if metrics:
            table.add_row("Unique Visitors", str(metrics.get("unique_visitors", 0)))
            table.add_row("Total Entries", str(metrics.get("total_entries", 0)))
            table.add_row("Total Exits", str(metrics.get("total_exits", 0)))
            table.add_row(
                "Conversion Rate",
                f"{metrics.get('conversion_rate', 0) * 100:.2f}%"
            )
            table.add_row(
                "Current Queue Depth",
                str(metrics.get("current_queue_depth", 0))
            )
            table.add_row(
                "Abandonment Rate",
                f"{metrics.get('abandonment_rate', 0) * 100:.2f}%"
            )
            table.add_row("Staff Excluded", str(metrics.get("staff_excluded", 0)))
        else:
            table.add_row("Error", "Failed to fetch metrics", style="red")
        
        return table
    
    def create_anomalies_panel(self, anomalies: Dict[str, Any]) -> Panel:
        """Create anomalies display panel."""
        if not anomalies or len(anomalies.get("anomalies", [])) == 0:
            content = Text("✓ No anomalies detected", style="green")
        else:
            lines = []
            for anomaly in anomalies["anomalies"]:
                severity = anomaly["severity"]
                style = {
                    "INFO": "blue",
                    "WARN": "yellow",
                    "CRITICAL": "red bold"
                }.get(severity, "white")
                
                lines.append(
                    Text(f"[{severity}] {anomaly['description']}", style=style)
                )
                lines.append(
                    Text(f"  → {anomaly['suggested_action']}", style="dim")
                )
                lines.append(Text(""))
            
            content = Text("\n").join(lines)
        
        return Panel(
            content,
            title="Active Anomalies",
            border_style="red" if anomalies and len(anomalies.get("anomalies", [])) > 0 else "green"
        )
    
    def create_layout(self) -> Layout:
        """Create dashboard layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        return layout
    
    def generate_display(self) -> Layout:
        """Generate complete dashboard display."""
        layout = self.create_layout()
        
        # Header
        header_text = Text(
            f"Store Intelligence Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style="bold white on blue",
            justify="center"
        )
        layout["header"].update(Panel(header_text))
        
        # Body - Metrics and Anomalies
        metrics = self.fetch_metrics()
        anomalies = self.fetch_anomalies()
        
        layout["body"].split_row(
            Layout(self.create_metrics_table(metrics)),
            Layout(self.create_anomalies_panel(anomalies))
        )
        
        # Footer
        footer_text = Text(
            f"API: {API_URL} | Refresh: {REFRESH_INTERVAL}s | Press Ctrl+C to exit",
            style="dim",
            justify="center"
        )
        layout["footer"].update(Panel(footer_text))
        
        return layout
    
    def run(self):
        """Run live dashboard."""
        self.console.print(f"\n[bold green]Starting dashboard for {self.store_id}...[/bold green]\n")
        
        try:
            with Live(self.generate_display(), refresh_per_second=1, console=self.console) as live:
                while True:
                    time.sleep(REFRESH_INTERVAL)
                    live.update(self.generate_display())
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard stopped.[/yellow]\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Store Intelligence Dashboard")
    parser.add_argument(
        "--store-id",
        default="STORE_BLR_002",
        help="Store ID to monitor"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL"
    )
    
    args = parser.parse_args()
    
    # Override API URL if provided
    global API_URL
    API_URL = args.api_url
    
    # Run dashboard
    dashboard = StoreDashboard(args.store_id)
    dashboard.run()


if __name__ == "__main__":
    main()
