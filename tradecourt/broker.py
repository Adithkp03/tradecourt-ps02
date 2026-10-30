"""Mock exchange / paper broker. SQLite-persisted. Every fill applies costs and is
written to an immutable trade ledger with its reason - nothing is ever overwritten."""
import sqlite3, os, time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper_account.db")
COST_BPS = 10  # 0.1% round cost approximation (brokerage + slippage), stated in UI

class PaperBroker:
    def __init__(self, path=DB, starting_cash=1_000_000.0):
        self.path, self.starting_cash = path, starting_cash
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("""CREATE TABLE IF NOT EXISTS positions
            (symbol TEXT PRIMARY KEY, qty INTEGER, avg_price REAL, stop_loss REAL, opened TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS trades
            (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, symbol TEXT, side TEXT, qty INTEGER,
             price REAL, cost REAL, strategy TEXT, reason TEXT, mode TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS equity_curve
            (ts TEXT PRIMARY KEY, equity REAL, cash REAL, benchmark REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS decisions
            (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, symbol TEXT, proposal TEXT,
             strategy TEXT, verdict TEXT, evidence TEXT, objections TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events
            (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, message TEXT)""")
        self.conn.commit()
        if self.get_meta("cash") is None:
            self.reset()

    def reset(self):
        c = self.conn.cursor()
        for t in ("positions", "trades", "equity_curve", "events", "decisions"):
            c.execute(f"DELETE FROM {t}")
        self.set_meta("cash", str(self.starting_cash))
        self.set_meta("day_start_equity", str(self.starting_cash))
        self.set_meta("trading_halted", "0")
        self.conn.commit()
        self.log_event("system", f"Paper account reset. Starting cash Rs{self.starting_cash:,.0f}. SIMULATED - no real money.")

    def get_meta(self, key):
        r = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

    def set_meta(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)", (key, str(value)))
        self.conn.commit()

    @property
    def cash(self):
        return float(self.get_meta("cash"))

    def log_event(self, kind, message):
        self.conn.execute("INSERT INTO events (ts,kind,message) VALUES (?,?,?)",
                          (time.strftime("%Y-%m-%d %H:%M:%S"), kind, message))
        self.conn.commit()

    def position(self, symbol):
        r = self.conn.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
        return dict(r) if r else None

    def positions(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM positions")]

    def buy(self, ts, symbol, qty, price, stop, strategy, reason, mode="replay"):
        cost = qty * price * COST_BPS / 1e4
        total = qty * price + cost
        if total > self.cash:
            return False
        self.set_meta("cash", self.cash - total)
        self.conn.execute("INSERT OR REPLACE INTO positions (symbol,qty,avg_price,stop_loss,opened) VALUES (?,?,?,?,?)",
                          (symbol, qty, price, stop, ts))
        self.conn.execute("INSERT INTO trades (ts,symbol,side,qty,price,cost,strategy,reason,mode) VALUES (?,?,?,?,?,?,?,?,?)",
                          (ts, symbol, "BUY", qty, price, cost, strategy, reason, mode))
        self.conn.commit()
        self.log_event("trade", f"BUY {qty} {symbol} @ Rs{price:,.2f} (stop Rs{stop:,.2f}) - {reason}")
        return True

    def sell(self, ts, symbol, price, strategy, reason, mode="replay"):
        pos = self.position(symbol)
        if not pos:
            return False
        proceeds = pos["qty"] * price
        cost = proceeds * COST_BPS / 1e4
        self.set_meta("cash", self.cash + proceeds - cost)
        self.conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        self.conn.execute("INSERT INTO trades (ts,symbol,side,qty,price,cost,strategy,reason,mode) VALUES (?,?,?,?,?,?,?,?,?)",
                          (ts, symbol, "SELL", pos["qty"], price, cost, strategy, reason, mode))
        self.conn.commit()
        pnl = (price - pos["avg_price"]) * pos["qty"]
        self.log_event("trade", f"SELL {pos['qty']} {symbol} @ Rs{price:,.2f} | P&L Rs{pnl:+,.0f} - {reason}")
        return True

    def record_decision(self, ts, symbol, proposal, strategy, verdict, evidence, objections):
        self.conn.execute("INSERT INTO decisions (ts,symbol,proposal,strategy,verdict,evidence,objections) VALUES (?,?,?,?,?,?,?)",
                          (ts, symbol, proposal, strategy, verdict, evidence, objections))
        self.conn.commit()

    def record_equity(self, ts, prices, benchmark_value):
        eq = self.cash + sum(p["qty"] * prices.get(p["symbol"], p["avg_price"]) for p in self.positions())
        self.conn.execute("INSERT OR REPLACE INTO equity_curve (ts,equity,cash,benchmark) VALUES (?,?,?,?)",
                          (ts, eq, self.cash, benchmark_value))
        self.conn.commit()
        return eq
