"""
AI Radar Africa - Rule-Based Scoring System
Scores articles using keyword matching and source weighting.
No external API, no API key, no cost.

v2 changes (mirrors scorer.py so both paths behave the same):
  - African source weights added (TechCabal, Techpoint, Disrupt Africa,
    TechMoran, Google News: AI Africa).
  - Articles from African sources (category == "africa") get an
    african_relevance floor of 8.0 — an African tech outlet covering AI
    is African-relevant by definition — plus the same +1.0 final boost.
  - Expanded African keyword dictionary (more countries, companies, hubs).
"""

import json
import logging
import re
from pathlib import Path
from datetime import date, datetime

log = logging.getLogger(__name__)

WEIGHTS = {
    "impact":            0.30,
    "novelty":           0.20,
    "african_relevance": 0.30,
    "job_impact":        0.20,
}

THRESHOLD = 6.0
AFRICA_BOOST = 1.0        # flat final-score bonus for African sources
AFRICA_RELEVANCE_FLOOR = 8.0  # minimum african_relevance for African sources

# ── Keyword dictionaries (tune these freely) ─────────────────────────────────────

IMPACT_TERMS = {
    # high impact (weight 10)
    10: ["foundation model", "gpt-5", "gpt-6", "breakthrough", "new model release",
         "state-of-the-art", "sota", "frontier model", "agi"],
    # medium-high (weight 7)
    7:  ["launches", "releases", "unveils", "announces", "open source", "open-source",
         "benchmark", "research", "paper", "funding round", "raises"],
    # medium (weight 4)
    4:  ["update", "improves", "adds", "feature", "integration", "partnership"],
}

NOVELTY_TERMS = {
    10: ["first", "introducing", "announcing", "launches today", "new", "unveils", "debut"],
    6:  ["expands", "updates", "now available", "general availability"],
    3:  ["analysis", "opinion", "why", "how to", "guide", "explained", "deep dive"],
}

AFRICAN_TERMS = {
    # very high (weight 10)
    10: ["kenya", "nigeria", "africa", "african", "nairobi", "lagos", "ghana",
         "south africa", "rwanda", "egypt", "m-pesa", "safaricom", "flutterwave",
         "ethiopia", "tanzania", "uganda", "senegal", "morocco", "tunisia",
         "ivory coast", "côte d'ivoire", "paystack", "andela", "zindi",
         "instadeep", "mtn", "airtel"],
    # high (weight 8) — emerging markets relevance
    8:  ["emerging market", "global south", "developing", "fintech", "mobile money",
         "remittance", "financial inclusion"],
    # medium (weight 4) — globally relevant trends
    4:  ["jobs", "hiring", "remote work", "freelance", "upskilling", "training",
         "data science", "machine learning", "automation"],
}

JOB_IMPACT_TERMS = {
    9:  ["automates", "replaces", "no-code", "low-code", "agent", "autonomous",
         "copilot", "assistant", "productivity"],
    6:  ["tool", "platform", "api", "workflow", "framework", "library",
         "data engineer", "data scientist", "developer"],
    3:  ["report", "survey", "study", "trend", "outlook"],
}

# Source quality multipliers — trusted primary sources score higher on novelty/impact
SOURCE_WEIGHTS = {
    "Anthropic":        1.2,
    "OpenAI Blog":      1.2,
    "Google DeepMind":  1.2,
    "Meta AI":          1.1,
    "Hugging Face":     1.1,
    "TechCrunch AI":    1.0,
    "Papers With Code": 1.0,
    "KDnuggets":        0.9,
    "Zapier Blog":      0.9,
    # African sources — trusted primary coverage of the beat that matters most
    "TechCabal":              1.2,
    "Techpoint Africa":       1.2,
    "Disrupt Africa":         1.2,
    "TechMoran":              1.1,
    "Techweez":               1.1,
    "Ventureburn":            1.1,
    "Google News: AI Africa": 1.0,
}


def _score_dimension(text: str, term_map: dict) -> float:
    """Return the highest matching weight for any term found in text."""
    text_low = text.lower()
    best = 0.0
    for weight, terms in term_map.items():
        for term in terms:
            if term in text_low:
                best = max(best, float(weight))
                break  # one hit per tier is enough
    return best


def score_article(article: dict) -> dict:
    """Score a single article using keyword rules. No API call."""
    text = f"{article.get('title', '')} {article.get('summary', '')}"

    impact   = _score_dimension(text, IMPACT_TERMS)
    novelty  = _score_dimension(text, NOVELTY_TERMS)
    african  = _score_dimension(text, AFRICAN_TERMS)
    job      = _score_dimension(text, JOB_IMPACT_TERMS)

    # Apply source quality multiplier to impact + novelty, capped at 10
    src_mult = SOURCE_WEIGHTS.get(article.get("source", ""), 1.0)
    impact  = min(10.0, impact * src_mult)
    novelty = min(10.0, novelty * src_mult)

    # African-source floor: an African tech outlet covering AI is
    # African-relevant by definition, even without keyword matches.
    is_african_source = article.get("category") == "africa"
    if is_african_source:
        african = max(african, AFRICA_RELEVANCE_FLOOR)

    scores = {
        "impact":            round(impact, 1),
        "novelty":           round(novelty, 1),
        "african_relevance": round(african, 1),
        "job_impact":        round(job, 1),
    }

    final = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    # Mirror scorer.py's deterministic boost so both paths rank alike
    if is_african_source:
        final = min(10.0, final + AFRICA_BOOST)

    scores["final_score"] = round(final, 2)
    scores["passes_threshold"] = final >= THRESHOLD

    # Build a human-readable reason
    parts = []
    if is_african_source: parts.append("African source")
    if african >= 8:  parts.append("strong African relevance")
    if impact >= 7:   parts.append("high impact")
    if novelty >= 8:  parts.append("breaking/new")
    if job >= 6:      parts.append("affects tech workflows")
    scores["one_line_reason"] = ", ".join(parts) if parts else "general interest"

    return scores


def score_all(articles: list[dict]) -> list[dict]:
    """Score all articles, return sorted by final_score descending."""
    log.info(f"Scoring {len(articles)} articles (rule-based, no API)…")
    scored = []
    for article in articles:
        s = score_article(article)
        scored.append({**article, **s})
    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored


def filter_top_stories(scored: list[dict], top_n: int = 10) -> list[dict]:
    passing = [a for a in scored if a.get("passes_threshold")]
    log.info(f"{len(passing)} articles passed threshold ({THRESHOLD}+) out of {len(scored)}")
    return passing[:top_n]


def save_scored(scored: list[dict], output_dir: str = "outputs") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = f"{output_dir}/scored_{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, default=str)
    log.info(f"Saved scored articles → {path}")
    return path


if __name__ == "__main__":
    import sys

    articles_path = f"outputs/articles_{date.today()}.json"
    if not Path(articles_path).exists():
        print(f"No articles file found at {articles_path}. Run scraper.py first.")
        sys.exit(1)

    with open(articles_path) as f:
        articles = json.load(f)

    scored = score_all(articles)
    path = save_scored(scored)

    top = filter_top_stories(scored, top_n=5)
    print(f"\n✅ Scored {len(scored)} articles. Top stories:")
    for a in top:
        print(f"  [{a['final_score']:.1f}] {a['source']}: {a['title'][:65]}")
        print(f"       → {a.get('one_line_reason', '')}")
