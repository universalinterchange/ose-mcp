import hashlib
import os
import time
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://oldschoolessentials.necroticgnome.com/srd/index.php/"
START = urljoin(BASE, "Main_Page")

CACHE_DIR = Path(os.environ.get("OSE_MCP_CACHE", "data/ose_srd_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def is_in_scope(url: str) -> bool:
    u = urlparse(url)
    if u.netloc != "oldschoolessentials.necroticgnome.com":
        return False
    if not u.path.startswith("/srd/index.php/"):
        return False

    # Page title is the part after /index.php/
    page = unquote(u.path.split("/srd/index.php/", 1)[1])

    # Skip MediaWiki utility namespaces
    if page.startswith("Special:"):
        return False
    if page.startswith("File:") or page.startswith("Image:"):
        return False
    if page.startswith("Help:") or page.startswith("Category:"):
        return False
    if page.startswith("Template:"):
        return False

    return True

def cache_name(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{h}.html"

def fetch(url: str, delay_s: float = 0.5) -> str | None:
    p = cache_name(url)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")

    try:
        r = requests.get(url, timeout=30)
        # If it’s a 404 or other error, skip it
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException:
        return None

    text = r.text
    p.write_text(text, encoding="utf-8")
    time.sleep(delay_s)
    return text

def is_in_scope(url: str) -> bool:
    u = urlparse(url)
    return u.netloc == "oldschoolessentials.necroticgnome.com" and u.path.startswith("/srd/index.php/")

def normalize(url: str) -> str:
    # strip fragments
    return url.split("#", 1)[0]

def extract_title_and_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled"

    # MediaWiki content is usually in #mw-content-text
    content = soup.select_one("#mw-content-text") or soup.body
    # remove nav / scripts
    for t in content.select("script, style, noscript"):
        t.decompose()

    text = content.get_text("\n", strip=True)
    # collapse excessive blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return title, "\n".join(lines)

def crawl(max_pages: int = 300, delay_s: float = 0.5):
    seen = set()
    q = [START]

    pages = []
    while q and len(pages) < max_pages:
        url = normalize(q.pop(0))
        if url in seen or not is_in_scope(url):
            continue
        seen.add(url)

        html = fetch(url, delay_s=delay_s)
        if not html:
            continue
        title, text = extract_title_and_text(html)
        pages.append((url, title, text))

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            nxt = normalize(urljoin(url, href))
            if is_in_scope(nxt) and nxt not in seen:
                q.append(nxt)

    return pages

if __name__ == "__main__":
    pages = crawl(max_pages=int(os.environ.get("OSE_MCP_MAXPAGES", "300")),
                  delay_s=float(os.environ.get("OSE_MCP_DELAY", "0.5")))
    print(f"Crawled {len(pages)} pages into cache dir: {CACHE_DIR}")

