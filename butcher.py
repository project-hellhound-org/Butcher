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
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup, Comment

# ── Colors & Branding ────────────────────────────────────────────────────────
class C:
    RED     = "\033[91m"    # Bright Red
    YELLOW  = "\033[93m"    # Bright Yellow
    CYAN    = "\033[96m"    # Bright Cyan
    MAGENTA = "\033[95m"    # Magenta
    WHITE   = "\033[97m"    # Bright White
    GRAY    = "\033[90m"    # Dark Gray
    B       = "\033[1m"     # Bold
    D       = "\033[2m"     # Dim
    RST     = "\033[0m"     # Reset

def get_tw():
    try:
        tw = shutil.get_terminal_size().columns
        return tw if tw > 10 else 100
    except: return 100

def print_banner():
    tw = get_tw()
    banner_raw = r"""
_____________  ______________________  __________________
___  __ )_  / / /__  __/_  ____/__  / / /__  ____/__  __ \
__  __  |  / / /__  /  _  /    __  /_/ /__  __/  __  /_/ /
_  /_/ // /_/ / _  /   / /___  _  __  / _  /___  _  _, _/ 
/_____/ \____/  /_/    \____/  /_/ /_/  /_____/  /_/ |_|   
"""
    for line in banner_raw.strip().split("\n"):
        print(f"{C.RED}{line.center(tw)}{C.RST}")
    print()

# ── HUD Engine (Clean Layout Interface) ───────────────────────────────────────
class ButcherHUD:
    def __init__(self, target: str, args: Any):
        self.target = target
        self.args = args
        self.start_time = time.time()
        self.total_score = 0
        self.findings_count = 0
        self.categories = {}
        self.quiet = args.quiet
        self.silent = getattr(args, 'silent', False)

    def border(self):
        if self.quiet or self.silent: return
        print(f"{C.RED}{'━' * get_tw()}{C.RST}")

    def header(self):
        if self.quiet or self.silent: return
        self.border()
        mode = "browser" if self.args.browser else "lightweight"
        print(f"{C.WHITE}TARGET: {C.YELLOW}{self.target}{C.RST}")
        print(f"{C.WHITE}MODE: {C.MAGENTA}{mode}{C.RST} | {C.WHITE}DEPTH: {C.MAGENTA}{self.args.depth}{C.RST} | {C.WHITE}TIMEOUT: {C.MAGENTA}{self.args.timeout}s{C.RST}")
        self.border()

    def progress(self, url: str, code: int = 0, size: int = 0, percent: int = 0):
        if self.quiet or self.silent: return
        tw = get_tw()
        bar_len = 30
        filled = int((percent / 100) * bar_len)
        bar = f"{C.RED}{'━' * filled}{C.GRAY}{' ' * (bar_len - filled)}{C.RST}"
        status = f"{C.WHITE}{code if code else '...'}{C.RST} ({size}b)"
        line = f"▶ FETCHING {bar} {status} {C.D}{url[:tw-bar_len-25]}{C.RST}"
        sys.stdout.write(f"\r{line.ljust(tw)}")
        sys.stdout.flush()

    def section(self, title: str):
        if self.quiet or self.silent: return
        print(f"\n{C.RED}{'━' * get_tw()}{C.RST}")
        print(f" {C.CYAN}{title}{C.RST}")
        print(f"{C.RED}{'━' * get_tw()}{C.RST}")

    def add_finding(self, ftype: str, content: str, score: int):
        if self.silent: return
        if ftype not in self.categories:
            self.categories[ftype] = {"count": 0, "findings": []}
        self.categories[ftype]["count"] += 1
        self.categories[ftype]["findings"].append(content)
        self.total_score += score
        self.findings_count += 1

    def display_findings(self):
        if self.silent or not self.categories: return
        self.section("EXTRACTIONS")
        emojis = {"EMAIL": "📧", "INTERNAL_IP": "🌐", "AWS_KEY": "🔑", "HIDDEN_INPUT": "👁️", "SENSITIVE_COMMENT": "💬", "JS_VAR": "📜", "JSON_LD": "📦"}
        for ftype, data in self.categories.items():
            emoji = emojis.get(ftype, "🔍")
            print(f"{emoji} {C.YELLOW}{ftype.upper()}{C.RST} ({C.WHITE}{data['count']}{C.RST})")
            for val in data["findings"]:
                clean_val = val.strip().replace("\n", " ")
                if len(clean_val) > 80: clean_val = clean_val[:77] + "..."
                print(f"   {C.WHITE}{clean_val}{C.RST}")

    def summary(self, filename: str):
        if self.silent: return
        elapsed = time.time() - self.start_time
        self.section("SUMMARY")
        print(f"{C.WHITE}Findings: {C.YELLOW}{self.findings_count}{C.RST} | {C.WHITE}Risk Score: {C.YELLOW}{self.total_score}{C.RST} | {C.WHITE}Time: {C.YELLOW}{elapsed:.2f}s{C.RST}")
        print(f"{C.WHITE}[✓] Output: {C.YELLOW}{filename}{C.RST}\n")

