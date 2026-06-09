"""
AI Radar Africa - Brief Generator
Takes top scored articles → generates daily brief (email + podcast script + LinkedIn post).
"""

import os
import json
import logging
from datetime import date, datetime
from pathlib import Path

import anthropic

from cost_tracker import tracker

log = logging.getLogger(__name__)

BRIEF_PROMPT = """You are John Wachira's AI content assistant for "AI Radar Africa" — a daily intelligence brief for African tech professionals.

Today's date: {today}
Top scored stories (JSON):
{stories_json}

Generate the daily brief in EXACTLY this format (use the exact section headers):

---AI RADAR AFRICA BRIEF---
Date: {today}

🔴 TOP STORY
Title: [title]
Score: [score]/10
What happened: [2-3 sentences, plain language]
Why it matters: [impact for data scientists / engineers / PMs]
African angle: [why Kenya or Africa should care — be specific]
Your move: [one concrete action the reader can take]

🟡 SECONDARY STORY
Title: [title]
Score: [score]/10
What happened: [2-3 sentences]
Why it matters: [impact]
African angle: [African/Kenyan relevance]
Your move: [action]

🟢 EMERGING TREND
Title: [title]
Score: [score]/10
What happened: [2-3 sentences]
Why it matters: [impact]
African angle: [African/Kenyan relevance]
Your move: [action]

---PODCAST SCRIPT---
Episode Title: [catchy title based on top stories]

Intro (30 sec):
[Hook sentence. "This week, [top story hook]. Here's why it matters for African tech pros."]

Segment 1 — [Story 1 Title] (2 min):
- What happened: [talking point]
- Why it matters: [talking point]
- Who wins / who loses: [talking point]
- Your move: [talking point]

Segment 2 — [Story 2 Title] (2 min):
- What happened: [talking point]
- Why it matters: [talking point]
- Who wins / who loses: [talking point]
- Your move: [talking point]

Segment 3 — African Angle (1 min):
[What's happening in Kenya/Africa this week related to these trends. Job market angle. Policy angle.]

Outro (30 sec):
Subscribe for weekly AI trends. Follow @jowac254 on TikTok for daily clips. See you next week.

---LINKEDIN POST---
[Hook — bold question or statement]

3 things happening in AI this week that matter for your role:

1. [Story 1 headline + 1 sentence take]
2. [Story 2 headline + 1 sentence take]
3. [Story 3 headline + 1 sentence take]

[1 question CTA for engagement]

#AI #DataScience #AfricaTech #Kenya #MLAfrica

Tone: formal-conversational, story-driven, actionable. Audience: African tech professionals and job seekers."""


def generate_brief(top_stories: list[dict], api_key: str = None) -> str:
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)

    # Trim stories to essential fields to keep prompt lean
    stories_slim = [
        {
            "title":            a["title"],
            "source":           a["source"],
            "url":              a["url"],
            "summary":          a.get("summary", "")[:400],
            "final_score":      a["final_score"],
            "one_line_reason":  a.get("one_line_reason", ""),
        }
        for a in top_stories[:5]
    ]

    prompt = BRIEF_PROMPT.format(
        today=date.today().strftime("%B %d, %Y"),
        stories_json=json.dumps(stories_slim, indent=2),
    )

    log.info("Generating daily brief via Claude API…")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )
    tracker.record(response, label="brief")

    return response.content[0].text.strip()


def save_brief(brief_text: str, output_dir: str = "outputs") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    date_str = date.today().strftime("%Y-%m-%d")
    path = f"{output_dir}/brief_{date_str}.txt"
    with open(path, "w") as f:
        f.write(brief_text)
    log.info(f"Saved brief → {path}")
    return path


def extract_section(brief_text: str, section_marker: str) -> str:
    """Pull a named section from the brief for separate use."""
    parts = brief_text.split("---")
    for i, part in enumerate(parts):
        if section_marker.upper() in part.upper():
            # Return the content between this marker and the next
            content_parts = part.split("\n", 1)
            return content_parts[1].strip() if len(content_parts) > 1 else part.strip()
    return ""


if __name__ == "__main__":
    import sys
    from scorer import filter_top_stories

    scored_path = f"outputs/scored_{date.today()}.json"
    if not Path(scored_path).exists():
        print(f"No scored file at {scored_path}. Run scorer.py first.")
        sys.exit(1)

    with open(scored_path) as f:
        scored = json.load(f)

    top = filter_top_stories(scored, top_n=5)
    brief = generate_brief(top)
    path = save_brief(brief)

    print(f"\n✅ Brief generated → {path}")
    print("\n" + "="*60)
    print(brief[:800] + "…")
