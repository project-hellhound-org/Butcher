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
import re
import csv
import random
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse

# ── Optional Rich Dependency ──────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

import aiohttp
from bs4 import BeautifulSoup, Comment

# ── Configuration & Globals ──────────────────────────────────────────────────
VERSION = "2.0.0"
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

if RICH_AVAILABLE:
    console = Console()
else:
    class DummyConsole:
        def print(self, *args, **kwargs): print(*args)
    console = DummyConsole()

# ── Extraction Matrix ─────────────────────────────────────────────────────────
class ExtractionMatrix:
    PATTERNS = {
        "emails": {
            "regex": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
            "score": 1,
            "label": "EMAIL"
        },
        "ips": {
            "regex": r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b',
            "score": 20,
            "label": "INTERNAL_IP"
        },
        "aws_key": {
            "regex": r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}',
            "score": 100,
            "label": "AWS_KEY"
        },
        "google_api": {
            "regex": r'AIza[0-9A-Za-z\\-_]{35}',
            "score": 50,
            "label": "GOOGLE_API"
        },
        "github_token": {
            "regex": r'ghp_[a-zA-Z0-9]{36}',
            "score": 80,
            "label": "GITHUB_TOKEN"
        },
        "slack_token": {
            "regex": r'xox[baprs]-[0-9a-zA-Z]{10,48}',
            "score": 70,
            "label": "SLACK_TOKEN"
        },
        "slack_webhook": {
            "regex": r'https:\/\/hooks.slack.com\/services\/T[a-zA-Z0-9_]{8}\/B[a-zA-Z0-9_]{8}\/[a-zA-Z0-9_]{24}',
            "score": 60,
            "label": "SLACK_WEBHOOK"
        }
    }

    @staticmethod
    def extract_from_text(text: str, filters: Set[str]) -> List[Dict[str, Any]]:
        findings = []
        for key, meta in ExtractionMatrix.PATTERNS.items():
            if filters and key not in filters and meta['label'].lower() not in filters:
                continue
            matches = re.findall(meta['regex'], text)
            for match in set(matches):
                findings.append({
                    "type": meta['label'],
                    "content": match,
                    "score": meta['score']
                })
        return findings

    @staticmethod
    def extract_from_soup(soup: BeautifulSoup, filters: Set[str]) -> List[Dict[str, Any]]:
        findings = []
        
        # Hidden Inputs
        if not filters or "hidden" in filters:
            for inp in soup.find_all("input", type="hidden"):
                name = inp.get("name", "N/A")
                val = inp.get("value", "N/A")
                findings.append({
                    "type": "HIDDEN_INPUT",
                    "content": f"{name}={val}",
                    "score": 5
                })

        # Comments
        if not filters or "comments" in filters:
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                if any(k in comment.upper() for k in ["TODO", "FIXME", "DEBUG", "HACK", "XXX", "SECRET"]):
                    findings.append({
                        "type": "SENSITIVE_COMMENT",
                        "content": comment.strip(),
                        "score": 10
                    })

        # JS Variables
        if not filters or "js_vars" in filters:
            for script in soup.find_all("script"):
                if script.string:
                    matches = re.findall(r'(?:var|const|let)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*[\'"]([^\'"]+)[\'"]', script.string)
                    for var_name, var_val in matches:
                        if any(k in var_name.upper() for k in ["KEY", "SECRET", "TOKEN", "PASS", "AUTH", "API"]):
                            findings.append({
                                "type": "JS_VAR",
                                "content": f"{var_name}={var_val}",
                                "score": 30
                            })

        # JSON-LD
        if not filters or "json_ld" in filters:
            for script in soup.find_all("script", type="application/ld+json"):
                if script.string:
                    findings.append({
                        "type": "JSON_LD",
                        "content": script.string.strip()[:200] + "...",
                        "score": 5
                    })

        return findings

# ── Stealth & Evasion ─────────────────────────────────────────────────────────
class StealthManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ]

    @staticmethod
    def get_random_ua():
        return random.choice(StealthManager.USER_AGENTS)

    @staticmethod
    def get_random_viewport():
        return {
            "width": random.randint(1280, 1920),
            "height": random.randint(720, 1080)
        }

