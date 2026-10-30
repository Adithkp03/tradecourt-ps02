"""The autonomous agent. One cycle = read market data + news snapshot, pick the
strategy per symbol, check every guardrail, size and place paper orders, journal it."""
import pandas as pd
from . import strategy, risk, journal

class TradingAgent:
    def __init__(self, broker, newsdesk, risk_mgr, symbols):
        self.broker, self.news, self.risk, self.symbols = broker, newsdesk, risk_mgr, symbols

    def run_day(self, date_str, windows, bench_value, mode="replay"):
        b = self.broker
        if risk.kill_switch_engaged():
            b.log_event("guardrail", "KILL SWITCH engaged - agent skipped this cycle entirely.")
            return None
        if risk.liquidate_requested():
            for p in b.positions():
                px = float(windows[p["symbol"]].iloc[-1]["Close"])
                b.sell(date_str, p["symbol"], px, "manual", "Human pressed LIQUIDATE ALL", mode)
            risk.set_state(liquidate=False)
            journal.guardrail_event(f"{date_str}: human pressed LIQUIDATE ALL - every position closed at market.")
            b.log_event("guardrail", "LIQUIDATE ALL executed on human command.")

        prices = {s: float(windows[s].iloc[-1]["Close"]) for s in self.symbols}
        equity = b.cash + sum(p["qty"] * prices.get(p["symbol"], p["avg_price"]) for p in b.positions())

        day_start = float(b.get_meta("day_start_equity") or equity)
        last_day = (b.get_meta("last_day") or "")
        if last_day != date_str[:10]:
            b.set_meta("day_start_equity", str(equity)); b.set_meta("last_day", date_str[:10])
            b.set_meta("trading_halted", "0")
            day_start = equity

        halted = b.get_meta("trading_halted") == "1"
        if not halted and self.risk.daily_limit_hit(day_start, equity):
            b.set_meta("trading_halted", "1"); halted = True
            msg = (f"{date_str}: daily loss limit hit (equity Rs{equity:,.0f} vs day start "
                   f"Rs{day_start:,.0f}, limit -{self.risk.daily_loss_pct*100:.0f}%). No new trades today.")
            journal.guardrail_event(msg); b.log_event("guardrail", msg)

        for s in self.symbols:
            df = windows[s]
            row = df.iloc[-1]
            price = float(row["Close"])
            pos = b.position(s)
            senti = self.news.sentiment(s)["score"]
            # 1. stop-loss always wins
            if pos and float(row["Low"]) <= pos["stop_loss"]:
                px = min(float(row["Open"]), pos["stop_loss"])
                pnl = (px - pos["avg_price"]) * pos["qty"]
                b.sell(date_str, s, px, pos.get("strategy") or "stop", "Stop-loss hit intraday", mode)
                journal.entry(date_str, "SELL", s, pos["qty"], px, pos["stop_loss"], equity,
                              "Stop-loss (hard guardrail)", [f"Price touched the stop at Rs{pos['stop_loss']:,.2f} - out, no second-guessing"],
                              senti, self.news.fetched_at, pnl=pnl)
                continue
            action, strat, reasons = strategy.decide(row, senti, pos is not None)
            if action == "sell" and pos:
                pnl = (price - pos["avg_price"]) * pos["qty"]
                b.sell(date_str, s, price, strat, reasons[0], mode)
                journal.entry(date_str, "SELL", s, pos["qty"], price, pos["stop_loss"], equity,
                              strat, reasons, senti, self.news.fetched_at, pnl=pnl)
            elif action == "buy" and not pos and not halted:
                if len(b.positions()) >= self.risk.max_positions:
                    b.log_event("guardrail", f"Skipped {s}: max {self.risk.max_positions} positions guardrail.")
                    continue
                qty, stop = self.risk.size_position(equity, b.cash, price, float(row["atr"]))
                if qty <= 0:
                    b.log_event("guardrail", f"Skipped {s}: risk sizing gave 0 shares (cash/equity limits).")
                    continue
                if b.buy(date_str, s, qty, price, stop, strat, reasons[0], mode):
                    journal.entry(date_str, "BUY", s, qty, price, stop, equity, strat, reasons,
                                  senti, self.news.fetched_at)
        return b.record_equity(date_str, prices, bench_value)
