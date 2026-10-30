import streamlit as st, sqlite3, json, os, time
import pandas as pd, plotly.graph_objects as go

st.set_page_config(page_title="TradeCourt", page_icon="⚖️", layout="wide")
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "paper_account.db")

def q(sql, args=()):
    for _ in range(5):
        try:
            conn = sqlite3.connect(DB, timeout=3); conn.row_factory = sqlite3.Row
            try: return [dict(r) for r in conn.execute(sql, args)]
            finally: conn.close()
        except sqlite3.OperationalError:
            time.sleep(0.3)
    return []

def state():
    try: return json.load(open(os.path.join(BASE, "state.json")))
    except Exception: return {}

def set_state(**kw):
    stt = state(); stt.update(kw)
    json.dump(stt, open(os.path.join(BASE, "state.json"), "w"))

st.title("⚖️ TradeCourt - a paper trader that must defend every trade")
try:
    _prov = json.load(open(os.path.join(BASE, "data_provenance.json")))
    _srcs = set(_prov.values())
    _dsrc = "Yahoo Finance EOD" if _srcs and all("Yahoo" in s for s in _srcs) else ("MIXED: " + "; ".join(f"{k}: {v}" for k, v in _prov.items()))
except Exception:
    _dsrc = "not loaded yet (replay starting)"
st.error("SIMULATED / PAPER TRADING ONLY - mock exchange, no real money. Starting paper capital Rs10,00,000. Price data: " + _dsrc + ". Not investment advice.")
st.caption("Historical-price replay with a current-news overlay. Judge-injected scenarios (crash / fake hype / broker failure) are synthetic test inputs, clearly logged as such.")

stt = state()
r1c1, r1c2, r1c3 = st.columns(3)
r2c1, r2c2, r2c3 = st.columns(3)
if r1c1.button("🛑 KILL SWITCH " + ("ON - release" if stt.get("kill") else "off - engage"), use_container_width=True):
    set_state(kill=not stt.get("kill")); st.rerun()
if r1c2.button("🧹 LIQUIDATE ALL", use_container_width=True):
    set_state(liquidate=True); st.rerun()
if r1c3.button("💥 Inject market crash", use_container_width=True):
    set_state(scenario={"type": "crash", "pct": -0.06}); st.rerun()
if r2c1.button("📰 Inject fake hype news", use_container_width=True):
    set_state(scenario={"type": "fake_hype", "symbol": "RELIANCE.NS"}); st.rerun()
if r2c2.button("🔌 Inject broker failure", use_container_width=True):
    set_state(scenario={"type": "broker_down"}); st.rerun()
if r2c3.button("🗞 Duplicate headline 20x", use_container_width=True):
    set_state(scenario={"type": "dup_hype"}); st.rerun()
if stt.get("kill"):
    st.warning("Kill switch ON - new trades blocked; stop-losses and exits keep running.")

eq = q("SELECT * FROM equity_curve ORDER BY ts")
if eq:
    df = pd.DataFrame(eq)
    final, start = df["equity"].iloc[-1], df["equity"].iloc[0]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Paper equity", f"Rs{final:,.0f}", f"{final/start-1:+.1%}")
    m2.metric("Buy & hold NIFTY", f"Rs{df['benchmark'].iloc[-1]:,.0f}", f"{df['benchmark'].iloc[-1]/start-1:+.1%}")
    m3.metric("Cash", f"Rs{df['cash'].iloc[-1]:,.0f}")
    m4.metric("Max drawdown", f"{((df['equity'].cummax()-df['equity'])/df['equity'].cummax()).max():.1%}")
    m5.metric("Open positions", len(q("SELECT * FROM positions")))
    fig = go.Figure()
    fig.add_scatter(x=df["ts"], y=df["equity"], name="TradeCourt agent", line=dict(color="#00c853", width=2))
    fig.add_scatter(x=df["ts"], y=df["benchmark"], name="Buy & hold NIFTY", line=dict(color="#90a4ae", dash="dash"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns([3, 2])
with left:
    st.subheader("🏛️ Decision room - every proposal, defended")
    ds = q("SELECT * FROM decisions ORDER BY id DESC LIMIT 6")
    for d in ds:
        v = d["verdict"]
        icon = {"APPROVED": "✅", "REJECTED": "❌", "HOLD": "⏸️"}.get(v, "•")
        with st.expander(f"{icon} {d['ts']} - {d['symbol']}: {d['proposal']} -> **{v}**  ({d['strategy']})", expanded=(v != "HOLD")):
            st.markdown("**Evidence**")
            for e in json.loads(d["evidence"]): st.markdown(f"- {e}")
            ob = json.loads(d["objections"])
            if ob:
                st.markdown("**Objections**")
                for o in ob: st.markdown(f"- ⚠️ {o}")
    pos = q("SELECT * FROM positions")
    st.subheader(f"Open positions ({len(pos)}) - hard stops attached")
    if pos:
        st.dataframe(pd.DataFrame(pos)[["symbol","qty","avg_price","stop_loss","opened"]], hide_index=True)
    else:
        st.info("No open positions right now - the agent only trades when a proposal survives court.")
with right:
    st.subheader("Agent activity")
    for e in q("SELECT ts,kind,message FROM events ORDER BY id DESC LIMIT 12"):
        icon = {"trade": "💱", "guardrail": "🛡️", "system": "⚙️", "court": "⚖️", "scenario": "🧨"}.get(e["kind"], "•")
        st.caption(f"{icon} `{e['ts']}` {e['message']}")
    st.subheader("News feed (NoiseShield input)")
    nj = os.path.join(BASE, "news_snapshot.json")
    if os.path.exists(nj):
        snap = json.load(open(nj))
        st.caption(f"CURRENT snapshot fetched {snap.get('fetched_at')} - demo overlay, not a historical news feed")
        for sym, d in list(snap.get("data", {}).items())[:3]:
            with st.expander(f"{sym} ({d['score']:+d})"):
                for h in d["headlines"][:4]: st.write("- " + h)

st.subheader("📖 Trade journal (plain language, written at trade time)")
jp = os.path.join(BASE, "journal.md")
if os.path.exists(jp):
    st.markdown(open(jp).read()[-5000:])

st.subheader("🧪 Strategy lab - 1y backtest vs buy-and-hold")
bt = os.path.join(BASE, "backtest_report.json")
if os.path.exists(bt):
    st.dataframe(pd.DataFrame(json.load(open(bt))), hide_index=True)
st.caption("TradeCourt prototype - AgentX PS-02 - Team Vanquishers. Paper trading only.")
time.sleep(2)
st.rerun()
