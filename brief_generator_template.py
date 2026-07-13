"""
AI Radar Africa - Template-Based Brief Generator (v2)
Builds the daily brief from scored articles using string templates.
No external API, no API key, no cost.

v2 changes:
  - Richer story blocks: longer summaries, score breakdowns, and varied
    "African angle" / "Your move" notes keyed to each story's category
    and scores (no more identical boilerplate on every story).
  - LinkedIn post rebuilt: hook, per-story takeaways drawn from actual
    summaries, a "Radar take" line, engagement question, tuned hashtags.
  - NEW Instagram section: ready-to-paste caption + a carousel slide
    outline (design the slides in Canva from the outline).
  - Deterministic variety: phrasing rotates based on the story ID, so
    every day reads slightly differently without any API call.
"""

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

TIER_LABELS = ["🔴 TOP STORY", "🟡 SECONDARY STORY", "🟢 EMERGING TREND"]

# Handles used in CTAs — update in one place
TIKTOK_HANDLE = "@jowac254"
IG_HANDLE = "@jowac254"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pick(options: list[str], a: dict) -> str:
    """Deterministic variety: same story always gets the same phrasing,
    but different stories (and days) rotate through the pool."""
    key = a.get("id", a.get("title", ""))
    return options[sum(ord(c) for c in str(key)) % len(options)]


def _first_sentence(text: str, max_len: int = 160) -> str:
    """Pull a clean first sentence from a summary for one-line takeaways."""
    if not text:
        return "Details at the source."
    for sep in [". ", "? ", "! "]:
        if sep in text:
            text = text.split(sep)[0] + sep.strip()
            break
    return text[:max_len].rstrip() + ("…" if len(text) > max_len else "")


def _african_angle(a: dict) -> str:
    cat = a.get("category", "")
    afr = a.get("african_relevance", 0)

    if cat == "africa":
        return _pick([
            "This is homegrown news — African builders are shipping, and stories like this shape what investors and policymakers expect from the ecosystem.",
            "African tech media covered this first. Watch which local players respond — partnerships and hiring often follow within weeks.",
            "A signal from within the continent's own ecosystem: momentum here compounds into funding, jobs, and copycat opportunities in neighbouring markets.",
        ], a)
    if afr >= 8:
        return _pick([
            "Direct implications for African markets — expect ripple effects on local pricing, hiring, or regulation.",
            "This lands squarely in the African tech conversation. The gap between global announcement and local adoption is where opportunity lives.",
        ], a)
    if afr >= 4:
        return _pick([
            "A global shift African data professionals should track — the tools and skills involved will show up in job descriptions here within months.",
            "Not an African story yet, but the second-order effects (cheaper tools, new APIs, remote roles) usually reach Nairobi and Lagos fast.",
        ], a)
    return "Background context — worth knowing to stay fluent in where global AI is heading."


def _your_move(a: dict) -> str:
    cat = a.get("category", "")
    title_sum = f"{a.get('title','')} {a.get('summary','')}".lower()

    if "funding" in title_sum or "raises" in title_sum:
        return _pick([
            "Founders: study what this team pitched and to whom — the investors behind this round are actively deploying in the region.",
            "If you're building in an adjacent space, this round is your proof-of-market slide. Note the investors' names.",
        ], a)
    if "policy" in title_sum or "regulat" in title_sum or "government" in title_sum:
        return _pick([
            "If your product touches this space, read the actual policy text, not just the coverage — compliance early is a moat.",
            "Policy moves slower than tech but hits harder. Worth 15 minutes to understand what's actually changing.",
        ], a)
    if a.get("job_impact", 0) >= 6:
        return _pick([
            "Try the tool this week — even a 30-minute test tells you whether it belongs in your workflow before your competitors decide for you.",
            "Add this to your learning list. Skills attached to fresh tools command premium rates while they're scarce.",
            "Pilot it on one real task. If it saves an hour, it earns a permanent slot in your stack.",
        ], a)
    if a.get("novelty", 0) >= 8:
        return _pick([
            "Read the source while it's fresh — being able to explain this before your peers is quiet career capital.",
            "Early awareness is the edge here. Skim the original announcement, not just the headlines.",
        ], a)
    return _pick([
        "Bookmark for context; revisit if it gains traction.",
        "No action needed today — file it under 'trends to watch'.",
    ], a)


