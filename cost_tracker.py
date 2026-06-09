"""
AI Radar Africa - Token & Cost Tracker
Accumulates token usage across all Claude API calls in a run and prints
a cost summary. Pricing is configurable — verify current rates at
https://docs.claude.com/en/docs/about-claude/pricing
"""

import logging

log = logging.getLogger(__name__)

# ── Pricing (USD per 1 million tokens) ───────────────────────────────────────────
# Verify current rates — these can change. Update here if needed.
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # add other models if you switch:
    # "claude-opus-4-20250514":   {"input": 15.00, "output": 75.00},
    # "claude-haiku-...":         {"input": 0.80,  "output": 4.00},
}

DEFAULT_PRICING = {"input": 3.00, "output": 15.00}  # fallback if model not listed


class CostTracker:
    """Singleton-style tracker. Call record() after each API response."""

    def __init__(self):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.model = None

    def record(self, response, label: str = ""):
        """Pull usage from an Anthropic API response object and accumulate it."""
        try:
            usage = response.usage
            self.calls += 1
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens
            self.model = getattr(response, "model", self.model)
            log.debug(
                f"  [token] {label}: {usage.input_tokens} in / "
                f"{usage.output_tokens} out"
            )
        except AttributeError:
            log.warning(f"Could not read usage from response ({label}).")

    def _rates(self):
        return PRICING.get(self.model, DEFAULT_PRICING)

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self):
        rates = self._rates()
        return (
            self.input_tokens  / 1_000_000 * rates["input"]
            + self.output_tokens / 1_000_000 * rates["output"]
        )

    def summary(self, kes_rate: float = 129.0) -> str:
        """Return a formatted cost summary. kes_rate = KSh per USD."""
        cost = self.cost_usd
        cost_kes = cost * kes_rate
        rates = self._rates()
        return (
            "\n┌─ Token & Cost Summary ─────────────────────────────\n"
            f"│ Model:          {self.model or 'unknown'}\n"
            f"│ API calls:      {self.calls}\n"
            f"│ Input tokens:   {self.input_tokens:,}  (${rates['input']}/M)\n"
            f"│ Output tokens:  {self.output_tokens:,}  (${rates['output']}/M)\n"
            f"│ Total tokens:   {self.total_tokens:,}\n"
            f"│ Cost this run:  ${cost:.4f}  (≈ KSh {cost_kes:.2f})\n"
            f"│ Est. monthly:   ${cost*30:.2f}  (≈ KSh {cost_kes*30:.2f})  @ 1 run/day\n"
            "└────────────────────────────────────────────────────"
        )

    def print_summary(self, kes_rate: float = 129.0):
        log.info(self.summary(kes_rate))
        print(self.summary(kes_rate))


# Shared instance imported by scorer.py and brief_generator.py
tracker = CostTracker()
