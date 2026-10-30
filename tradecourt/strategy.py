"""Strategies + regime selection + backtest. The agent picks momentum vs mean-reversion
from the current volatility/trend regime - that choice is logged for every trade."""
import numpy as np
import pandas as pd

def add_indicators(df):
    df = df.copy()
    c = df["Close"]
    df["sma20"] = c.rolling(20).mean()
    df["sma50"] = c.rolling(50).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = (100 - 100 / (1 + rs)).fillna(50.0)
    tr = pd.concat([(df["High"] - df["Low"]), (df["High"] - c.shift()).abs(),
                    (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean().bfill()
    return df

def regime(row):
    if pd.isna(row["sma50"]) or row["sma50"] == 0:
        return "warming-up"
    strength = abs(row["sma20"] - row["sma50"]) / row["sma50"]
    return "trending" if strength > 0.02 else "ranging"

def decide(row, sentiment_score, has_position):
    """Returns (action, strategy_name, reasons[list]). action in buy/sell/hold."""
    reg = regime(row)
    rsi, s20, s50 = row["rsi"], row["sma20"], row["sma50"]
    if reg == "trending":
        strat = "Momentum (SMA 20/50 trend-following)"
        if not has_position and s20 > s50 and rsi < 70:
            if sentiment_score <= -3:
                return "hold", strat, [f"Uptrend (SMA20 {s20:.1f} > SMA50 {s50:.1f}) but news sentiment {sentiment_score} is strongly negative, entry blocked"]
            return "buy", strat, [f"Uptrend: SMA20 ({s20:.1f}) above SMA50 ({s50:.1f})", f"RSI {rsi:.0f} - not overbought"]
        if has_position and s20 < s50:
            return "sell", strat, [f"Trend broken: SMA20 ({s20:.1f}) crossed below SMA50 ({s50:.1f})"]
        return "hold", strat, [f"Trend {'up' if s20 > s50 else 'down'}, no crossover"]
    if reg == "ranging":
        strat = "Mean reversion (RSI-14)"
        if not has_position and rsi < 32:
            if sentiment_score <= -3:
                return "hold", strat, [f"Oversold (RSI {rsi:.0f}) but news sentiment {sentiment_score} strongly negative, entry blocked"]
            return "buy", strat, [f"Oversold: RSI {rsi:.0f} below 32 in a ranging market"]
        if has_position and rsi > 55:
            return "sell", strat, [f"Reversion complete: RSI {rsi:.0f} back above 55"]
        return "hold", strat, [f"Ranging market, RSI {rsi:.0f} neutral"]
    return "hold", "none", ["Warming up: not enough history for indicators"]

def backtest(df, starting_cash=1_000_000.0, risk_pct=0.01, max_pos_pct=0.20,
             atr_mult=2.0, cost_bps=10):
    """Single-symbol backtest with the same sizing/stop rules the live agent uses."""
    df = add_indicators(df)
    cash, qty, stop, entry_price = starting_cash, 0, 0.0, 0.0
    equity_curve, trades = [], []
    bh_qty = 0.0
    started = False
    for i in range(len(df)):
        row = df.iloc[i]
        price = float(row["Close"])
        if not started and not pd.isna(row["sma50"]):
            bh_qty = starting_cash / price
            started = True
        if pd.isna(row["sma50"]):
            equity_curve.append(starting_cash); continue
        action, strat, reasons = decide(row, 0, qty > 0)
        # stop-loss check on the day's low
        if qty > 0 and float(row["Low"]) <= stop:
            px = min(float(row["Open"]), stop)
            proceeds = qty * px * (1 - cost_bps / 1e4)
            trades.append({"date": str(df.index[i].date()), "side": "SELL", "price": px,
                           "qty": qty, "reason": "Stop-loss hit", "strategy": strat})
            cash += proceeds; qty = 0
        elif action == "sell" and qty > 0:
            proceeds = qty * price * (1 - cost_bps / 1e4)
            trades.append({"date": str(df.index[i].date()), "side": "SELL", "price": price,
                           "qty": qty, "reason": reasons[0], "strategy": strat})
            cash += proceeds; qty = 0
        elif action == "buy" and qty == 0:
            atr = float(row["atr"]) if not pd.isna(row["atr"]) else price * 0.02
            stop_dist = atr_mult * atr
            equity = cash
            q = int((equity * risk_pct) / stop_dist)
            q = min(q, int((equity * max_pos_pct) / price))
            if q > 0:
                cost = q * price * (1 + cost_bps / 1e4)
                if cost <= cash:
                    cash -= cost; qty, entry_price = q, price
                    stop = price - stop_dist
                    trades.append({"date": str(df.index[i].date()), "side": "BUY", "price": price,
                                   "qty": qty, "reason": reasons[0], "strategy": strat})
        equity_curve.append(cash + qty * price)
    eq = pd.Series(equity_curve, index=df.index)
    bh = (bh_qty * df["Close"]) if started else pd.Series(starting_cash, index=df.index)
    rets = eq.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if len(rets) > 2 and rets.std() > 0 else 0.0
    dd = float(((eq.cummax() - eq) / eq.cummax()).max())
    sells = [t for t in trades if t["side"] == "SELL"]
    return {"equity": eq, "benchmark": bh, "trades": trades,
            "total_return": float(eq.iloc[-1] / starting_cash - 1),
            "benchmark_return": float(bh.iloc[-1] / starting_cash - 1) if started else 0.0,
            "max_drawdown": dd, "sharpe": sharpe, "n_trades": len(trades)}
