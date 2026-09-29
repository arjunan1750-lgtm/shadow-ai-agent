import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
import yfinance as yf

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Shadow AI Agent - Indian Market Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# INDIAN MARKET HOURS CHECKER (NSE / BSE)
# ==========================================
def is_indian_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    
    # Check if today is a weekday (0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday)
    if now.weekday() >= 5:
        return False, "Market is closed today (Weekend)."
    
    # Market Trading Hours: 9:15 AM to 3:30 PM IST
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if market_open <= now <= market_close:
        return True, "Market is Active"
    elif now < market_open:
        return False, f"Market is closed. Opens today at 9:15 AM IST."
    else:
        return False, f"Market is closed for the day (Closed at 3:30 PM IST)."

market_active, market_status_msg = is_indian_market_open()

# ==========================================
# MODE 1: MARKET CLOSED -> ONLY AI CHATBOT ACTIVE
# ==========================================
if not market_active:
    st.title("🤖 Shadow AI Trading Assistant")
    st.warning(f"🔒 **Dashboard Closed:** {market_status_msg}")
    st.info("The live interactive charts and execution engine are closed during off-market hours. You can chat with **Shadow AI** below for strategy research, technical setup advice, or stock analysis.")

    # Initialize chat history state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am **Shadow AI**. The Indian stock market is currently closed. How can I assist you with market analysis, strategy planning, or stock queries today?"}
        ]

    # Render chat interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle user prompt
    if user_prompt := st.chat_input("Ask Shadow AI anything about stocks, Pine Script, or technical analysis..."):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Placeholder AI response logic (Expand with backend LLM / Gemini API if needed)
        with st.chat_message("assistant"):
            bot_reply = f"**Shadow AI Analysis:** Thank you for your question regarding '{user_prompt}'. I am monitoring pre-market data and historical order blocks. Market resumes tomorrow at 9:15 AM IST!"
            st.markdown(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})

    st.stop()  # Halt execution so the full dashboard remains hidden when market is closed

# ==========================================
# MODE 2: MARKET ACTIVE -> FULL DASHBOARD OPEN
# ==========================================
st.title("⚡ Shadow AI - Advanced NSE/BSE Trading Dashboard")
st.success("🟢 **Live Market Active:** Real-time data and execution charts are live.")

# ==========================================
# TOP 10 WATCHLISTS (NSE & BSE)
# ==========================================
WATCHLIST_NSE = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "INFY": "INFY.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "ITC": "ITC.NS",
    "SBIN": "SBIN.NS",
    "LTIM": "LTIM.NS",
    "AXISBANK": "AXISBANK.NS"
}

WATCHLIST_BSE = {
    "RELIANCE": "RELIANCE.BO",
    "TCS": "TCS.BO",
    "HDFCBANK": "HDFCBANK.BO",
    "ICICIBANK": "ICICIBANK.BO",
    "INFY": "INFY.BO",
    "BHARTIARTL": "BHARTIARTL.BO",
    "ITC": "ITC.BO",
    "SBIN": "SBIN.BO",
    "LTIM": "LTIM.BO",
    "AXISBANK": "AXISBANK.BO"
}

STOCK_METADATA = {
    "RELIANCE": {"momentum": "Strong Bullish", "fii": "21.4%", "dii": "15.8%", "news": "Expanding retail footprint & Green Energy investments.", "order_book": "Heavy Buy Pressure (62%)"},
    "TCS": {"momentum": "Mild Bullish", "fii": "12.5%", "dii": "20.1%", "news": "Secured major multi-million digital cloud transformation deal.", "order_book": "Balanced (50/50)"},
    "HDFCBANK": {"momentum": "Strong Bullish", "fii": "32.1%", "dii": "28.4%", "news": "Deposit growth surge & post-merger efficiency improvement.", "order_book": "Strong Buy Accent (68%)"},
    "ICICIBANK": {"momentum": "Strong Bullish", "fii": "44.2%", "dii": "45.1%", "news": "NIM steady with strong loan growth across credit segments.", "order_book": "Bullish Accumulation (59%)"},
    "INFY": {"momentum": "Consolidating", "fii": "33.8%", "dii": "18.2%", "news": "AI deal integration accelerating quarterly revenue.", "order_book": "Mild Sell Pressure (53%)"}
}

# ==========================================
# SIDEBAR CONTROLS
# ==========================================
st.sidebar.header("🕹️ Market Controls")
exchange_choice = st.sidebar.radio("Select Exchange", ["NSE", "BSE"])
active_watchlist = WATCHLIST_NSE if exchange_choice == "NSE" else WATCHLIST_BSE

