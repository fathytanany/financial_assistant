"""The one LLM step: Claude turns the gold-layer numbers into a plain-language read.

Deterministic facts are computed here; Claude only narrates and advises. With no API key
it falls back to a templated summary, so the pipeline never hard-depends on the network.
"""

from __future__ import annotations

import pandas as pd

from . import config

_PROMPT = """You are a personal-finance analyst. Using ONLY the facts below, write a short
markdown brief (max ~150 words) for the account owner. Explain how their net worth moved and
WHY — separating money they added from currency (EGP) moves and gold moves. Note when EGP-
denominated 'gains' are really just the pound weakening (compare the EGP vs USD figures). End
with one or two concrete, cautious suggestions. Be direct; no preamble.

FACTS:
"""


def _window(attr: pd.DataFrame, days: int) -> dict:
    recent = attr[attr["date"] >= attr["date"].max() - pd.Timedelta(days=days)]
    return {
        "net_worth_change": float(recent["total_change"].sum()),
        "contributions": float(recent["external_flow"].sum()),
        "realized_gain": float(recent["realized_gain"].sum()),
        "unrealized_fx": float(recent["unrealized_fx"].sum()),
        "unrealized_gold": float(recent["unrealized_gold"].sum()),
    }


def build_facts(normalized, gold) -> str:
    attr = gold.pnl_attribution
    last = attr.iloc[-1]
    lines = [
        f"- Net worth now: {last['net_worth_egp']:,.0f} EGP / {last['net_worth_usd']:,.0f} USD",
    ]
    for label, days in [("30 days", 30), ("90 days", 90)]:
        w = _window(attr, days)
        lines.append(
            f"- Last {label}: total change {w['net_worth_change']:,.0f} EGP "
            f"(contributions {w['contributions']:,.0f}, booked/realized gains "
            f"{w['realized_gain']:,.0f}, FX {w['unrealized_fx']:,.0f}, gold {w['unrealized_gold']:,.0f})"
        )
    holdings = normalized.balances.sort_values("value_egp", ascending=False)
    top = holdings[holdings["value_egp"].abs() > 0].head(5)
    lines.append("- Largest holdings (EGP value): " + ", ".join(
        f"{r['name']} {r['value_egp']:,.0f}" for _, r in top.iterrows()
    ))
    return "\n".join(lines)


def _fallback(facts: str) -> str:
    return "## Insights\n\n_(set ANTHROPIC_API_KEY for a written analysis)_\n\n" + facts


def generate_insights(normalized, gold) -> str:
    facts = build_facts(normalized, gold)
    if not config.ANTHROPIC_API_KEY:
        return _fallback(facts)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": _PROMPT + facts}],
        )
        return msg.content[0].text
    except Exception as exc:  # never fail the pipeline over insights
        return _fallback(facts) + f"\n\n_(Claude call failed: {exc})_"
