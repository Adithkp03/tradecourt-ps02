"""Backtest report: each symbol, same rules as the live agent, vs buy-and-hold."""
import json
from tradecourt.data import load_history, SYMBOLS, INDEX
from tradecourt.strategy import backtest

rows = []
for s in SYMBOLS + [INDEX]:
    df = load_history(s)
    r = backtest(df)
    rows.append({"symbol": s, "agent_return": f"{r['total_return']:+.1%}",
                 "buy_hold_return": f"{r['benchmark_return']:+.1%}",
                 "max_drawdown": f"{r['max_drawdown']:.1%}", "sharpe": round(r["sharpe"], 2),
                 "trades": r["n_trades"]})
json.dump(rows, open("backtest_report.json", "w"), indent=1)
for r in rows: print(r)