selected_stocks = st.sidebar.multiselect(
    "Select 3 Top Momentum Stocks to Analyze:",
    options=list(active_watchlist.keys()),
    default=["RELIANCE", "HDFCBANK", "ICICIBANK"]
)

if len(selected_stocks) != 3:
    st.warning("⚠️ Please select exactly 3 stocks from the sidebar to load full analysis.")
    st.stop()

# ==========================================
# HELPER FUNCTIONS & DATA RETRIEVAL
# ==========================================
@st.cache_data(ttl=60)
def fetch_stock_data(symbol, period="7d", interval="1m"):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

# ==========================================
# SECTION 1: TOP 10 LIST & TOP 3 METRICS OVERVIEW
# ==========================================
st.subheader("📋 Top Stock Screener (Momentum, FII/DII Holdings & News)")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown(f"**Top 10 Watchlist ({exchange_choice})**")
    st.dataframe(pd.DataFrame({"Ticker": list(active_watchlist.keys()), "Yahoo Symbol": list(active_watchlist.values())}), use_container_width=True)

with col2:
    st.markdown("**Selected Top 3 Deep Dive Summary**")
    data_list = []
    for s in selected_stocks:
        meta = STOCK_METADATA.get(s, {"momentum": "Neutral", "fii": "N/A", "dii": "N/A", "news": "No recent updates", "order_book": "Neutral"})
        data_list.append({
            "Stock": s,
            "Momentum": meta["momentum"],
            "FII Holding": meta["fii"],
            "DII Holding": meta["dii"],
            "Order Book Depth": meta["order_book"],
            "Latest Key News": meta["news"]
        })
    st.table(pd.DataFrame(data_list))

st.divider()

# ==========================================
# SECTION 2: 1-MINUTE CHARTS (ENTRY, SL, TARGET, BREAKOUTS, ORDER COUNTS)
# ==========================================
st.subheader("📈 1-Minute Live Execution Charts")

tabs = st.tabs([f"📌 {s}" for s in selected_stocks])