def _score_breakdown(a: dict) -> str:
    return (f"Impact {a.get('impact', 0):.0f} · Novelty {a.get('novelty', 0):.0f} · "
            f"African relevance {a.get('african_relevance', 0):.0f} · "
            f"Job impact {a.get('job_impact', 0):.0f}")


def _story_block(label: str, a: dict) -> str:
    return f"""{label}
Title: {a['title']}
Score: {a['final_score']:.1f}/10  ({_score_breakdown(a)})
Source: {a['source']}  |  {a['url']}
What happened: {a.get('summary', 'See source for details.')[:420]}
Why it matters: {a.get('one_line_reason', 'Relevant to tech professionals.').capitalize()}.
African angle: {_african_angle(a)}
Your move: {_your_move(a)}
"""


# ── Main generator ─────────────────────────────────────────────────────────────

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
        brief += f"- What happened: {a.get('summary', '')[:200]}\n"
        brief += f"- Why it matters: {a.get('one_line_reason', '')}\n"
        brief += f"- African angle: {_african_angle(a)}\n"
        brief += f"- Your move: {_your_move(a)}\n\n"
    brief += "Segment 3 — African Angle (1 min):\n"
    brief += "What's moving in Kenya/Africa this week — jobs, funding, and policy worth watching.\n\n"
    brief += "Outro (30 sec):\n"
    brief += f"Subscribe for weekly AI trends. Follow {TIKTOK_HANDLE} on TikTok. See you next week.\n\n"

    # ── LinkedIn post ──
    top = stories[0] if stories else {}
    hook = _pick([
        f"Most AI news doesn't matter for your career. These 3 stories do ({today}):",
        f"3 AI developments African tech professionals should actually care about this week:",
        f"I filter hundreds of AI stories daily so you don't have to. Today's 3 that matter:",
        f"AI moves fast. Here's what changed for African tech this week — in 60 seconds:",
    ], top)

    brief += "---LINKEDIN POST---\n"
    brief += hook + "\n\n"
    for i, a in enumerate(stories, 1):
        brief += f"{i}️⃣ {a['title']}\n"
        brief += f"→ {_first_sentence(a.get('summary', ''))}\n"
        brief += f"→ {_your_move(a)}\n\n"
    if stories:
        brief += f"📡 Radar take: {_african_angle(stories[0])}\n\n"
    brief += _pick([
        "Which of these hits closest to your work? 👇",
        "What's on your radar that I missed? Drop it below 👇",
        "Are you already using any of these? Tell me how 👇",
    ], top) + "\n\n"
    brief += "♻️ Repost to help a colleague stay ahead.\n\n"
    brief += "#AI #ArtificialIntelligence #AfricaTech #DataScience #Kenya #TechAfrica #MLAfrica #FutureOfWork\n\n"

    # ── Instagram post ──
    brief += "---INSTAGRAM POST---\n"
    brief += "CAPTION:\n"
    brief += _pick([
        f"🌍 Your AI radar for {today} — the 3 stories African tech pros need today 🇰🇪⬇️",
        f"📡 While you slept, AI moved. Here's what matters for Africa today ({today}) ⬇️",
        f"🚨 {today}: 3 AI stories with real implications for African tech ⬇️",
    ], top) + "\n\n"
    for i, a in enumerate(stories, 1):
        brief += f"{i}. {a['title'][:80]}\n"
        brief += f"   {_first_sentence(a.get('summary', ''), 110)}\n\n"
    brief += "💡 Save this post — future you will thank present you.\n"
    brief += f"📲 Follow {IG_HANDLE} for daily AI intelligence, Africa-first.\n\n"
    brief += "HASHTAGS (paste as first comment):\n"
    brief += ("#AIRadarAfrica #AI #ArtificialIntelligence #AfricaTech #TechInAfrica "
              "#KenyaTech #NairobiTech #LagosTech #DataScience #MachineLearning "
              "#TechNews #AINews #AfricanStartups #FutureOfWork #DigitalAfrica\n\n")
    brief += "CAROUSEL OUTLINE (design in Canva):\n"
    brief += f"Slide 1 (hook): \"3 AI stories Africa can't ignore — {today}\"\n"
    for i, a in enumerate(stories, 1):
        brief += f"Slide {i+1}: {a['title'][:70]}\n"
        brief += f"  • {_first_sentence(a.get('summary', ''), 100)}\n"
        brief += f"  • {_your_move(a)[:100]}\n"
    brief += f"Slide {len(stories)+2} (CTA): \"Follow {IG_HANDLE} for tomorrow's radar 📡\"\n"

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