# ── Extraction Matrix ─────────────────────────────────────────────────────────
class ExtractionMatrix:
    PATTERNS = {
        "emails": {"regex": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "score": 1, "label": "EMAIL"},
        "ips": {"regex": r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b', "score": 20, "label": "INTERNAL_IP"},
        "aws_key": {"regex": r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}', "score": 100, "label": "AWS_KEY"},
        "google_api": {"regex": r'AIza[0-9A-Za-z\\-_]{35}', "score": 50, "label": "GOOGLE_API"},
        "github_token": {"regex": r'ghp_[a-zA-Z0-9]{36}', "score": 80, "label": "GITHUB_TOKEN"},
        "slack_token": {"regex": r'xox[baprs]-[0-9a-zA-Z]{10,48}', "score": 70, "label": "SLACK_TOKEN"},
        "slack_webhook": {"regex": r'https:\/\/hooks.slack.com\/services\/T[a-zA-Z0-9_]{8}\/B[a-zA-Z0-9_]{8}\/[a-zA-Z0-9_]{24}', "score": 60, "label": "SLACK_WEBHOOK"}
    }

    @staticmethod
    def extract_from_text(text: str, filters: Set[str]) -> List[Dict[str, Any]]:
        findings = []
        for key, meta in ExtractionMatrix.PATTERNS.items():
            if filters and key not in filters and meta['label'].lower() not in filters:
                continue
            matches = re.findall(meta['regex'], text)
            for match in set(matches):
                findings.append({"type": meta['label'], "content": match, "score": meta['score']})
        return findings

    @staticmethod
    def extract_from_soup(soup: BeautifulSoup, filters: Set[str]) -> List[Dict[str, Any]]:
        findings = []
        if not filters or "hidden" in filters:
            for inp in soup.find_all("input", type="hidden"):
                findings.append({"type": "HIDDEN_INPUT", "content": f"{inp.get('name', 'N/A')}={inp.get('value', 'N/A')}", "score": 5})
        if not filters or "comments" in filters:
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                if any(k in comment.upper() for k in ["TODO", "FIXME", "DEBUG", "HACK", "XXX", "SECRET"]):
                    findings.append({"type": "SENSITIVE_COMMENT", "content": comment.strip(), "score": 10})
        if not filters or "js_vars" in filters:
            for script in soup.find_all("script"):
                if script.string:
                    matches = re.findall(r'(?:var|const|let)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*[\'"]([^\'"]+)[\'"]', script.string)
                    for var_name, var_val in matches:
                        if any(k in var_name.upper() for k in ["KEY", "SECRET", "TOKEN", "PASS", "AUTH", "API"]):
                            findings.append({"type": "JS_VAR", "content": f"{var_name}={var_val}", "score": 30})
        if not filters or "json_ld" in filters:
            for script in soup.find_all("script", type="application/ld+json"):
                if script.string:
                    findings.append({"type": "JSON_LD", "content": script.string.strip()[:200] + "...", "score": 5})
        return findings

# ── Stealth & Evasion ─────────────────────────────────────────────────────────
class StealthManager:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]
    @staticmethod
    def get_random_ua(): return random.choice(StealthManager.USER_AGENTS)
    @staticmethod
    def get_random_viewport(): return {"width": random.randint(1280, 1920), "height": random.randint(720, 1080)}

