# TradeCourt - Agentic Paper-Trading Bot (AgentX PS-02)

**SIMULATED / PAPER TRADING ONLY. No real money, no broker connection, no investment advice.**

Aegis is an autonomous trading agent that reads market data and news, picks a strategy
per stock based on the market regime, backtests it, and trades a simulated account on a
mock exchange - with hard risk guardrails and a human kill switch, and a plain-language
journal explaining every trade.

Built for the AgentX Hackathon 2026 PS-02 by Team Vanquishers.

## What it does (PS-02 mapping)

| Requirement | Where |
|---|---|
| Reads market data | `aegis/data.py` - Yahoo Finance EOD (NSE), cached, synthetic fallback labelled |
| Reads news | `aegis/news.py` - Google News RSS, transparent keyword sentiment, raw headlines shown |
| Picks / adapts strategy | `aegis/strategy.py` - regime switch: momentum (SMA 20/50) when trending, mean reversion (RSI-14) when ranging; strong negative news blocks entries |
| Backtests | `aegis/strategy.py::backtest` + `backtest_report.py` - same rules as live, vs buy-and-hold |
| Simulated execution | `aegis/broker.py` - mock exchange, SQLite ledger, 0.1% cost model |
| Position sizing | `aegis/risk.py` - 1% equity risk per trade via 2x ATR stop distance, max 20% notional, max 5 positions |
| Stop-losses | Hard 2x ATR stop per position, checked on every bar, exits at the stop |
| Daily loss limit | Halts all new trades for the day at -2% of day-start equity |
| Plain-language journal | `journal.md` + dashboard - every trade explained: why, risk in rupees, news context, result |
| Human kill switch | Dashboard button -> `state.json`; agent checks before every cycle. LIQUIDATE ALL closes everything at market |
| Backtest vs buy-and-hold | `backtest_report.py` (per symbol) and the live equity curve vs NIFTY buy-and-hold on the dashboard |

## Quick start (Windows / macOS / Linux, CPU-only)

```bash
pip install -r requirements.txt
python run_replay.py --days 120 --delay 1   # replay 120 trading days, 1s per day
streamlit run dashboard.py                  # watch it trade at http://localhost:8501
python backtest_report.py                   # per-symbol backtest vs buy-and-hold
```

## Architecture

```
 Yahoo EOD data ----+--> strategy.py (regime -> momentum | mean reversion)
 Google News RSS ---+         |
                              v
                        agent.py -- cycle per day
                              |  guardrails: risk.py (sizing, stops, daily limit, kill switch)
                              v
                        broker.py (mock exchange, SQLite ledger)
                              |
                    journal.md + dashboard.py (Streamlit)
```

The agent never sees future data during a replay: each day it only gets the rows up to
that date. Costs (0.1%) are charged on every fill.

## Honesty notes

- All results are simulated on historical EOD data. The replay does not predict anything.
- News sentiment is a simple keyword score over recent headlines at run time, not a
  per-day historical news feed - the journal states the fetch time on every entry.
- A trading bot that slightly underperforms buy-and-hold in a replay is shown as-is;
  the point of the prototype is autonomy + guardrails + explainability, not fake alpha.

Team Vanquishers - AgentX Hackathon 2026 (PS-02)