# ── HUD Engine ────────────────────────────────────────────────────────────────
class ButcherHUD:
    def __init__(self, target: str):
        self.target = target
        self.start_time = time.time()
        self.extracted_count = 0
        self.total_score = 0
        self.errors = 0
        self.current_action = "Initializing..."
        self.findings: List[Dict[str, Any]] = []

    def make_layout(self) -> Layout:
        if not RICH_AVAILABLE: return None
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
        table.add_row("Findings", f"[green]{len(self.findings)}[/green]")
        table.add_row("Risk Score", f"[bold red]{self.total_score}[/bold red]")
        table.add_row("Errors", f"[red]{self.errors}[/red]")
        table.add_row("Action", f"[yellow]{self.current_action}[/yellow]")
        return table

    def get_results_table(self) -> Table:
        table = Table(title="Surgical Extraction Log", box=box.MINIMAL_DOUBLE_HEAD, expand=True)
        table.add_column("Type", style="bold magenta", width=15)
        table.add_column("Content", style="green", no_wrap=True)
        table.add_column("Score", style="yellow", justify="right", width=5)
        
        for finding in self.findings[-12:]:
            content = finding["content"]
            if len(content) > 80: content = content[:77] + "..."
            table.add_row(finding["type"], content, str(finding["score"]))
        return table

    def get_footer(self) -> Panel:
        return Panel(
            "[dim]Press Ctrl+C to abort surgical extraction[/dim]",
            box=box.HORIZONTALS,
            border_style="red",
            title_align="right"
        )

# ── Recon Engine (Phase 1) ────────────────────────────────────────────────────
def run_external_spider(target: str, depth: int, verbose: bool):
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    # Try to find spider.py in the same dir or in sibling Hellhound-Spider
    spider_paths = [
        os.path.join(_script_dir, "spider.py"),
        os.path.join(os.path.dirname(_script_dir), "Hellhound-Spider", "spider.py")
    ]
    spider_path = next((p for p in spider_paths if os.path.exists(p)), None)
    
    if not spider_path:
        return [{"url": target, "method": "GET"}]

    temp_json = os.path.join(_script_dir, f".butcher_recon_{int(time.time())}.json")
    cmd = [sys.executable, spider_path, target, "--out", temp_json, "--depth", str(depth)]
    if verbose: cmd.append("--verbose")

    try:
        if RICH_AVAILABLE:
            with Progress(SpinnerColumn(), TextColumn("[bold red]PHASE 1: RECONNAISSANCE BY HELLHOUND-SPIDER[/]"), transient=True) as p:
                p.add_task("Crawling...", total=None)
                subprocess.run(cmd, check=True, capture_output=not verbose)
        else:
            print("[*] Phase 1: Reconnaissance by Hellhound-Spider...")
            subprocess.run(cmd, check=True, capture_output=not verbose)

        if not os.path.exists(temp_json): return [{"url": target, "method": "GET"}]
        with open(temp_json, "r") as f: data = json.load(f)
        try: os.remove(temp_json)
        except OSError: pass

        endpoints = []
        for ep in data.get("endpoints", []):
            endpoints.append({"url": ep["url"], "method": ep.get("methods", ["GET"])[0]})
        return endpoints
    except Exception as e:
        print(f"[!] Recon failed: {e}")
        return [{"url": target, "method": "GET"}]

