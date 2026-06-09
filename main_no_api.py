"""
AI Radar Africa - Main Pipeline
Run this to execute the full daily pipeline:
  1. Scrape all sources
  2. Score articles with Claude
  3. Generate daily brief
  4. Email via Gmail

Usage:
  python main.py                    # full pipeline
  python main.py --scrape-only      # just scrape
  python main.py --no-email         # skip email (useful for testing)
  python main.py --use-cached       # skip scrape, use today's cached articles
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 so emoji/arrows in log messages don't crash Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Create folders BEFORE logging is configured (the log file lives in logs/)
Path("logs").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/pipeline_{date.today()}.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


def run(args):
    today = date.today()
    articles_path = f"outputs/articles_{today}.json"
    scored_path   = f"outputs/scored_{today}.json"
    brief_path    = f"outputs/brief_{today}.txt"

    # ── Step 1: Scrape ─────────────────────────────────────────────────────────
    if args.use_cached and Path(articles_path).exists():
        log.info(f"Using cached articles: {articles_path}")
        with open(articles_path) as f:
            articles = json.load(f)
    else:
        log.info("Step 1/4 — Scraping sources…")
        from scraper import run_scraper, save_articles
        articles = run_scraper(max_per_source=5)
        save_articles(articles)
        log.info(f"  Scraped {len(articles)} unique articles")

    if args.scrape_only:
        log.info("--scrape-only flag set. Stopping after scrape.")
        return

    if not articles:
        log.error("No articles found. Check network / sources.")
        sys.exit(1)

    # ── Step 2: Score ──────────────────────────────────────────────────────────
    log.info("Step 2/4 — Scoring articles…")
    from scorer_rulebased import score_all, filter_top_stories, save_scored
    scored = score_all(articles)  # rule-based, no API
    save_scored(scored)

    top_stories = filter_top_stories(scored, top_n=5)
    if not top_stories:
        log.warning("No articles passed the threshold. Lowering to top 3 regardless.")
        top_stories = scored[:3]

    log.info(f"  Top story: [{top_stories[0]['final_score']:.1f}] {top_stories[0]['title'][:60]}")

    # ── Step 3: Generate brief ─────────────────────────────────────────────────
    log.info("Step 3/4 — Generating daily brief…")
    from brief_generator_template import generate_brief, save_brief
    brief_text = generate_brief(top_stories)
    save_brief(brief_text)
    log.info(f"  Brief saved → {brief_path}")

    # ── Step 4: Send email ─────────────────────────────────────────────────────
    if args.no_email:
        log.info("--no-email flag set. Skipping Gmail delivery.")
    else:
        log.info("Step 4/4 — Sending via Gmail…")
        recipient = os.environ.get("BRIEF_RECIPIENT", "")
        sender    = os.environ.get("GMAIL_SENDER", "")
        if not recipient:
            log.error("BRIEF_RECIPIENT not set in .env. Skipping email.")
        else:
            from email_sender import send_brief
            send_brief(brief_text, to_email=recipient, from_email=sender)
            log.info(f"  Brief emailed to {recipient}")

    log.info("=== Pipeline complete ===")
    print(f"\n✅ Done! Brief saved to {brief_path}")
    if top_stories:
        print(f"\nTop 3 stories today:")
        for a in top_stories[:3]:
            print(f"  [{a['final_score']:.1f}] {a['source']}: {a['title'][:65]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Radar Africa Pipeline")
    parser.add_argument("--scrape-only",  action="store_true", help="Only run the scraper")
    parser.add_argument("--no-email",     action="store_true", help="Skip email delivery")
    parser.add_argument("--use-cached",   action="store_true", help="Use today's cached articles (skip scrape)")
    args = parser.parse_args()
    run(args)
