"""Plain-language trade journal. Every trade gets a human-readable explanation a
non-trader can audit: what happened, why, what the risk was, what the news said."""
import os

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "journal.md")

def reset_journal(starting_cash):
    with open(JOURNAL, "w") as f:
        f.write("# Aegis trade journal (SIMULATED / paper trading only)\n\n")
        f.write(f"Starting paper capital: Rs{starting_cash:,.0f}. Every entry below was written "
                "by the agent at the moment it traded.\n\n---\n")

def entry(ts, side, symbol, qty, price, stop, equity, strategy, reasons, senti, news_time, pnl=None):
    lines = [f"\n## {ts} - {side} {qty} x {symbol} @ Rs{price:,.2f}\n"]
    lines.append(f"**Strategy in charge:** {strategy}\n")
    lines.append("**Why:**")
    for r in reasons:
        lines.append(f"- {r}")
    if side == "BUY":
        risk = (price - stop) * qty
        lines.append(f"**Risk on this trade:** stop-loss at Rs{stop:,.2f}. If it triggers, this trade "
                     f"loses about Rs{risk:,.0f} ({risk / equity * 100:.2f}% of current equity). Position "
                     f"value is Rs{qty * price:,.0f} ({qty * price / equity * 100:.1f}% of equity).")
    if pnl is not None:
        lines.append(f"**Result:** {'profit' if pnl >= 0 else 'loss'} of Rs{pnl:+,.0f} on this position.")
    lines.append(f"**News check:** sentiment score {senti} from headlines fetched {news_time} "
                 "(keyword scoring, raw headlines visible in dashboard).")
    lines.append("\n---\n")
    with open(JOURNAL, "a") as f:
        f.write("\n".join(lines) + "\n")

def guardrail_event(text):
    with open(JOURNAL, "a") as f:
        f.write(f"\n> **GUARDRAIL:** {text}\n\n---\n")
