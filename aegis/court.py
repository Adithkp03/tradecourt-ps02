"""TradeCourt: every proposed trade must be defended before it is placed.
Proposal -> evidence -> objections -> deterministic verdict. Plus NoiseShield:
flags duplicate, stale or provenance-free headlines before they can influence a trade."""
import hashlib

class NoiseShield:
    def __init__(self):
        self.seen = {}
    def check(self, symbol, headlines):
        flags = []
        dup = 0
        for h in headlines:
            key = hashlib.md5(h.strip().lower().encode()).hexdigest()
            if self.seen.get(key):
                dup += 1
            self.seen[key] = self.seen.get(key, 0) + 1
        if dup:
            flags.append(f"{dup} headline(s) are repeats of stories already counted - one story is not {dup+1} confirmations")
        if any("[INJECTED" in h for h in headlines):
            flags.append("headline fails provenance check: source is unverified (no publisher, no timestamp chain)")
        if not headlines:
            flags.append("no verifiable headlines at all - price data only")
        return flags

def deliberate(symbol, row, action, strat, reasons, sentiment, headlines, ns_flags,
               day_pnl_pct, open_positions, max_positions, stop_dist, price, bt, broker_down):
    evidence = list(reasons)
    evidence.append(f"RSI {row['rsi']:.0f}, SMA20 {row['sma20']:.1f} vs SMA50 {row['sma50']:.1f}, ATR {row['atr']:.1f}")
    if bt:
        evidence.append(f"1y backtest of this strategy on {symbol}: {bt['total_return']:+.1%} vs buy-and-hold "
                        f"{bt['benchmark_return']:+.1%}, max drawdown {bt['max_drawdown']:.1%}, {bt['n_trades']} trades")
    evidence.append(f"news sentiment {sentiment:+d} across {len(headlines)} headlines")
    objections = list(ns_flags)
    if sentiment <= -3:
        objections.append(f"news sentiment strongly negative ({sentiment:+d}) - entries blocked by policy")
    if action == "buy" and row["rsi"] > 65:
        objections.append(f"RSI {row['rsi']:.0f} is near overbought - poor reward-to-risk for a fresh entry")
    if day_pnl_pct <= -0.015:
        objections.append(f"day P&L {day_pnl_pct:+.1%} - close to the -2% daily loss limit")
    if action == "buy" and open_positions >= max_positions:
        objections.append(f"already holding the maximum of {max_positions} positions")
    if action == "buy" and stop_dist / price > 0.06:
        objections.append(f"stop distance is {stop_dist/price:.1%} of price - too volatile to size within 1% risk")
    if broker_down:
        objections.append("broker simulator unreachable (judge-injected failure) - order cannot be routed")
    if action == "hold":
        verdict = "HOLD"
    elif objections:
        verdict = "REJECTED"
    else:
        verdict = "APPROVED"
    return {"symbol": symbol, "proposal": action.upper(), "strategy": strat,
            "evidence": evidence, "objections": objections, "verdict": verdict}