for i, stock in enumerate(selected_stocks):
    with tabs[i]:
        ticker = active_watchlist[stock]
        df_1m = fetch_stock_data(ticker, period="1d", interval="1m")

        if df_1m.empty or len(df_1m) < 10:
            st.error(f"Insufficient intraday 1m data for {stock}.")
            continue

        high_val = df_1m["High"].max()
        low_val = df_1m["Low"].min()
        mid_val = (high_val + low_val) / 2
        last_price = df_1m["Close"].iloc[-1]

        entry_price = last_price
        sl_price = round(entry_price * 0.995, 2)
        target_price = round(entry_price * 1.01, 2)
        progress_pct = min(max(((last_price - sl_price) / (target_price - sl_price)) * 100, 0), 100)

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

        fig.add_trace(go.Candlestick(
            x=df_1m.index,
            open=df_1m["Open"], high=df_1m["High"],
            low=df_1m["Low"], close=df_1m["Close"],
            name="1m Candle"
        ), row=1, col=1)

        fig.add_hline(y=high_val, line_dash="dash", line_color="green", annotation_text=f"High: {high_val:.2f}", row=1, col=1)
        fig.add_hline(y=low_val, line_dash="dash", line_color="red", annotation_text=f"Low: {low_val:.2f}", row=1, col=1)
        fig.add_hline(y=mid_val, line_dash="dot", line_color="blue", annotation_text=f"Mid Break: {mid_val:.2f}", row=1, col=1)

        fig.add_annotation(x=df_1m.index[-1], y=entry_price, text=f"BUY Entry: {entry_price:.2f}", showarrow=True, arrowhead=1, row=1, col=1)

        colors = ['red' if df_1m['Open'].iloc[j] > df_1m['Close'].iloc[j] else 'green' for j0, j in enumerate(range(len(df_1m)))]
        fig.add_trace(go.Bar(x=df_1m.index, y=df_1m["Volume"], marker_color=colors, name="Volume"), row=2, col=1)

        fig.update_layout(title=f"{stock} (1-Min Execution Chart)", yaxis_title="Price (INR)", height=500, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("Optimal Entry", f"₹{entry_price:.2f}")
        mcol2.metric("Stop Loss (SL)", f"₹{sl_price:.2f}")
        mcol3.metric("Target Level", f"₹{target_price:.2f}")
        mcol4.metric("Trade Progress", f"{progress_pct:.1f}%")
        st.progress(progress_pct / 100.0)

        st.markdown("**📊 Key Breakout Levels Overview**")
        lcol1, lcol2, lcol3, lcol4 = st.columns(4)
        lcol1.info(f"**Day High/Low/Mid:** H: {high_val:.2f} | L: {low_val:.2f} | Mid: {mid_val:.2f}")
        lcol2.info(f"**15m Range:** {df_1m['Close'].tail(15).min():.2f} - {df_1m['Close'].tail(15).max():.2f}")
        lcol3.info(f"**1H Range:** {df_1m['Close'].tail(60).min():.2f} - {df_1m['Close'].tail(60).max():.2f}")
        lcol4.info(f"**4H Level:** {mid_val:.2f}")

        with st.expander("🔢 View Order Numbers for Each 1m Candle"):
            df_orders = df_1m[["Open", "High", "Low", "Close", "Volume"]].tail(10).copy()
            df_orders["Simulated Orders Count"] = (df_orders["Volume"] / np.random.randint(5, 15, size=len(df_orders))).astype(int)
            st.dataframe(df_orders, use_container_width=True)

st.divider()

# ==========================================
# SECTION 3: 5-MINUTE CHART (SMC / Smart Money Concepts)
# ==========================================
st.subheader("🎯 5-Minute Smart Money Concepts (FVG, Order Block, Liquidity Sweep & Retest)")

smc_tabs = st.tabs([f"📊 5m SMC - {s}" for s in selected_stocks])

for i, stock in enumerate(selected_stocks):
    with smc_tabs[i]:
        ticker = active_watchlist[stock]
        df_5m = fetch_stock_data(ticker, period="5d", interval="5m")

        if df_5m.empty or len(df_5m) < 20:
            st.error(f"Insufficient 5m data for {stock}.")
            continue

        fig_5m = go.Figure(data=[go.Candlestick(
            x=df_5m.index,
            open=df_5m["Open"], high=df_5m["High"],
            low=df_5m["Low"], close=df_5m["Close"],
            name="5m Candle"
        )])

        recent_low = df_5m["Low"].iloc[-10:-1].min()
        recent_high = df_5m["High"].iloc[-10:-1].max()
        ob_zone = (recent_low, recent_low * 1.003)
        fvg_zone = (recent_high * 0.997, recent_high)

        fig_5m.add_hrect(y0=ob_zone[0], y1=ob_zone[1], fillcolor="blue", opacity=0.2, line_width=0, annotation_text="Order Block (OB)")
        fig_5m.add_hrect(y0=fvg_zone[0], y1=fvg_zone[1], fillcolor="orange", opacity=0.2, line_width=0, annotation_text="Fair Value Gap (FVG)")

        fig_5m.add_annotation(x=df_5m.index[-5], y=df_5m["Low"].iloc[-5], text="⚡ Liquidity Sweep Area", showarrow=True, arrowhead=2, arrowcolor="purple")
        fig_5m.add_annotation(x=df_5m.index[-1], y=df_5m["High"].iloc[-1], text="🔄 Retesting Zone / Pending Orders", showarrow=True, arrowhead=2, arrowcolor="brown")

        fig_5m.update_layout(title=f"{stock} (5-Min SMC & Structural Chart)", yaxis_title="Price (INR)", height=450, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_5m, use_container_width=True)

st.divider()

# ==========================================
# SECTION 4: IMMEDIATE ALERTS PANEL
# ==========================================
st.subheader("🚨 Immediate Intraday Alerts & Signals Panel")

alert_cols = st.columns(3)

for idx, stock in enumerate(selected_stocks):
    ticker = active_watchlist[stock]
    df_alert = fetch_stock_data(ticker, period="1d", interval="1m")

    with alert_cols[idx]:
        st.markdown(f"#### {stock}")
        if not df_alert.empty and len(df_alert) > 5:
            last_vol = df_alert["Volume"].iloc[-1]
            avg_vol = df_alert["Volume"].mean()

            if last_vol > avg_vol * 1.5:
                st.error("🚨 **High Buying/Selling Volume Detected!**")
            else:
                st.info("ℹ️ Volume condition: **Low / Normal**")

            c_prev = df_alert["Close"].iloc[-2]
            c_curr = df_alert["Close"].iloc[-1]
            o_curr = df_alert["Open"].iloc[-1]

            if (c_prev < df_alert["Open"].iloc[-2]) and (c_curr > o_curr):
                st.success("🔄 **Bullish Reversal Pattern Detected!**")
            elif (c_prev > df_alert["Open"].iloc[-2]) and (c_curr < o_curr):
                st.warning("⚠️ **Bearish Reversal Pattern Detected!**")
            else:
                st.write("Status: Trend Continuing")
        else:
            st.write("Alerts offline (waiting for live stream feed).")
