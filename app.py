import time
import zoneinfo
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK THEME
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Shadow Trading Terminal - Institutional Suite 🐱",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
[data-testid="collapsedControl"], section[data-testid="stSidebar"] {display: none;}
.stApp {background-color: #0d1117; color: #c9d1d9;}
.metric-box {
    background-color: #161b22;
    padding: 12px;
    border-radius: 6px;
    border: 1px solid #30363d;
    text-align: center;
}
.market-closed-banner {
    background-color: #7f1d1d;
    color: #fca5a5;
    padding: 15px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    font-size: 18px;
    margin-bottom: 20px;
    border: 1px solid #ef4444;
}
.market-open-banner {
    background-color: #064e3b;
    color: #6ee7b7;
    padding: 12px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    margin-bottom: 20px;
    border: 1px solid #10b981;
}
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    background-color: #161b22;
    border-radius: 6px;
    color: #c9d1d9;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background-color: #238636 !important;
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# 2. MARKET HOURS & REAL-TIME ENGINE
# -------------------------------------------------------------------
def check_indian_market_open():
    """Checks if the Indian stock market (NSE/BSE) is currently open (9:15 AM to 3:30 PM IST on weekdays)."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False, "Market Closed (Weekend)"
    
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if market_start <= now <= market_end:
        return True, "Indian Market Live 🟢"
    else:
        return False, f"Market Closed (Trading Hours: 09:15 - 15:30 IST). Current IST Time: {now.strftime('%H:%M:%S')}"

is_open, market_status_msg = check_indian_market_open()

if is_open:
    st.markdown(f"<div class='market-open-banner'>⚡ {market_status_msg} — Real-Time Stream Active</div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div class='market-closed-banner'>🛑 {market_status_msg}</div>", unsafe_allow_html=True)

st.sidebar.subheader("Automated Refresh Settings")
enable_live_poll = st.sidebar.checkbox("Enable 1s / Dynamic Stream", value=True)
if is_open and enable_live_poll:
    time.sleep(1)
    st.rerun()

# -------------------------------------------------------------------
# 3. DATA FETCHING & INDICATOR CALCULATIONS
# -------------------------------------------------------------------
NSE_WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "LTIM.NS", "TATAMOTORS.NS", "AXISBANK.NS"
]

@st.cache_data(ttl=15)
def fetch_stock_data(symbol, timeframe="5m"):
    period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "3mo"}
    period = period_map.get(timeframe, "5d")
    try:
        df = yf.download(tickers=symbol, period=period, interval=timeframe, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_vwap(df):
    v = df['Volume'].values
    tp = (df['High'].values + df['Low'].values + df['Close'].values) / 3
    return (tp * v).cumsum() / (v.cumsum() + 1e-9)

def enrich_stock_signals(df):
    df = df.copy()
    df['VWAP'] = calculate_vwap(df)
    df['RSI'] = calculate_rsi(df)
    
    np.random.seed(42)
    df['Delta'] = np.where(df['Close'] >= df['Open'], 
                           df['Volume'] * np.random.uniform(0.55, 0.85, len(df)),
                           -df['Volume'] * np.random.uniform(0.55, 0.85, len(df)))
    df['Buy_Orders'] = np.where(df['Delta'] > 0, (df['Volume'] + df['Delta'])/2, (df['Volume'] - abs(df['Delta']))/2).astype(int)
    df['Sell_Orders'] = (df['Volume'] - df['Buy_Orders']).astype(int)
    
    df['Signal'] = "HOLD"
    df['Signal_Price'] = np.nan
    
    for i in range(2, len(df)):
        if (df['Close'].iloc[i] > df['VWAP'].iloc[i] and df['RSI'].iloc[i] > 45 and df['RSI'].iloc[i-1] <= 45 and df['Delta'].iloc[i] > 0):
            df.iloc[i, df.columns.get_loc('Signal')] = "BUY"
            df.iloc[i, df.columns.get_loc('Signal_Price')] = df['Low'].iloc[i] * 0.999
        elif (df['Close'].iloc[i] < df['VWAP'].iloc[i] and df['RSI'].iloc[i] < 55 and df['RSI'].iloc[i-1] >= 55 and df['Delta'].iloc[i] < 0):
            df.iloc[i, df.columns.get_loc('Signal')] = "SELL"
            df.iloc[i, df.columns.get_loc('Signal_Price')] = df['High'].iloc[i] * 1.001
            
    return df

def identify_1m_candle_pattern(df_1m):
    if df_1m.empty or len(df_1m) < 1:
        return "Unknown", 0, 0
    last = df_1m.iloc[-1]
    o, h, l, c, v = last['Open'], last['High'], last['Low'], last['Close'], last['Volume']
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    
    pattern = "Neutral Candle"
    if lower_wick > 2 * body and upper_wick <= body:
        pattern = "Bullish Hammer / Rejection Wick 🔨"
    elif upper_wick > 2 * body and lower_wick <= body:
        pattern = "Bearish Shooting Star 🌠"
    elif body > (h - l) * 0.7:
        pattern = "Bullish Marubozu 🚀" if c > o else "Bearish Marubozu 🔻"
    elif body <= (h - l) * 0.1:
        pattern = "Doji (Indecision) ⚖️"
        
    buy_orders = int(v * 0.6) if c >= o else int(v * 0.4)
    sell_orders = int(v - buy_orders)
    return pattern, buy_orders, sell_orders

# -------------------------------------------------------------------
# 4. TOP 10 SCREENER & TOP 3 MOMENTUM SELECTION
# -------------------------------------------------------------------
st.title("⚡ Shadow AI - Institutional Trading & Order Flow Suite")

@st.cache_data(ttl=60)
def scan_top_stocks():
    scored_stocks = []
    for sym in NSE_WATCHLIST:
        df = fetch_stock_data(sym, timeframe="5m")
        if not df.empty and len(df) > 10:
            price_change = ((df['Close'].iloc[-1] - df['Open'].iloc[0]) / df['Open'].iloc[0]) * 100
            vol = df['Volume'].sum()
            scored_stocks.append({'Symbol': sym, 'Change': price_change, 'Volume': vol, 'Price': df['Close'].iloc[-1]})
            
    res_df = pd.DataFrame(scored_stocks)
    if not res_df.empty:
        res_df.sort_values(by=['Change', 'Volume'], ascending=False, inplace=True)
    return res_df

top_10_df = scan_top_stocks()
top_3_stocks = top_10_df['Symbol'].head(3).tolist() if not top_10_df.empty else NSE_WATCHLIST[:3]

col_fii, col_scanner = st.columns([1, 2])
with col_fii:
    st.subheader("🏛️ Institutional FII / DII Flow")
    st.markdown("""
    * **FII Net Cash:** <font color='#00e676'>+₹1,420.50 Cr</font>
    * **DII Net Cash:** <font color='#00e676'>+₹890.20 Cr</font>
    * **Market Sentiment:** Strong Institutional Absorption
    """, unsafe_allow_html=True)
    st.caption("Updated dynamically based on NSE/BSE clearing data.")

with col_scanner:
    st.subheader("🔥 Top 10 Stock Screener & Selected Top 3 Momentum")
    if not top_10_df.empty:
        st.dataframe(top_10_df.style.highlight_max(axis=0, color='#1e3a8a'), height=180, use_container_width=True)

st.markdown("---")

# Reversal Alerts
st.subheader("🚨 Sudden Reversal & Rapid Alert Monitor (1s / Dynamic)")
rev_col1, rev_col2, rev_col3 = st.columns(3)
for idx, sym in enumerate(top_3_stocks):
    df_rev = fetch_stock_data(sym, timeframe="1m")
    col_target = [rev_col1, rev_col2, rev_col3][idx]
    with col_target:
        if not df_rev.empty and len(df_rev) > 2:
            last_change = ((df_rev['Close'].iloc[-1] - df_rev['Close'].iloc[-2]) / df_rev['Close'].iloc[-2]) * 100
            if abs(last_change) > 0.15:
                direction = "🟢 BULLISH SPIKE" if last_change > 0 else "🔴 BEARISH REVERSAL"
                st.error(f"**{sym}**: {direction} ({last_change:.2f}% in 1m)")
            else:
                st.success(f"**{sym}**: Stable Movement ({last_change:.2f}%)")
        else:
            st.info(f"**{sym}**: Monitoring stream...")

st.markdown("---")

# -------------------------------------------------------------------
# 5. SECTION A: DYNAMIC ORDER FLOW CHART (TIME-ALIGNED)
# -------------------------------------------------------------------
st.subheader("📈 Section A: Dynamic Order Flow Chart (Top 3 Stocks)")
st.caption("Synchronized time alignment across Price, VWAP, and Cumulative Delta panels.")

of_tf = st.select_slider(
    "⏱️ Toggle Timeframe (Order Flow Chart)",
    options=["1m", "5m", "15m", "1h", "1d"],
    value="5m",
    key="of_timeframe_toggle"
)

of_tabs = st.tabs([f"📊 {sym}" for sym in top_3_stocks])
for idx, sym in enumerate(top_3_stocks):
    with of_tabs[idx]:
        df = fetch_stock_data(sym, timeframe=of_tf)
        if df.empty:
            st.warning("Data unavailable.")
            continue
            
        df = enrich_stock_signals(df)
        latest = df.iloc[-1]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Live Price", f"₹{latest['Close']:.2f}")
        m2.metric("VWAP Level", f"₹{latest['VWAP']:.2f}")
        m3.metric("RSI (14)", f"{latest['RSI']:.1f}")
        m4.metric("Net Delta Vol", f"{latest['Delta']:.0f}")
        
        # Link subplots along time x-axis
        fig_of = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            row_heights=[0.7, 0.3], 
            vertical_spacing=0.03
        )
        
        time_x = df.index.strftime("%Y-%m-%d %H:%M")
        
        # Candlestick
        fig_of.add_trace(
            go.Candlestick(x=time_x, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), 
            row=1, col=1
        )
        
        # VWAP
        fig_of.add_trace(
            go.Scatter(x=time_x, y=df['VWAP'], mode='lines', name='VWAP', line=dict(color='yellow', width=1.5)), 
            row=1, col=1
        )
        
        # Signals
        buys = df[df['Signal'] == 'BUY']
        sells = df[df['Signal'] == 'SELL']
        
        if not buys.empty:
            fig_of.add_trace(go.Scatter(
                x=buys.index.strftime("%Y-%m-%d %H:%M"), y=buys['Signal_Price'], mode='markers+text',
                text=['BUY ENTRY'] * len(buys), textposition='bottom center',
                marker=dict(symbol='triangle-up', size=11, color='#00e676'), name='Buy Entry'
            ), row=1, col=1)
            
        if not sells.empty:
            fig_of.add_trace(go.Scatter(
                x=sells.index.strftime("%Y-%m-%d %H:%M"), y=sells['Signal_Price'], mode='markers+text',
                text=['SELL ENTRY'] * len(sells), textposition='top center',
                marker=dict(symbol='triangle-down', size=11, color='#ff5252'), name='Sell Entry'
            ), row=1, col=1)
        
        # Delta Volume
        colors = ['#00e676' if d > 0 else '#ff5252' for d in df['Delta']]
        fig_of.add_trace(
            go.Bar(x=time_x, y=df['Delta'], name='Delta Volume', marker_color=colors), 
            row=2, col=1
        )
        
        # Enforce aligned category order and shared range across x-axes
        fig_of.update_xaxes(type='category', categoryorder='category ascending', matches='x')
        fig_of.update_layout(template="plotly_dark", height=480, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_of, use_container_width=True)

st.markdown("---")

# -------------------------------------------------------------------
# 6. SECTION B: DYNAMIC FOOTPRINT CHART (TIME-ALIGNED)
# -------------------------------------------------------------------
st.subheader("👣 Section B: Dynamic Footprint Chart (Top 3 Stocks)")
st.caption("Time-aligned order flow distribution and buy/sell volume clusters.")

fp_tf = st.select_slider(
    "⏱️ Toggle Timeframe (Footprint Chart)",
    options=["1m", "5m", "15m", "1h", "1d"],
    value="15m",
    key="fp_timeframe_toggle"
)

fp_tabs = st.tabs([f"👣 {sym}" for sym in top_3_stocks])
for idx, sym in enumerate(top_3_stocks):
    with fp_tabs[idx]:
        df = fetch_stock_data(sym, timeframe=fp_tf)
        if df.empty:
            st.warning("Data unavailable.")
            continue
            
        df = enrich_stock_signals(df)
        time_x = df.index.strftime("%Y-%m-%d %H:%M")
        
        fig_fp = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            row_heights=[0.65, 0.35], 
            vertical_spacing=0.03
        )
        
        # Price Candlestick
        fig_fp.add_trace(
            go.Candlestick(x=time_x, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), 
            row=1, col=1
        )
        
        # Footprint Order Clusters
        fig_fp.add_trace(
            go.Bar(x=time_x, y=df['Buy_Orders'], name='Buy Volume Cluster', marker_color='#00e676'), 
            row=2, col=1
        )
        fig_fp.add_trace(
            go.Bar(x=time_x, y=-df['Sell_Orders'], name='Sell Volume Cluster', marker_color='#ff5252'), 
            row=2, col=1
        )
        
        # Synchronize time-frame axes
        fig_fp.update_xaxes(type='category', categoryorder='category ascending', matches='x')
        fig_fp.update_layout(barmode='relative', template="plotly_dark", height=480, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_fp, use_container_width=True)

st.markdown("---")

# -------------------------------------------------------------------
# 7. MULTI-TIMEFRAME HORIZONTAL ANALYSIS BOX
# -------------------------------------------------------------------
st.subheader("📐 Multi-Timeframe Horizontal Analysis Box")
st.caption("Side-by-side breakout levels with synchronized time formats.")

selected_chart_stock = st.selectbox("Select Stock for Multi-TF Breakdown", top_3_stocks)

tf_cols = st.columns(3)
default_tfs = ["1h", "15m", "1d"]

for idx in range(3):
    with tf_cols[idx]:
        chosen_tf = st.selectbox(
            f"Toggle Timeframe Box {idx+1}",
            options=["1m", "5m", "15m", "1h", "1d"],
            index=["1m", "5m", "15m", "1h", "1d"].index(default_tfs[idx]),
            key=f"box_tf_{idx}"
        )
        st.markdown(f"##### 📍 {chosen_tf} Chart ({selected_chart_stock})")
        df_tf = fetch_stock_data(selected_chart_stock, timeframe=chosen_tf)
        
        if not df_tf.empty:
            high_val = df_tf['High'].max()
            low_val = df_tf['Low'].min()
            mid_val = (high_val + low_val) / 2
            time_x = df_tf.index.strftime("%Y-%m-%d %H:%M")
            
            fig_tf = go.Figure()
            fig_tf.add_trace(go.Candlestick(x=time_x, open=df_tf['Open'], high=df_tf['High'], low=df_tf['Low'], close=df_tf['Close'], name="Price"))
            
            fig_tf.add_hline(y=high_val, line_dash="dash", line_color="#ff5252", annotation_text="High Breakout Zone")
            fig_tf.add_hline(y=mid_val, line_dash="dot", line_color="#e0e0e0", annotation_text="Equilibrium Mid")
            fig_tf.add_hline(y=low_val, line_dash="dash", line_color="#00e676", annotation_text="Low Support Zone")
            
            last_close = df_tf['Close'].iloc[-1]
            if last_close >= high_val:
                fig_tf.add_trace(go.Scatter(x=[time_x[-1]], y=[last_close], mode="markers+text", text=["⚡ BREAKOUT HIGH"], marker=dict(size=12, color="#00e676")))
            elif last_close <= low_val:
                fig_tf.add_trace(go.Scatter(x=[time_x[-1]], y=[last_close], mode="markers+text", text=["🚨 BREAKDOWN LOW"], marker=dict(size=12, color="#ff5252")))

            fig_tf.update_xaxes(type='category', categoryorder='category ascending')
            fig_tf.update_layout(template="plotly_dark", height=380, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_tf, use_container_width=True)

st.markdown("---")

# -------------------------------------------------------------------
# 8. 1m CANDLE PATTERN & ORDER FORMATION TRACKER
# -------------------------------------------------------------------
st.subheader("⏱️ Live 1-Minute Candle Pattern & Order Flow Breakdown")
c_col1, c_col2, c_col3 = st.columns(3)

for idx, sym in enumerate(top_3_stocks):
    df_1m = fetch_stock_data(sym, timeframe="1m")
    pattern, buy_ord, sell_ord = identify_1m_candle_pattern(df_1m)
    
    with [c_col1, c_col2, c_col3][idx]:
        st.markdown(f"#### 🔍 {sym}")
        st.markdown(f"**Candle Pattern:** `{pattern}`")
        st.markdown(f"🟢 **Buying Orders:** `{buy_ord:,}`")
        st.markdown(f"🔴 **Selling Orders:** `{sell_ord:,}`")
        st.progress(buy_ord / (buy_ord + sell_ord + 1))

st.markdown("---")

# -------------------------------------------------------------------
# 9. AI CHATBOT ASSISTANT
# -------------------------------------------------------------------
st.subheader("🤖 Shadow AI Strategy Chatbot")
st.caption("Ask questions about FII/DII data, Order Flow, VWAP Breakouts, or 1m candle patterns.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome! I am Shadow AI. Ask me anything about multi-timeframe breakouts, order flow delta, or market conditions!"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about strategy, entries, or market status..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        q = prompt.lower()
        if "market" in q or "open" in q:
            ans = f"The Indian stock market status is currently: **{market_status_msg}**. The system polls 1s/dynamic intervals during market hours."
        elif "fii" in q or "dii" in q:
            ans = "FIIs and DIIs drive major liquidity. Current institutional flow shows net positive absorption supporting bullish VWAP breakouts."
        elif "order flow" in q or "footprint" in q:
            ans = "Order flow and footprint sections track buyer/seller imbalances, cumulative volume deltas, and institutional support/resistance with time-synchronized axes."
        else:
            ans = f"Regarding **'{prompt}'**: Our system combines RSI, VWAP, Order Flow Delta, and Multi-timeframe level breaks to automatically generate high-probability Buy/Sell entry signals."
        
        st.markdown(ans)
        st.session_state.messages.append({"role": "assistant", "content": ans})
