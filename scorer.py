"""
AI Radar Africa - Scoring System
Uses Claude API to score each article on 4 dimensions.
Filters to top stories for the daily brief.
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime

import anthropic

from cost_tracker import tracker

log = logging.getLogger(__name__)

# Weighted scoring formula from brief
WEIGHTS = {
    "impact":            0.30,
    "novelty":           0.20,
    "african_relevance": 0.30,
    "job_impact":        0.20,
}

THRESHOLD = 6.0   # minimum score to make the daily brief

SCORING_PROMPT = """You are an AI trend analyst for Africa. Score this article for an African tech professional audience.

Article:
Title: {title}
Source: {source}
Summary: {summary}

Score each dimension 0-10 using these criteria:

IMPACT (0-10): How game-changing is this?
- 9-10: New foundation model, major breakthrough, paradigm shift
- 6-8: Significant tool release, important research finding
- 3-5: Tool update, incremental improvement
- 0-2: Minor news, opinion piece

NOVELTY (0-10): How new is this information?
- 9-10: First announcement, breaking news
- 5-7: Early coverage of a new development
- 2-4: Follow-up coverage, analysis of known news
- 0-1: Old news, repeat coverage

AFRICAN_RELEVANCE (0-10): Relevance to African/Kenyan tech professionals
- 9-10: AI jobs opening in Africa/Kenya, African startup funding
- 7-9: Policy/regulation directly affecting African tech
- 4-6: Global trend clearly relevant to African data scientists/engineers
- 1-3: Tangentially relevant
- 0: No African relevance

JOB_IMPACT (0-10): Will this change workflows for data scientists, engineers, or PMs?
- 9-10: Directly automates or transforms core job tasks
- 6-8: New tool/capability that changes how professionals work
- 3-5: Worth knowing, minor workflow change
- 0-2: No professional workflow impact

Respond ONLY with valid JSON (no markdown, no explanation):
{{"impact": <0-10>, "novelty": <0-10>, "african_relevance": <0-10>, "job_impact": <0-10>, "one_line_reason": "<why this scored as it did>"}}"""


def score_article(client: anthropic.Anthropic, article: dict, retries: int = 2) -> dict:
    """Score a single article using Claude API."""
    prompt = SCORING_PROMPT.format(
        title=article.get("title", ""),
        source=article.get("source", ""),
        summary=article.get("summary", "No summary available.")[:600],
    )

    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            tracker.record(response, label="score")
            raw = response.content[0].text.strip()

            # Strip any accidental markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            scores = json.loads(raw)

            # Validate keys exist
            for key in ["impact", "novelty", "african_relevance", "job_impact"]:
                scores[key] = float(scores.get(key, 0))

            # Compute weighted final score
            final = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
            scores["final_score"] = round(final, 2)
            scores["passes_threshold"] = final >= THRESHOLD
            return scores

        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error on attempt {attempt+1}: {e} | raw={raw[:100]}")
            if attempt < retries:
                time.sleep(1)
        except Exception as e:
            log.warning(f"Scoring API error attempt {attempt+1}: {e}")
            if attempt < retries:
                time.sleep(2)

    # Fallback: neutral score so article isn't silently dropped
    return {
        "impact": 0, "novelty": 0, "african_relevance": 0, "job_impact": 0,
        "final_score": 0.0, "passes_threshold": False,
        "one_line_reason": "Scoring failed — skipped."
    }


def score_all(articles: list[dict], api_key: str = None) -> list[dict]:
    """Score all articles, return sorted by final_score descending."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=api_key)
    scored = []

    log.info(f"Scoring {len(articles)} articles…")
    for i, article in enumerate(articles, 1):
        log.info(f"  [{i}/{len(articles)}] {article['title'][:60]}")
        scores = score_article(client, article)
        article_scored = {**article, **scores}
        scored.append(article_scored)
        # Respect rate limits
        time.sleep(0.5)

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored


def filter_top_stories(scored: list[dict], top_n: int = 10) -> list[dict]:
    """Return only articles that pass the threshold, up to top_n."""
    passing = [a for a in scored if a.get("passes_threshold")]
    log.info(f"{len(passing)} articles passed threshold ({THRESHOLD}+) out of {len(scored)}")
    return passing[:top_n]


def save_scored(scored: list[dict], output_dir: str = "outputs") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = f"{output_dir}/scored_{date_str}.json"
    with open(path, "w") as f:
        json.dump(scored, f, indent=2, default=str)
    log.info(f"Saved scored articles → {path}")
    return path


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Load today's articles
    from datetime import date
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
