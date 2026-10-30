import streamlit as st, sqlite3, json, os, time
import pandas as pd, plotly.graph_objects as go

st.set_page_config(page_title="Aegis - Paper Trading Agent", page_icon="🛡️", layout="wide")
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "paper_account.db")

def q(sql, args=()):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    try: return [dict(r) for r in conn.execute(sql, args)]
    finally: conn.close()

def state():
    try: return json.load(open(os.path.join(BASE, "state.json")))
    except Exception: return {}

st.title("🛡️ Aegis - Agentic Paper-Trading Bot")
st.error("SIMULATED / PAPER TRADING ONLY - no real money, no broker connection. EOD data: Yahoo Finance. Not investment advice.")

stt = state()
k1, k2, k3 = st.columns([1, 1, 2])
if k1.button("🛑 ENGAGE KILL SWITCH" if not stt.get("kill") else "✅ Kill switch ENGAGED - click to release"):
    json.dump({**stt, "kill": not stt.get("kill")}, open(os.path.join(BASE, "state.json"), "w")); st.rerun()
if k2.button("🧹 LIQUIDATE ALL POSITIONS"):
    json.dump({**stt, "liquidate": True}, open(os.path.join(BASE, "state.json"), "w")); st.rerun()
if stt.get("kill"):
    k3.warning("Kill switch is ON - the agent checks it before every cycle and will not trade.")

eq = q("SELECT * FROM equity_curve ORDER BY ts")
if eq:
    df = pd.DataFrame(eq)
    final, start = df["equity"].iloc[-1], df["equity"].iloc[0]
    bh_final = df["benchmark"].iloc[-1]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Paper equity", f"Rs{final:,.0f}", f"{final/start-1:+.1%}")
    m2.metric("Buy & hold (NIFTY)", f"Rs{bh_final:,.0f}", f"{bh_final/start-1:+.1%}")
    m3.metric("Cash", f"Rs{df['cash'].iloc[-1]:,.0f}")
    m4.metric("Max drawdown", f"{((df['equity'].cummax()-df['equity'])/df['equity'].cummax()).max():.1%}")
    m5.metric("Open positions", len(q("SELECT * FROM positions")))
    fig = go.Figure()
    fig.add_scatter(x=df["ts"], y=df["equity"], name="Aegis agent", line=dict(color="#00c853", width=2))
    fig.add_scatter(x=df["ts"], y=df["benchmark"], name="Buy & hold NIFTY", line=dict(color="#90a4ae", dash="dash"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Open positions (with hard stops)")
    pos = q("SELECT * FROM positions")
    if pos:
        st.dataframe(pd.DataFrame(pos)[["symbol","qty","avg_price","stop_loss","opened"]], hide_index=True)
    else:
        st.info("Flat - no open positions. The agent only trades when a strategy signals.")
    st.subheader("Recent trades")
    tr = q("SELECT ts,symbol,side,qty,price,strategy,reason FROM trades ORDER BY id DESC LIMIT 12")
    st.dataframe(pd.DataFrame(tr), hide_index=True) if tr else st.info("None yet")
with right:
    st.subheader("Agent activity log")
    ev = q("SELECT ts,kind,message FROM events ORDER BY id DESC LIMIT 14")
    for e in ev:
        icon = {"trade": "💱", "guardrail": "🛡️", "system": "⚙️"}.get(e["kind"], "•")
        st.caption(f"{icon} `{e['ts']}` {e['message']}")
    st.subheader("Latest news sentiment snapshot")
    nj = os.path.join(BASE, "news_snapshot.json")
    if os.path.exists(nj):
        snap = json.load(open(nj))
        st.caption(f"Fetched {snap.get('fetched_at')} - Google News RSS, keyword-scored, raw headlines below")
        for sym, d in snap.get("data", {}).items():
            with st.expander(f"{sym}  (score {d['score']:+d})"):
                for h in d["headlines"][:5]: st.write("- " + h)

st.subheader("Trade journal (plain language, written by the agent)")
jp = os.path.join(BASE, "journal.md")
if os.path.exists(jp):
    txt = open(jp).read()
    st.markdown(txt[-6000:])

st.subheader("Backtest vs buy-and-hold (per symbol, full year)")
bt = os.path.join(BASE, "backtest_report.json")
if os.path.exists(bt):
    rows = json.load(open(bt))
    st.dataframe(pd.DataFrame(rows), hide_index=True)
else:
    st.info("Run `python3 backtest_report.py` to generate.")

st.caption("Aegis prototype for AgentX PS-02 - Team Vanquishers. Paper trading only.")
time.sleep(2)
st.rerun()