# ── Recon Engine ──────────────────────────────────────────────────────────────
def run_external_spider(target: str, depth: int, verbose: bool):
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    spider_paths = [os.path.join(_script_dir, "spider.py"), os.path.join(os.path.dirname(_script_dir), "Hellhound-Spider", "spider.py")]
    spider_path = next((p for p in spider_paths if os.path.exists(p)), None)
    
    if not spider_path:
        if verbose: print(f"{C.GRAY}  [!] Spider engine not found. Target only.{C.RST}")
        return [{"url": target, "method": "GET"}]

    if verbose:
        print(f"{C.CYAN}  [#] Launching Hellhound-Spider recon phase...{C.RST}")
        print(f"{C.GRAY}  [#] Mapping attack surface for: {target}{C.RST}")

    temp_json = os.path.join(_script_dir, f".butcher_recon_{int(time.time())}.json")
    cmd = [sys.executable, spider_path, target, "--out", temp_json, "--depth", str(depth)]
    if verbose: cmd.append("--verbose")

    try:
        # If verbose, we allow stdout to show spider progress
        subprocess.run(cmd, check=True, capture_output=not verbose)
        
        if not os.path.exists(temp_json): return [{"url": target, "method": "GET"}]
        with open(temp_json, "r") as f: data = json.load(f)
        os.remove(temp_json)
        
        eps = [{"url": ep["url"], "method": ep.get("methods", ["GET"])[0]} for ep in data.get("endpoints", [])]
        if verbose: print(f"{C.YELLOW}  [✓] Recon complete. {len(eps)} endpoints ingested.{C.RST}\n")
        return eps
    except Exception as e:
        if verbose: print(f"{C.RED}  [!] Recon failed: {e}{C.RST}")
        return [{"url": target, "method": "GET"}]

# ── Scraper Core ──────────────────────────────────────────────────────────────
class ButcherEngine:
    def __init__(self, args):
        self.args = args
        self.findings = []
        self.filters = set(args.extract.split(",")) if args.extract else set()

    async def run(self, hud: ButcherHUD):
        endpoints = run_external_spider(self.args.target, self.args.depth, self.args.verbose)
        total_eps = len(endpoints)
        async with aiohttp.ClientSession(headers={"User-Agent": StealthManager.get_random_ua()}) as session:
            for i, ep in enumerate(endpoints[:self.args.max_pages]):
                url = ep["url"]
                if any(ex in url for ex in self.args.exclude.split(",")): continue
                percent = int(((i + 1) / total_eps) * 100)
                try:
                    results, status, size = await self._scrape_with_meta(url, session)
                    hud.progress(url, code=status, size=size, percent=percent)
                    for res in results:
                        hud.add_finding(res["type"], res["content"], res["score"])
                        self.findings.append(res)
                except:
                    hud.progress(url, code=500, size=0, percent=percent)
        print()
        hud.display_findings()

    async def _scrape_with_meta(self, url: str, session: aiohttp.ClientSession):
        if self.args.browser:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=StealthManager.get_random_ua())
                page = await context.new_page()
                resp = await page.goto(url, timeout=self.args.timeout * 1000)
                html = await page.content()
                status = resp.status if resp else 0
                await browser.close()
                return self.perform_extraction(html), status, len(html)
        else:
            async with session.get(url, timeout=self.args.timeout) as resp:
                html = await resp.text()
                return self.perform_extraction(html), resp.status, len(html)

    def perform_extraction(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        return ExtractionMatrix.extract_from_text(text, self.filters) + ExtractionMatrix.extract_from_soup(soup, self.filters)

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Butcher — Surgical Web Scraper")
    parser.add_argument("target", help="Target URL to scrape")
    parser.add_argument("--browser", action="store_true", help="Use headless browser")
    parser.add_argument("--extract", help="Extraction filters")
    parser.add_argument("--output", help="Save findings to file")
    parser.add_argument("--output-format", choices=["json", "csv", "markdown"], default="json")
    parser.add_argument("--depth", type=int, default=0, help="Crawl depth")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout")
    parser.add_argument("--proxy", help="Proxy URL")
    parser.add_argument("--exclude", default="logout,delete", help="Exclude paths")
    parser.add_argument("--follow-redirects", action="store_true", help="Follow HTTP redirects")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    parser.add_argument("--silent", action="store_true", help="Banner only")
    args = parser.parse_args()

    if not args.target.startswith("http"): args.target = "https://" + args.target
    if not args.output:
        domain = urlparse(args.target).netloc.replace(".", "_")
        args.output = f"butcher_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print_banner()
    if args.silent: sys.exit(0)
    
    hud = ButcherHUD(args.target, args)
    hud.header()
    engine = ButcherEngine(args)
    
    try:
        asyncio.run(engine.run(hud))
        hud.summary(args.output)
        
        if args.output.endswith(".json"):
            with open(args.output, "w") as f: json.dump(engine.findings, f, indent=4)
        print(f"{C.WHITE}[✓] Results saved to {C.YELLOW}{args.output}{C.RST}")
    except KeyboardInterrupt:
        print(f"\n{C.RED}Aborted by user.{C.RST}")
        sys.exit(1)

if __name__ == "__main__":
    main()
