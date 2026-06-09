"""
AI Radar Africa - Template-Based Brief Generator
Builds the daily brief from scored articles using string templates.
No external API, no API key, no cost.
"""

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

TIER_LABELS = ["🔴 TOP STORY", "🟡 SECONDARY STORY", "🟢 EMERGING TREND"]


def _story_block(label: str, a: dict) -> str:
    return f"""{label}
Title: {a['title']}
Score: {a['final_score']:.1f}/10
Source: {a['source']}  |  {a['url']}
What happened: {a.get('summary', 'See source for details.')[:280]}
Why it matters: {a.get('one_line_reason', 'Relevant to tech professionals.').capitalize()}.
African angle: {_african_angle(a)}
Your move: {_your_move(a)}
"""


def _african_angle(a: dict) -> str:
    if a.get("african_relevance", 0) >= 8:
        return "Directly relevant to the Kenyan/African tech ecosystem — watch for local opportunities."
    if a.get("african_relevance", 0) >= 4:
        return "A global trend African data professionals should track and adapt early."
    return "Background context for staying current on global AI direction."


def _your_move(a: dict) -> str:
    if a.get("job_impact", 0) >= 6:
        return "Explore how this tool/skill could slot into your workflow this week."
    if a.get("novelty", 0) >= 8:
        return "Read the source while it's fresh — early movers get the edge."
    return "Bookmark for context; revisit if it gains traction."


def generate_brief(top_stories: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    stories = top_stories[:3]

    # ── Brief section ──
    brief = f"---AI RADAR AFRICA BRIEF---\nDate: {today}\n\n"
    for i, a in enumerate(stories):
        label = TIER_LABELS[i] if i < len(TIER_LABELS) else "📌 ALSO NOTED"
        brief += _story_block(label, a) + "\n"

    # ── Podcast script ──
    titles = [a["title"] for a in stories]
    brief += "---PODCAST SCRIPT---\n"
    brief += f"Episode Title: The Week in AI — {titles[0][:50] if titles else 'Top Trends'}\n\n"
    brief += "Intro (30 sec):\n"
    brief += f"This week, {titles[0] if titles else 'big moves in AI'}. Here's why it matters for African tech pros.\n\n"
    for i, a in enumerate(stories[:2], 1):
        brief += f"Segment {i} — {a['title'][:50]} (2 min):\n"
        brief += f"- What happened: {a.get('summary', '')[:150]}\n"
        brief += f"- Why it matters: {a.get('one_line_reason', '')}\n"
        brief += f"- Your move: {_your_move(a)}\n\n"
    brief += "Segment 3 — African Angle (1 min):\n"
    brief += "What's moving in Kenya/Africa this week — jobs, funding, and policy worth watching.\n\n"
    brief += "Outro (30 sec):\n"
    brief += "Subscribe for weekly AI trends. Follow @jowac254 on TikTok. See you next week.\n\n"

    # ── LinkedIn post ──
    brief += "---LINKEDIN POST---\n"
    brief += "What in AI actually matters for your role this week? Here are 3:\n\n"
    for i, a in enumerate(stories, 1):
        brief += f"{i}. {a['title']} — {a.get('one_line_reason', 'worth a look')}.\n"
    brief += "\nWhat are you seeing in your network?\n\n"
    brief += "#AI #DataScience #AfricaTech #Kenya #MLAfrica\n"

    return brief


def save_brief(brief_text: str, output_dir: str = "outputs") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    date_str = date.today().strftime("%Y-%m-%d")
    path = f"{output_dir}/brief_{date_str}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(brief_text)
    log.info(f"Saved brief → {path}")
    return path


if __name__ == "__main__":
    import sys
    from scorer_rulebased import filter_top_stories

    scored_path = f"outputs/scored_{date.today()}.json"
    if not Path(scored_path).exists():
        print(f"No scored file at {scored_path}. Run scorer_rulebased.py first.")
        sys.exit(1)

    with open(scored_path) as f:
        scored = json.load(f)

    top = filter_top_stories(scored, top_n=5)
    brief = generate_brief(top)
    save_brief(brief)
    print("\n✅ Brief generated (no API):\n")
    print(brief)
