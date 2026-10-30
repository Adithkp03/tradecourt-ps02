"""Hard risk guardrails. Every order passes through here; the kill switch is checked
before every single cycle and cannot be overridden by the agent."""
import json, os

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state.json")

class RiskManager:
    def __init__(self, risk_pct=0.01, max_pos_pct=0.20, max_positions=5,
                 daily_loss_pct=0.02, atr_mult=2.0):
        self.risk_pct, self.max_pos_pct = risk_pct, max_pos_pct
        self.max_positions = max_positions
        self.daily_loss_pct, self.atr_mult = daily_loss_pct, atr_mult

    def size_position(self, equity, cash, price, atr):
        """Shares such that hitting the stop loses ~risk_pct of equity, capped at
        max_pos_pct of equity in notional. Returns (qty, stop_price)."""
        stop_dist = self.atr_mult * max(atr, price * 0.005)
        qty = int((equity * self.risk_pct) / stop_dist)
        qty = min(qty, int((equity * self.max_pos_pct) / price))
        qty = min(qty, int(cash / (price * 1.001)))
        return max(qty, 0), price - stop_dist

    def daily_limit_hit(self, day_start_equity, equity):
        if day_start_equity <= 0:
            return False
        return (equity - day_start_equity) / day_start_equity <= -self.daily_loss_pct

def kill_switch_engaged():
    try:
        return bool(json.load(open(STATE)).get("kill", False))
    except Exception:
        return False

def liquidate_requested():
    try:
        return bool(json.load(open(STATE)).get("liquidate", False))
    except Exception:
        return False

def set_state(**kw):
    st = {}
    if os.path.exists(STATE):
        try: st = json.load(open(STATE))
        except Exception: st = {}
    st.update(kw)
    json.dump(st, open(STATE, "w"))
