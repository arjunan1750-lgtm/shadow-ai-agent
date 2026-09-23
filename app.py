import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import gtts
import base64
import io
import re
import google.generativeai as genai
from streamlit_mic_recorder import speech_to_text

# 1. Set Page Configuration with Cat Icon 🐱
st.set_page_config(
    page_title="Shadow AI Agent 🐱", 
    page_icon="🐱", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling
st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .chat-box { background-color: #1e222d; padding: 18px; border-radius: 12px; border-left: 5px solid #2962ff; margin-bottom: 15px; font-size: 15px; }
    .news-box { background-color: #1a1d24; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #2d313e; }
    .metric-card { background-color: #1e222d; padding: 15px; border-radius: 10px; border: 1px solid #2962ff; text-align: center; }
</style>
""", unsafe_allow_html=True)

# Initialize Session States for Journal & Capital Management
if "journal_logs" not in st.session_state:
    st.session_state.journal_logs = pd.DataFrame(columns=["Date", "Stock", "Type", "Entry", "Exit", "Qty", "P&L", "R:R", "Notes"])

if "initial_capital" not in st.session_state:
    st.session_state.initial_capital = 100000.0

if "target_capital" not in st.session_state:
    st.session_state.target_capital = 200000.0

if "daily_updates" not in st.session_state:
    st.session_state.daily_updates = pd.DataFrame(columns=["Date", "Daily P&L", "Total Capital"])

# API Initialization
api_key = st.secrets.get("GEMINI_API_KEY", None)
if api_key:
    genai.configure(api_key=api_key)

# Ticker Resolver
def resolve_indian_stock_ticker(query: str) -> str:
    query_clean = query.upper().strip()
    alias_map = {
        "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
        "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
        "INFOSYS": "INFY.NS", "HDFC": "HDFCBANK.NS", "HDFCBANK": "HDFCBANK.NS",
        "ICICI": "ICICIBANK.NS", "SBI": "SBIN.NS", "SUZLON": "SUZLON.NS"
    }
    for key, ticker in alias_map.items():
        if key in query_clean:
            return ticker
    if query_clean.endswith(".NS") or query_clean.endswith(".BO") or query_clean.startswith("^"):
        return query_clean
    return f"{query_clean}.NS"

@st.cache_data(ttl=60)
def fetch_stock_data(symbol: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="15m")
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def fetch_stock_news(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news
        cleaned = []
        if raw_news:
            for item in raw_news[:4]:
                title = item.get('title') or item.get('content', {}).get('title', 'Market News Update')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', 'Finance News')
                cleaned.append({"title": title, "publisher": publisher})
        return cleaned
    except Exception:
        return []

def analyze_smc_data(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 20:
        return {}
    latest_close = float(df['Close'].iloc[-1])
    day_high = float(df['High'].max())
    day_low = float(df['Low'].min())
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['TP'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    vwap_val = float(df['VWAP'].iloc[-1])

    ema_20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
    ema_50 = float(df['Close'].ewm(span=50, adjust=False).mean().iloc[-1])

    df['Price_Bin'] = df['Close'].round(1)
    poc_level = float(df.groupby('Price_Bin')['Volume'].sum().idxmax())

    demand_zone = float(df[df['Close'] < vwap_val]['Low'].min()) if not df[df['Close'] < vwap_val].empty else day_low
    supply_zone = float(df[df['Close'] > vwap_val]['High'].max()) if not df[df['Close'] > vwap_val].empty else day_high

    trend = "BULLISH 📈" if ema_20 > ema_50 else "BEARISH 📉"
    structure = "Breakout (BOS)" if latest_close > df['High'].iloc[-5:-1].max() else ("Breakdown (CHoCH)" if latest_close < df['Low'].iloc[-5:-1].min() else "Consolidation (Range)")

    bias = "STRONG BUY 🟢" if (latest_close > vwap_val and ema_20 > ema_50) else ("STRONG SELL 🔴" if latest_close < vwap_val else "NEUTRAL 🟡")

    return {
        "latest_close": round(latest_close, 2), "day_high": round(day_high, 2), "day_low": round(day_low, 2),
        "poc": round(poc_level, 2), "vwap": round(vwap_val, 2), "ema_20": round(ema_20, 2), "ema_50": round(ema_50, 2),
        "supply_zone": round(supply_zone, 2), "demand_zone": round(demand_zone, 2), "trend": trend,
        "structure": structure, "bias": bias
    }

# --- NAVIGATION TABS ---
tab_market, tab_dashboard, tab_journal = st.tabs(["📈 Market & Chart Analysis", "📊 Capital & Target Dashboard", "📓 Stock Journal"])

# ==========================================
# TAB 1: CHART ANALYSIS ENGINE
# ==========================================
with tab_market:
    st.title("🐱 Shadow AI Technical Analysis")
    spoken_text = speech_to_text(language='ml-IN', start_prompt="🎙️ Voice Input", stop_prompt="⏹️ Stop", key='voice_input')
    stock_query = st.text_input("1️⃣ Stock Name / Ticker (e.g. SUZLON, RELIANCE, TCS):", key="stock_name")
    
    condition_input = ""
    if stock_query or spoken_text:
        condition_input = st.text_input("2️⃣ Conditions (Separate with ';'):", placeholder="e.g. 1day high; supply zone; demand zone; poc; vwap; news", key="conditions_input")

    target_stock = spoken_text if spoken_text else stock_query
    if target_stock:
        target_symbol = resolve_indian_stock_ticker(target_stock)
        df = fetch_stock_data(target_symbol)
        metrics = analyze_smc_data(df)
        raw_conditions = [c.strip().lower() for c in condition_input.split(";") if c.strip()] if condition_input else []

        if not df.empty:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.8])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)

            if any("ema" in c for c in raw_conditions):
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'].ewm(span=20).mean(), line=dict(color='#ffb74d'), name="20 EMA"), row=1, col=1)
            if any("high" in c for c in raw_conditions) or not raw_conditions:
                fig.add_hline(y=metrics['day_high'], line_dash="dash", line_color="#00e676", annotation_text=f"High: ₹{metrics['day_high']}", row=1, col=1)
            if any("low" in c for c in raw_conditions) or not raw_conditions:
                fig.add_hline(y=metrics['day_low'], line_dash="dash", line_color="#ff5252", annotation_text=f"Low: ₹{metrics['day_low']}", row=1, col=1)
            if any("supply" in c for c in raw_conditions):
                fig.add_hline(y=metrics['supply_zone'], line_color="#d50000", annotation_text=f"Supply: ₹{metrics['supply_zone']}", row=1, col=1)
            if any("demand" in c for c in raw_conditions):
                fig.add_hline(y=metrics['demand_zone'], line_color="#00c853", annotation_text=f"Demand: ₹{metrics['demand_zone']}", row=1, col=1)
            if any("vwap" in c for c in raw_conditions):
                fig.add_hline(y=metrics['vwap'], line_dash="dash", line_color="#ff4081", annotation_text=f"VWAP: ₹{metrics['vwap']}", row=1, col=1)
            if any("poc" in c for c in raw_conditions) or not raw_conditions:
                fig.add_hline(y=metrics['poc'], line_dash="dot", line_color="#ab47bc", annotation_text=f"POC: ₹{metrics['poc']}", row=1, col=1)

            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#2962ff'), row=2, col=1)
            fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            col_news, col_signal = st.columns([1, 1])
            with col_news:
                st.subheader(f"📰 Live News: {target_symbol}")
                for item in fetch_stock_news(target_symbol):
                    st.markdown(f'<div class="news-box"><b>{item["publisher"]}</b><br>{item["title"]}</div>', unsafe_allow_html=True)

            with col_signal:
                st.subheader("🎯 Trade Signal")
                st.write(f"**Bias:** {metrics.get('bias')}")
                st.write(f"**Trend:** {metrics.get('trend')} | **Structure:** {metrics.get('structure')}")
                st.write(f"**Supply Target:** ₹{metrics.get('supply_zone')} | **Demand Stop:** ₹{metrics.get('demand_zone')}")

# ==========================================
# TAB 2: CAPITAL & TARGET DASHBOARD
# ==========================================
with tab_dashboard:
    st.title("📊 Financial Target & Capital Dashboard")

    col_cap1, col_cap2 = st.columns(2)
    with col_cap1:
        st.session_state.initial_capital = st.number_input("Starting Capital (₹):", value=st.session_state.initial_capital, step=5000.0)
    with col_cap2:
        st.session_state.target_capital = st.number_input("Target Capital (₹):", value=st.session_state.target_capital, step=10000.0)

    # Daily Profit Update Input
    st.subheader("➕ Add Today's Profit / Loss")
    c_date, c_pnl, c_btn = st.columns([2, 2, 1])
    update_date = c_date.date_input("Date:", key="pnl_date")
    daily_pnl = c_pnl.number_input("Profit / Loss Amount (₹):", value=0.0, step=500.0, key="pnl_val")

    if c_btn.button("Update Capital"):
        current_total = st.session_state.initial_capital + st.session_state.daily_updates["Daily P&L"].sum() + daily_pnl
        new_row = pd.DataFrame([{"Date": str(update_date), "Daily P&L": daily_pnl, "Total Capital": current_total}])
        st.session_state.daily_updates = pd.concat([st.session_state.daily_updates, new_row], ignore_index=True)
        st.success("Capital updated successfully!")

    # Calculate Capital Analytics
    total_pnl = st.session_state.daily_updates["Daily P&L"].sum() if not st.session_state.daily_updates.empty else 0.0
    current_balance = st.session_state.initial_capital + total_pnl
    growth_pct = ((current_balance - st.session_state.initial_capital) / st.session_state.initial_capital) * 100
    
    distance_to_target = st.session_state.target_capital - current_balance
    target_pct_remaining = (distance_to_target / st.session_state.target_capital) * 100 if st.session_state.target_capital > 0 else 0

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Capital", f"₹{current_balance:,.2f}")
    m2.metric("Total P&L Growth", f"{growth_pct:+.2f}%", f"₹{total_pnl:,.2f}")
    m3.metric("Target Goal", f"₹{st.session_state.target_capital:,.2f}")
    m4.metric("Distance to Target", f"₹{distance_to_target:,.2f}", f"{target_pct_remaining:.1f}% remaining")

    st.progress(min(max(current_balance / st.session_state.target_capital, 0.0), 1.0))

    if not st.session_state.daily_updates.empty:
        st.subheader("📈 Capital Growth Progress")
        st.line_chart(st.session_state.daily_updates.set_index("Date")["Total Capital"])

# ==========================================
# TAB 3: STOCK JOURNAL & DYNAMIC AI RISK:REWARD
# ==========================================
with tab_journal:
    st.title("📓 Trade Journal & AI Risk:Reward Calculator")

    col_j1, col_j2 = st.columns([2, 1])

    with col_j1:
        st.subheader("📝 Log New Trade")
        with st.form("trade_form"):
            tf_stock = st.text_input("Stock Symbol (e.g. SUZLON)")
            tf_type = st.selectbox("Type", ["BUY", "SELL"])
            tf_entry = st.number_input("Entry Price (₹)", min_value=0.1, step=1.0)
            tf_exit = st.number_input("Target / Exit Price (₹)", min_value=0.1, step=1.0)
            tf_sl = st.number_input("Stop Loss (₹)", min_value=0.1, step=1.0)
            tf_qty = st.number_input("Quantity", min_value=1, value=100)
            tf_notes = st.text_area("Trade Setup / Strategy Notes")
            submit = st.form_submit_button("Save Trade Log")

            if submit and tf_entry > 0 and tf_sl > 0:
                pnl = (tf_exit - tf_entry) * tf_qty if tf_type == "BUY" else (tf_entry - tf_exit) * tf_qty
                risk = abs(tf_entry - tf_sl)
                reward = abs(tf_exit - tf_entry)
                rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

                new_trade = pd.DataFrame([{
                    "Date": str(pd.Timestamp.now().date()), "Stock": tf_stock.upper(), "Type": tf_type,
                    "Entry": tf_entry, "Exit": tf_exit, "Qty": tf_qty, "P&L": round(pnl, 2), "R:R": f"1:{rr_ratio}", "Notes": tf_notes
                }])
                st.session_state.journal_logs = pd.concat([st.session_state.journal_logs, new_trade], ignore_index=True)
                st.success("Trade added to journal!")

    with col_j2:
        st.subheader("🤖 AI Dynamic Risk:Reward Assister")
        calc_entry = st.number_input("Entry Price", value=100.0, key="c_entry")
        calc_sl = st.number_input("Stop Loss", value=95.0, key="c_sl")
        calc_target = st.number_input("Target Price", value=115.0, key="c_tgt")
        max_risk_amount = st.number_input("Max Risk Per Trade (₹)", value=2000.0, key="c_risk")

        risk_per_share = abs(calc_entry - calc_sl)
        reward_per_share = abs(calc_target - calc_entry)
        
        if risk_per_share > 0:
            rr = reward_per_share / risk_per_share
            suggested_qty = int(max_risk_amount / risk_per_share)
            st.markdown(f"### R:R Ratio: **1 : {rr:.2f}**")
            st.info(f"💡 **Suggested Position Size:** {suggested_qty} shares (Max Risk: ₹{max_risk_amount})")
            
            if rr < 1.5:
                st.warning("⚠️ Poor Risk:Reward ratio (< 1.5). Consider adjusting entry or target.")
            else:
                st.success("✅ Good Trade Setup with high expectancy.")
        else:
            st.error("Stop Loss cannot equal Entry Price.")

    st.markdown("---")
    st.subheader("📋 Trade Logs History")
    if not st.session_state.journal_logs.empty:
        st.dataframe(st.session_state.journal_logs, use_container_width=True)
    else:
        st.info("No trade logs available yet.")