# ── Scraper Core (Phase 2) ────────────────────────────────────────────────────
class ButcherEngine:
    def __init__(self, args):
        self.args = args
        self.visited = set()
        self.findings = []
        self.total_score = 0
        self.filters = set(args.extract.split(",")) if args.extract else set()

    async def run(self, hud: ButcherHUD):
        # Phase 1: Recon
        hud.current_action = "Phase 1: Reconnaissance..."
        endpoints = run_external_spider(self.args.target, self.args.depth, self.args.verbose)
        
        # Phase 2: Extraction
        hud.current_action = "Phase 2: Surgical Extraction..."
        async with aiohttp.ClientSession(headers={"User-Agent": StealthManager.get_random_ua()}) as session:
            tasks = []
            for ep in endpoints[:getattr(self.args, "max_pages", 50)]:
                if any(ex in ep["url"] for ex in self.args.exclude.split(",")): continue
                tasks.append(self.process_endpoint(ep["url"], session, hud))
            await asyncio.gather(*tasks)

    async def process_endpoint(self, url: str, session: aiohttp.ClientSession, hud: ButcherHUD):
        if url in self.visited: return
        self.visited.add(url)
        
        hud.current_action = f"Butchering {urlparse(url).path or '/'}"
        try:
            if self.args.browser:
                findings = await self._scrape_with_playwright(url, hud)
            else:
                findings = await self._scrape_with_aiohttp(url, session, hud)
            
            for f in findings:
                if f["content"] not in [x["content"] for x in self.findings]:
                    self.findings.append(f)
                    self.total_score += f["score"]
                    hud.findings.append(f)
                    hud.total_score = self.total_score
        except Exception as e:
            hud.errors += 1

    async def _scrape_with_aiohttp(self, url: str, session: aiohttp.ClientSession, hud: ButcherHUD):
        try:
            async with session.get(url, timeout=self.args.timeout, proxy=self.args.proxy, allow_redirects=self.args.follow_redirects) as resp:
                if resp.status == 403: return [{"type": "INFO", "content": "403 Forbidden - Try --browser", "score": 0}]
                if resp.status == 404: return []
                html = await resp.text()
                return self.perform_extraction(html)
        except: return []

    async def _scrape_with_playwright(self, url: str, hud: ButcherHUD):
        from playwright.async_api import async_playwright
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy={"server": self.args.proxy} if self.args.proxy else None)
                context = await browser.new_context(
                    user_agent=StealthManager.get_random_ua(),
                    viewport=StealthManager.get_random_viewport()
                )
                page = await context.new_page()
                await page.goto(url, timeout=self.args.timeout * 1000, wait_until="networkidle")
                html = await page.content()
                await browser.close()
                return self.perform_extraction(html)
        except: return []

    def perform_extraction(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        f1 = ExtractionMatrix.extract_from_text(text, self.filters)
        f2 = ExtractionMatrix.extract_from_soup(soup, self.filters)
        return f1 + f2

# ── CLI Interface ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Butcher — Surgical Web Scraper")
    parser.add_argument("target", help="Target URL to scrape")
    parser.add_argument("--browser", action="store_true", help="Use headless browser for SPA rendering")
    parser.add_argument("--extract", help="Comma-separated list of items to extract")
    parser.add_argument("--output", help="Save findings to file")
    parser.add_argument("--output-format", choices=["json", "csv", "markdown", "quiet"], default="json")
    parser.add_argument("--depth", type=int, default=0, help="Crawl depth (via spider)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to process")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--proxy", help="Proxy URL (e.g., http://127.0.0.1:8080)")
    parser.add_argument("--exclude", default="logout,delete,admin", help="Exclude paths")
    parser.add_argument("--follow-redirects", action="store_true", help="Follow HTTP redirects")
    parser.add_argument("--score-only", action="store_true", help="Only show the final risk score")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    if not args.target.startswith("http"):
        args.target = "https://" + args.target

    if not args.score_only: print(BANNER)
    
    hud = ButcherHUD(args.target)
    engine = ButcherEngine(args)
    
    try:
        if RICH_AVAILABLE and not args.score_only:
            layout = hud.make_layout()
            with Live(layout, refresh_per_second=10, screen=True):
                async def run_loop():
                    await engine.run(hud)
                    hud.current_action = "Extraction Complete"
                    await asyncio.sleep(1)
                asyncio.run(run_loop())
        else:
            asyncio.run(engine.run(hud))

        # Output Generation
        generate_output(engine.findings, engine.total_score, args)

    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
        sys.exit(1)

def generate_output(findings, score, args):
    if args.score_only:
        print(f"Risk Score: {score}")
        return

    if not args.output:
        if args.output_format != "quiet":
            print(f"\n[+] Total Score: {score}")
            print(f"[+] Total Findings: {len(findings)}")
        return

    if args.output_format == "json":
        with open(args.output, "w") as f:
            json.dump({"target": args.target, "score": score, "findings": findings}, f, indent=4)
    elif args.output_format == "csv":
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["type", "content", "score"])
            writer.writeheader()
            writer.writerows(findings)
    elif args.output_format == "markdown":
        with open(args.output, "w") as f:
            f.write(f"# Butcher Scan Report: {args.target}\n\n")
            f.write(f"- **Total Risk Score:** {score}\n")
            f.write(f"- **Total Findings:** {len(findings)}\n\n")
            f.write("## Findings\n\n")
            f.write("| Type | Content | Score |\n")
            f.write("| --- | --- | --- |\n")
            for fnd in findings:
                f.write(f"| {fnd['type']} | `{fnd['content']}` | {fnd['score']} |\n")

    print(f"[+] Results saved to {args.output} ({args.output_format})")

if __name__ == "__main__":
    main()
