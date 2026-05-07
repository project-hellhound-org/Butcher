#!/usr/bin/env python3
"""
BUTCHER — Surgical Web Scraper
High-fidelity data extraction engine for the Hellhound ecosystem.
"""

import asyncio
import argparse
import sys
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich import box

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ── Configuration & Globals ──────────────────────────────────────────────────
VERSION = "1.0.0"
BANNER = f"""
\033[91m
 ██████╗ ██╗   ██╗████████╗ ██████╗██╗  ██╗███████╗██████╗ 
 ██╔══██╗██║   ██║╚══██╔══╝██╔════╝██║  ██║██╔════╝██╔══██╗
 ██████╔╝██║   ██║   ██║   ██║     ███████║█████╗  ██████╔╝
 ██╔══██╗██║   ██║   ██║   ██║     ██╔══██║██╔══╝  ██╔══██╗
 ██████╔╝╚██████╔╝   ██║   ╚██████╗██║  ██║███████╗██║  ██║
 ╚══════╝ ╚═════╝    ╚═╝    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
\033[0m
          \033[1mSurgical Web Scraper v{VERSION}\033[0m
"""

console = Console()

# ── HUD Engine ────────────────────────────────────────────────────────────────
class ButcherHUD:
    def __init__(self, target: str):
        self.target = target
        self.start_time = time.time()
        self.extracted_count = 0
        self.errors = 0
        self.current_action = "Initializing..."
        self.findings: List[Dict[str, str]] = []

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="status", ratio=1),
            Layout(name="results", ratio=2)
        )
        return layout

    def get_header(self) -> Panel:
        return Panel(
            f"[bold red]BUTCHER[/bold red] [white]|[/white] Target: [cyan]{self.target}[/cyan]",
            box=box.HORIZONTALS,
            border_style="red"
        )

    def get_status_table(self) -> Table:
        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        table.add_column("Key", style="dim cyan")
        table.add_column("Value", style="bold white")
        
        elapsed = time.strftime("%H:%M:%S", time.gmtime(time.time() - self.start_time))
        table.add_row("Elapsed Time", elapsed)
        table.add_row("Extracted", f"[green]{self.extracted_count}[/green]")
        table.add_row("Errors", f"[red]{self.errors}[/red]")
        table.add_row("Action", f"[yellow]{self.current_action}[/yellow]")
        return table

    def get_results_table(self) -> Table:
        table = Table(title="Live Extraction Log", box=box.MINIMAL_DOUBLE_HEAD, expand=True)
        table.add_column("Type", style="dim", width=12)
        table.add_column("Content", style="green", no_wrap=True)
        
        # Show last 10 findings
        for finding in self.findings[-10:]:
            table.add_row(finding["type"], finding["content"][:80] + "..." if len(finding["content"]) > 80 else finding["content"])
        return table

    def get_footer(self) -> Panel:
        return Panel(
            "[dim]Press Ctrl+C to abort surgical extraction[/dim]",
            box=box.HORIZONTALS,
            border_style="red",
            title_align="right"
        )

# ── Scraper Core ─────────────────────────────────────────────────────────────
class ButcherEngine:
    def __init__(self, target: str, use_browser: bool = False):
        self.target = target
        self.use_browser = use_browser
        self.results = []

    async def scrape(self, hud: ButcherHUD):
        if self.use_browser:
            await self._scrape_with_playwright(hud)
        else:
            await self._scrape_with_aiohttp(hud)

    async def _scrape_with_aiohttp(self, hud: ButcherHUD):
        hud.current_action = "Fetching via HTTP..."
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.target, timeout=10) as response:
                    html = await response.text()
                    await self._process_html(html, hud)
        except Exception as e:
            hud.errors += 1
            hud.current_action = f"Error: {str(e)[:30]}"

    async def _scrape_with_playwright(self, hud: ButcherHUD):
        hud.current_action = "Launching Chromium..."
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            hud.current_action = f"Rendering {self.target}..."
            await page.goto(self.target, wait_until="networkidle")
            
            # Extract content after JS execution
            html = await page.content()
            await self._process_html(html, hud)
            await browser.close()

    async def _process_html(self, html: str, hud: ButcherHUD):
        hud.current_action = "Carving data..."
        soup = BeautifulSoup(html, "lxml")
        
        # Sample extraction logic: Links and Headings
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith("http"):
                hud.findings.append({"type": "LINK", "content": href})
                hud.extracted_count += 1
                await asyncio.sleep(0.05) # Dramatic effect

        for h in soup.find_all(["h1", "h2", "h3"]):
            text = h.get_text(strip=True)
            if text:
                hud.findings.append({"type": "HEADING", "content": text})
                hud.extracted_count += 1
                await asyncio.sleep(0.05)

# ── CLI Interface ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Butcher — Surgical Web Scraper")
    parser.add_argument("target", help="Target URL to scrape")
    parser.add_argument("--browser", action="store_true", help="Use headless browser for SPA rendering")
    parser.add_argument("-o", "--output", help="Save findings to JSON file")
    args = parser.parse_args()

    print(BANNER)
    
    hud = ButcherHUD(args.target)
    engine = ButcherEngine(args.target, use_browser=args.browser)
    
    layout = hud.make_layout()

    try:
        with Live(layout, refresh_per_second=10, screen=True):
            # Update loop
            async def run():
                scrape_task = asyncio.create_task(engine.scrape(hud))
                while not scrape_task.done():
                    layout["header"].update(hud.get_header())
                    layout["status"].update(Panel(hud.get_status_table(), title="Telemetry", border_style="cyan"))
                    layout["results"].update(hud.get_results_table())
                    layout["footer"].update(hud.get_footer())
                    await asyncio.sleep(0.1)
                hud.current_action = "Extraction Complete"
                await asyncio.sleep(1) # Allow user to see final state

            asyncio.run(run())

        # Post-run cleanup
        console.print(f"\n[bold green]✓[/bold green] Surgical extraction complete.")
        console.print(f"[bold cyan]*[/bold cyan] Total findings: [white]{hud.extracted_count}[/white]")
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(hud.findings, f, indent=4)
            console.print(f"[bold cyan]*[/bold cyan] Results saved to [yellow]{args.output}[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[bold red]✗[/bold red] Extraction aborted by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()
