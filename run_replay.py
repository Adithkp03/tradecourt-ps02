"""Replay the last N trading days through the agent against the paper account.
Honest simulation: EOD data, decisions use only data available that day. All output
is labelled SIMULATED. Use --delay to watch it trade live on the dashboard."""
import argparse, time, sys
import pandas as pd
from aegis.data import load_history, SYMBOLS, INDEX
from aegis.news import NewsDesk
from aegis.broker import PaperBroker
from aegis.risk import RiskManager, set_state
from aegis import journal
from aegis.agent import TradingAgent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--cash", type=float, default=1_000_000.0)
    args = ap.parse_args()

    print("=" * 64, flush=True)
    print(" AEGIS - agentic paper-trading bot  |  SIMULATED, NO REAL MONEY", flush=True)
    print("=" * 64, flush=True)
    print(f"[setup] downloading EOD data for {len(SYMBOLS)} NSE symbols + NIFTY...", flush=True)
    hist = {s: load_history(s) for s in SYMBOLS}
    bench = load_history(INDEX)
    from aegis.strategy import add_indicators
    hist = {s: add_indicators(df) for s, df in hist.items()}
    sources = {s: df.attrs.get("source", "?") for s, df in hist.items()}
    print(f"[setup] data source: {set(sources.values())}", flush=True)

    set_state(kill=False, liquidate=False)
    broker = PaperBroker(starting_cash=args.cash)
    broker.reset()
    journal.reset_journal(args.cash)
    news = NewsDesk()
    print("[setup] fetching latest news headlines (Google News RSS, no key)...", flush=True)
    news.refresh(SYMBOLS)
    for s in SYMBOLS:
        st = news.sentiment(s)
        print(f"[news] {s:<14} sentiment {st['score']:+d} from {len(st['headlines'])} headlines", flush=True)

    import json as _json
    _json.dump({"fetched_at": news.fetched_at, "data": news.cache}, open("news_snapshot.json", "w"), indent=1)
    agent = TradingAgent(broker, news, RiskManager(), SYMBOLS)
    dates = bench.index[-args.days - 60:]  # extra warmup so indicators are valid on day 1
    replay_dates = dates[-args.days:]
    bench0 = float(bench["Close"].loc[replay_dates[0]])
    print(f"[run] replaying {len(replay_dates)} trading days, {replay_dates[0].date()} -> {replay_dates[-1].date()}", flush=True)
    print(f"[run] paper capital Rs{args.cash:,.0f} | risk 1%/trade | stop 2xATR | daily loss limit 2% | kill switch armed", flush=True)

    for d in replay_dates:
        windows = {s: hist[s].loc[:d] for s in SYMBOLS if d in hist[s].index}
        if len(windows) < len(SYMBOLS):
            continue
        bv = args.cash * float(bench["Close"].loc[d]) / bench0
        eq = agent.run_day(str(d.date()), windows, bv)
        if eq is not None:
            n = len(broker.positions())
            print(f"[{d.date()}] equity Rs{eq:>12,.0f} | bench Rs{bv:>12,.0f} | open {n}", flush=True)
        if args.delay:
            time.sleep(args.delay)

    eq = broker.conn.execute("SELECT equity,benchmark FROM equity_curve ORDER BY ts").fetchall()
    if eq:
        final, bfinal = eq[-1]["equity"], eq[-1]["benchmark"]
        print("-" * 64, flush=True)
        print(f"[done] agent Rs{final:,.0f} ({final/args.cash-1:+.1%}) vs buy-and-hold NIFTY "
              f"Rs{bfinal:,.0f} ({bfinal/args.cash-1:+.1%}) | trades: "
              f"{broker.conn.execute('SELECT COUNT(*) c FROM trades').fetchone()['c']}", flush=True)
        print("[done] journal.md + dashboard updated. SIMULATED results - not investment advice.", flush=True)

if __name__ == "__main__":
    main()
