"""TradeCourt replay: N trading days through the agent vs the paper account.
Decisions use only data available that day. Judge scenarios (crash / fake hype /
broker failure) are injected live from the dashboard. SIMULATED throughout."""
import argparse, time, json, os
from tradecourt.data import load_history, SYMBOLS, INDEX
from tradecourt.news import NewsDesk
from tradecourt.broker import PaperBroker
from tradecourt.risk import RiskManager, set_state
from tradecourt import journal
from tradecourt.strategy import add_indicators, backtest
from tradecourt.agent import TradingAgent

def run_replay(days=120, delay=0.0, cash=1_000_000.0):
    class args:  # keeps the loop body below unchanged
        pass
    args.days, args.delay, args.cash = days, delay, cash

    print("=" * 66, flush=True)
    print(" TRADECOURT - every trade defended before it is placed | SIMULATED", flush=True)
    print("=" * 66, flush=True)
    print(f"[setup] EOD data for {len(SYMBOLS)} NSE symbols + NIFTY...", flush=True)
    hist = {s: add_indicators(load_history(s)) for s in SYMBOLS}
    bench = load_history(INDEX)

    print("[setup] backtesting strategies (court needs the evidence)...", flush=True)
    bts = {s: backtest(load_history(s)) for s in SYMBOLS}
    for s, r in bts.items():
        print(f"[backtest] {s:<14} agent {r['total_return']:+.1%} vs B&H {r['benchmark_return']:+.1%} "
              f"| maxDD {r['max_drawdown']:.1%} | {r['n_trades']} trades", flush=True)

    set_state(kill=False, liquidate=False, scenario=None)
    broker = PaperBroker(starting_cash=args.cash)
    broker.reset()
    journal.reset_journal(args.cash)
    news = NewsDesk()
    print("[setup] fetching live news headlines (Google News RSS)...", flush=True)
    news.refresh(SYMBOLS)
    json.dump({"fetched_at": news.fetched_at, "data": news.cache}, open("news_snapshot.json", "w"), indent=1)
    for s in SYMBOLS:
        st = news.sentiment(s)
        print(f"[news] {s:<14} sentiment {st['score']:+d} ({len(st['headlines'])} headlines)", flush=True)

    agent = TradingAgent(broker, news, RiskManager(), SYMBOLS, backtests=bts)
    replay_dates = bench.index[-args.days:]
    bench0 = float(bench["Close"].loc[replay_dates[0]])
    print(f"[run] {len(replay_dates)} trading days, {replay_dates[0].date()} -> {replay_dates[-1].date()}", flush=True)
    print("[run] risk 1%/trade | stops 2xATR | daily loss limit -2% | kill switch armed | court in session", flush=True)

    for d in replay_dates:
        windows = {s: hist[s].loc[:d].copy() for s in SYMBOLS if d in hist[s].index}
        if len(windows) < len(SYMBOLS):
            continue
        scenario = None
        try:
            st = json.load(open("state.json"))
            if st.get("scenario"):
                scenario = st["scenario"]  # agent consumes it when it can actually apply it
        except Exception:
            pass
        bv = args.cash * (1 - 0.001) * float(bench["Close"].loc[d]) / bench0  # B&H pays same 0.1% buy cost
        eq = agent.run_day(str(d.date()), windows, bv, scenario=scenario)
        if eq is not None:
            print(f"[{d.date()}] equity Rs{eq:>12,.0f} | B&H Rs{bv:>12,.0f} | open {len(broker.positions())}", flush=True)
        if args.delay:
            time.sleep(args.delay)

    rows = broker.conn.execute("SELECT equity,benchmark FROM equity_curve ORDER BY ts").fetchall()
    if rows:
        f_, b_ = rows[-1]["equity"], rows[-1]["benchmark"]
        n = broker.conn.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"]
        nd = broker.conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"]
        print("-" * 66, flush=True)
        print(f"[done] agent Rs{f_:,.0f} ({f_/args.cash-1:+.1%}) vs buy-and-hold Rs{b_:,.0f} ({b_/args.cash-1:+.1%})"
              f" | {n} trades, {nd} court decisions", flush=True)
        print("[done] SIMULATED results - not investment advice.", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--cash", type=float, default=1_000_000.0)
    a = ap.parse_args()
    run_replay(days=a.days, delay=a.delay, cash=a.cash)

if __name__ == "__main__":
    main()
