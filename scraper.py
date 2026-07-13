"""
AI Radar Africa - Feed Scraper
Pulls articles from core global + African sources via RSS + web scraping.

v2 changes:
  - Added African tech sources (category "africa") — TechCabal, Techpoint,
    Disrupt Africa, TechMoran + a Google News query for African AI stories.
  - URL normalization before hashing (strips ?utm_... params) so the same
    story shared with different tracking links dedupes correctly.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── RSS Sources ────────────────────────────────────────────────────────────────
SOURCES = [
    # AI Labs
    {"name": "Anthropic",       "url": "https://www.anthropic.com/rss.xml",                    "category": "ai_lab"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml",                 "category": "ai_lab"},
    {"name": "Meta AI",         "url": "https://ai.meta.com/blog/feed/",                       "category": "ai_lab"},
    # Data Science & ML
    {"name": "Hugging Face",    "url": "https://huggingface.co/blog/feed.xml",                 "category": "ml"},
    {"name": "KDnuggets",       "url": "https://www.kdnuggets.com/feed",                       "category": "data_science"},
    # Automation
    {"name": "Zapier Blog",     "url": "https://zapier.com/blog/feeds/latest/",               "category": "automation"},
    # Funding & Startups
    {"name": "TechCrunch AI",   "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "startups"},
    # Research
    {"name": "Papers With Code","url": "https://paperswithcode.com/latest.rss",               "category": "research"},

    # African Tech — the differentiator. Category "africa" gets a scoring boost.
    {"name": "TechCabal",        "url": "https://techcabal.com/feed/",       "category": "africa"},
    {"name": "Techpoint Africa", "url": "https://techpoint.africa/feed/",    "category": "africa"},
    {"name": "Disrupt Africa",   "url": "https://disrupt-africa.com/feed/",  "category": "africa"},
    {"name": "TechMoran",        "url": "https://techmoran.com/feed/",       "category": "africa"},
    {"name": "Google News: AI Africa",
     "url": "https://news.google.com/rss/search?q=%22artificial+intelligence%22+Africa+startup",
     "category": "africa"},
    # Easy adds when you want more volume (uncomment to enable):
    # {"name": "Techweez",     "url": "https://techweez.com/feed/",    "category": "africa"},
    # {"name": "Ventureburn",  "url": "https://ventureburn.com/feed/", "category": "africa"},
]

# OpenAI blog doesn't have RSS; we scrape it directly
SCRAPE_SOURCES = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news", "category": "ai_lab"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# ── Helpers ────────────────────────────────────────────────────────────────────

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "fbclid", "gclid", "ref"}


def normalize_url(url: str) -> str:
    """Strip tracking params so the same story dedupes across share links."""
    try:
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if k.lower() not in TRACKING_PARAMS]
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(query), ""))
    except Exception:
        return url


def article_id(url: str) -> str:
    """Stable ID for deduplication (computed on the normalized URL)."""
    return hashlib.md5(normalize_url(url).encode()).hexdigest()[:12]


def clean_html(raw: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    return " ".join(text.split())[:800]   # cap at 800 chars for scoring prompts


def parse_date(entry) -> str:
    """Best-effort ISO date from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


# ── RSS Puller ─────────────────────────────────────────────────────────────────

def pull_rss(source: dict, max_items: int = 5) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    log.info(f"  Fetching RSS: {source['name']}")
    try:
        feed = feedparser.parse(source["url"])
        articles = []
        for entry in feed.entries[:max_items]:
            url = entry.get("link", "")
            if not url:
                continue
            summary_raw = (
                entry.get("summary", "")
                or entry.get("description", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
            articles.append({
                "id":       article_id(url),
                "title":    entry.get("title", "").strip(),
                "url":      url,
                "summary":  clean_html(summary_raw),
                "source":   source["name"],
                "category": source["category"],
                "date":     parse_date(entry),
            })
        log.info(f"    → {len(articles)} articles")
        return articles
    except Exception as e:
        log.warning(f"    RSS error for {source['name']}: {e}")
        return []


# ── Web Scraper (OpenAI) ───────────────────────────────────────────────────────

def scrape_openai(source: dict, max_items: int = 5) -> list[dict]:
    """Scrape OpenAI news page (no RSS available)."""
    log.info(f"  Scraping: {source['name']}")
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        articles = []
        # OpenAI uses anchor tags with article links
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/"):
                continue
            if not any(seg in href for seg in ["/research/", "/blog/", "/index/"]):
                continue
            full_url = "https://openai.com" + href
            if full_url in seen:
                continue
            seen.add(full_url)

            title_tag = a.find(["h2", "h3", "h4", "span", "p"])
            title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append({
                "id":       article_id(full_url),
                "title":    title,
                "url":      full_url,
                "summary":  "",          # fetched separately if needed
                "source":   source["name"],
                "category": source["category"],
                "date":     datetime.now(timezone.utc).isoformat(),
            })
            if len(articles) >= max_items:
                break

        log.info(f"    → {len(articles)} articles")
        return articles
    except Exception as e:
        log.warning(f"    Scrape error for {source['name']}: {e}")
        return []


# ── Deduplication ──────────────────────────────────────────────────────────────

def deduplicate(articles: list[dict]) -> list[dict]:
    seen_ids = set()
    seen_titles = set()
    unique = []
    for a in articles:
        title_key = a["title"].lower()[:60]
        if a["id"] in seen_ids or title_key in seen_titles:
            continue
        seen_ids.add(a["id"])
        seen_titles.add(title_key)
        unique.append(a)
    return unique


# ── Main ───────────────────────────────────────────────────────────────────────

def run_scraper(max_per_source: int = 5) -> list[dict]:
    log.info("=== AI Radar Africa — Scraper Starting ===")
    all_articles = []

    for source in SOURCES:
        all_articles.extend(pull_rss(source, max_per_source))

    for source in SCRAPE_SOURCES:
        all_articles.extend(scrape_openai(source, max_per_source))

    unique = deduplicate(all_articles)
    n_africa = sum(1 for a in unique if a.get("category") == "africa")
    log.info(f"Total after dedup: {len(unique)} articles (from {len(all_articles)} raw, {n_africa} African)")
    return unique


def save_articles(articles: list[dict], output_dir: str = "outputs") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = f"{output_dir}/articles_{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, default=str)
    log.info(f"Saved {len(articles)} articles → {path}")
    return path


if __name__ == "__main__":
    articles = run_scraper()
    save_articles(articles)
    print(f"\n✅ Scraped {len(articles)} unique articles")
    for a in articles[:5]:
        print(f"  [{a['source']}] {a['title'][:70]}")
