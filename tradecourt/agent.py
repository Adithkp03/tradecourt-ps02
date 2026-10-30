"""The autonomous agent, TradeCourt edition. One cycle = read market data + news,
pick the strategy per symbol, DEFEND the proposal in court (evidence/objections/verdict),
pass every guardrail, size and place paper orders, journal everything."""
import json
from . import strategy, risk, journal
from .court import NoiseShield, deliberate

class TradingAgent:
    def __init__(self, broker, newsdesk, risk_mgr, symbols, backtests=None):
        self.broker, self.news, self.risk, self.symbols = broker, newsdesk, risk_mgr, symbols
        self.ns = NoiseShield()
        self.backtests = backtests or {}

    def _record(self, ts, d):
        self.broker.record_decision(ts, d["symbol"], d["proposal"], d["strategy"],
                                    d["verdict"], json.dumps(d["evidence"]), json.dumps(d["objections"]))

    def run_day(self, date_str, windows, bench_value, mode="replay", scenario=None):
        b = self.broker
        no_entries = risk.kill_switch_engaged()
        if no_entries:
            b.log_event("guardrail", "KILL SWITCH on - new entries blocked; stop-losses and exits stay protected.")
        scenario = scenario or {}
        applied = None
        if scenario.get("type") == "fake_hype":
            if not scenario.get("symbol"):
                # Aim the judge's fake hype at a symbol whose setup is genuinely
                # buy-eligible under positive sentiment - a real proposal, not staged.
                for s in self.symbols:
                    if s not in windows or b.position(s):
                        continue
                    if strategy.decide(windows[s].iloc[-1], 5, False)[0] == "buy":
                        scenario["symbol"] = s
                        break
            if scenario.get("symbol") and not b.position(scenario["symbol"]):
                applied = scenario
            else:
                b.log_event("scenario", "Judge's fake hype queued - waiting for a buy-eligible setup.")
        else:
            applied = scenario
        if applied:
            risk.set_state(scenario=None)  # exactly one injection per press
            scenario = dict(applied)
        else:
            scenario = {}
        broker_down = scenario.get("type") == "broker_down"
        if risk.liquidate_requested():
            for p in b.positions():
                px = float(windows[p["symbol"]].iloc[-1]["Close"])
                b.sell(date_str, p["symbol"], px, "manual", "Human pressed LIQUIDATE ALL", mode)
            risk.set_state(liquidate=False)
            journal.guardrail_event(f"{date_str}: human pressed LIQUIDATE ALL - every position closed at market.")
            b.log_event("guardrail", "LIQUIDATE ALL executed on human command.")

        prices = {s: float(windows[s].iloc[-1]["Close"]) for s in self.symbols}
        if scenario.get("type") == "crash":
            shock = float(scenario.get("pct", -0.06))
            prices = {s: p * (1 + shock) for s, p in prices.items()}
            for s in self.symbols:
                w = windows[s]
                w.iloc[-1, w.columns.get_loc("Low")] = min(float(w.iloc[-1]["Low"]), prices[s])
                w.iloc[-1, w.columns.get_loc("Close")] = prices[s]
            b.log_event("scenario", f"JUDGE INJECTED market crash {shock:+.0%} - simulated tape moved, agent must react.")

        equity = b.cash + sum(p["qty"] * prices.get(p["symbol"], p["avg_price"]) for p in b.positions())
        day_start = float(b.get_meta("day_start_equity") or equity)
        if (b.get_meta("last_day") or "") != date_str[:10]:
            b.set_meta("day_start_equity", str(equity)); b.set_meta("last_day", date_str[:10])
            b.set_meta("trading_halted", "0"); day_start = equity
        day_pnl_pct = (equity - day_start) / day_start if day_start else 0.0

        halted = b.get_meta("trading_halted") == "1"
        if not halted and self.risk.daily_limit_hit(day_start, equity):
            b.set_meta("trading_halted", "1"); halted = True
            msg = (f"{date_str}: daily loss limit hit (equity Rs{equity:,.0f} vs day start Rs{day_start:,.0f}, "
                   f"limit -{self.risk.daily_loss_pct*100:.0f}%). No new trades today.")
            journal.guardrail_event(msg); b.log_event("guardrail", msg)

        for s in self.symbols:
            df = windows[s]
            row = df.iloc[-1]
            price = prices[s]
            pos = b.position(s)
            snap = self.news.sentiment(s)
            headlines, senti = list(snap["headlines"]), snap["score"]
            if scenario.get("type") == "fake_hype" and scenario.get("symbol") == s:
                headlines = [f"[INJECTED by judge] {s} to double in a week, say insiders - act now!"] + headlines
                senti = 5
                b.log_event("scenario", f"JUDGE INJECTED misleading hype headline on {s} - NoiseShield must catch it.")
            ns_flags = self.ns.check(s, headlines)

            if pos and float(row["Low"]) <= pos["stop_loss"]:
                px = min(float(row["Open"]), pos["stop_loss"])
                pnl = (px - pos["avg_price"]) * pos["qty"]
                if broker_down:
                    b.log_event("scenario", f"broker down: stop-exit order for {s} could not route - will retry next cycle")
                    continue
                b.sell(date_str, s, px, "stop-loss", "Stop-loss hit intraday", mode)
                journal.entry(date_str, "SELL", s, pos["qty"], px, pos["stop_loss"], equity,
                              "Stop-loss (hard guardrail)",
                              [f"Price touched the stop at Rs{pos['stop_loss']:,.2f} - out, no second-guessing"],
                              senti, self.news.fetched_at, pnl=pnl)
                continue

            action, strat, reasons = strategy.decide(row, senti, pos is not None)
            stop_dist = self.risk.atr_mult * max(float(row["atr"]), price * 0.005)
            d = deliberate(s, row, action, strat, reasons, senti, headlines, ns_flags,
                           day_pnl_pct, len(b.positions()), self.risk.max_positions,
                           stop_dist, price, self.backtests.get(s), broker_down)
            interesting = action != "hold" or d["objections"] or scenario
            if no_entries and action == "buy":
                d["objections"].append("kill switch engaged by a human - new entries blocked")
                d["verdict"] = "REJECTED"
                interesting = True
            if interesting:
                self._record(date_str, d)
                b.log_event("court", f"{s}: proposal {d['proposal']} -> {d['verdict']}"
                            + (f" ({len(d['objections'])} objection(s))" if d["objections"] else ""))

            if d["verdict"] != "APPROVED":
                continue
            if action == "sell" and pos:
                pnl = (price - pos["avg_price"]) * pos["qty"]
                b.sell(date_str, s, price, strat, reasons[0], mode)
                journal.entry(date_str, "SELL", s, pos["qty"], price, pos["stop_loss"], equity,
                              strat, reasons, senti, self.news.fetched_at, pnl=pnl)
            elif action == "buy" and not pos and not halted and not no_entries:
                qty, stop = self.risk.size_position(equity, b.cash, price, float(row["atr"]))
                if qty <= 0:
                    b.log_event("guardrail", f"Skipped {s}: risk sizing gave 0 shares (cash/equity limits).")
                    continue
                if b.buy(date_str, s, qty, price, stop, strat, reasons[0], mode):
                    journal.entry(date_str, "BUY", s, qty, price, stop, equity, strat, reasons,
                                  senti, self.news.fetched_at)
        return b.record_equity(date_str, prices, bench_value)
