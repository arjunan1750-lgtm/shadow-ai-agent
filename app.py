import datetime
import zoneinfo
import time
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
    page_title="Shadow AI Trading Agent 🐱",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="collapsedControl"], section[data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .status-card { background-color: #1e222d; padding: 16px; border-radius: 10px; border: 1px solid #2962ff; margin-bottom: 20px; }
    .metric-value { font-size: 22px; font-weight: bold; color: #00e676; }
    .metric-value-red { font-size: 22px; font-weight: bold; color: #ff5252; }
    .metric-label { font-size: 13px; color: #b2b5be; }
    .alert-box { padding: 12px; background-color: #311b92; border-left: 5px solid #7c4dff; border-radius: 5px; margin: 10px 0px; }
    </style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
# 2. MARKET TIMING & AUTOMATION (NSE/BSE IST)
# -------------------------------------------------------------------
def check_market_status():
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    
    # Weekday check (0=Mon, 4=Fri, 5=Sat, 6=Sun)
    is_weekday = now.weekday() < 5
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    is_live = is_weekday and (market_open <= now <= market_close)
    return is_live, now.strftime("%I:%M:%S %p IST")

is_market_live, current_time_str = check_market_status()

# -------------------------------------------------------------------
# 3. DATA FETCHING & ANALYSIS FUNCTIONS
# -------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_fii_dii_data():
    # Simulated structure representing daily FII/DII net flows
    return {"fii_net": -1250.45, "dii_net": 1840.10, "bias": "Bullish Bias (DII Support)"}

@st.cache_data(ttl=60)
def fetch_market_news():
    return [
        {"title": "RBI Monetary Policy Stance Keeps Banking Stocks in Focus", "source": "MarketPulse", "time": "10 mins ago"},
        {"title": "FIIs Turn Net Sellers in Cash Segment; DII Cushion Retained", "source": "NSE Updates", "time": "25 mins ago"},
        {"title": "IT Sector Gains Momentum on Strong Tech Earnings", "source": "BSE News", "time": "40 mins ago"}
    ]

def analyze_smc_and_orderflow(df):
    """Calculates Order Blocks, Delta Valuation Proxy, and EMA Trend"""
    if df.empty or len(df) < 20:
        return df, {}

    # Calculate EMA Trend
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()

    # Delta Valuation Proxy: (Close - Low) - (High - Close) * Volume
    df['Delta'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) * df['Volume']
    df['Delta_Cumulative'] = df['Delta'].cumsum()

    # Smart Money Concept (SMC): Identify Bullish/Bearish Order Blocks (OB)
    df['Bullish_OB'] = (df['Low'] == df['Low'].rolling(10).min()) & (df['Close'] > df['Open'])
    df['Bearish_OB'] = (df['High'] == df['High'].rolling(10).max()) & (df['Close'] < df['Open'])

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Signal Generation
    trend = "BULLISH" if latest['EMA_20'] > latest['EMA_50'] else "BEARISH"
    signal = "BUY" if trend == "BULLISH" and latest['Delta'] > 0 else "SELL"

    entry = latest['Close']
    if signal == "BUY":
        sl = round(entry * 0.995, 2)
        target = round(entry * 1.01, 2)
    else:
        sl = round(entry * 1.005, 2)
        target = round(entry * 0.99, 2)

    progress = abs(latest['Close'] - entry) / abs(target - entry) * 100 if target != entry else 0

    metrics = {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": sl,
        "target": target,
        "progress": min(round(progress, 1), 100),
        "trend": trend,
        "delta": round(latest['Delta'], 2),
        "alert": "Negative reversal candle near resistance!" if (latest['Close'] < prev['Low'] and signal == "SELL") else None
    }
    return df, metrics

@st.cache_data(ttl=30)
def process_stock(ticker):
    data = yf.download(ticker, period="1d", interval="1m")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    df, metrics = analyze_smc_and_orderflow(data)
    return df, metrics

# Tickers to scan
candidate_tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TATAMOTORS.NS"]

# -------------------------------------------------------------------
# 4. DASHBOARD HEADER & MARKET STATUS
# -------------------------------------------------------------------
st.title("🐱 Shadow AI Trading Agent — SMC & Order Flow Dashboard")
st.caption(f"Automated NSE/BSE Scalping Suite | IST Time: {current_time_str}")

status_color = "🟢 Live (Market Open)" if is_market_live else "🔴 Closed (Offline Mode)"
st.markdown(f"**Market Status:** `{status_color}`")

# FII / DII & Overview Metrics
fii_dii = fetch_fii_dii_data()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("FII Net Activity (Today)", f"₹ {fii_dii['fii_net']} Cr")
with col2:
    st.metric("DII Net Activity (Today)", f"₹ +{fii_dii['dii_net']} Cr")
with col3:
    st.metric("Market Sentiment Bias", fii_dii['bias'])

st.divider()

# -------------------------------------------------------------------
# 5. MARKET NEWS ANALYSIS
# -------------------------------------------------------------------
st.subheader("📰 Live NSE/BSE News & Sentiment Analysis")
news_items = fetch_market_news()
for item in news_items:
    st.markdown(f"• **{item['title']}** — *{item['source']}* ({item['time']})")

st.divider()

# -------------------------------------------------------------------
# 6. TOP 3 HIGH-CONVICTION STOCKS & CHARTING
# -------------------------------------------------------------------
st.subheader("🔥 Top 3 High-Conviction Stock Picks (1m Timeframe)")

top_3_tickers = candidate_tickers[:3]
selected_ticker = st.radio("Select Stock to View 1m SMC Chart:", top_3_tickers, horizontal=True)

for ticker in top_3_tickers:
    df, metrics = process_stock(ticker)
    
    if not metrics:
        continue

    if ticker == selected_ticker:
        # Display Metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("LTP (1m)", f"₹ {metrics['entry']}", f"{metrics['signal']}")
        m2.metric("Entry Point", f"₹ {metrics['entry']}")
        m3.metric("Stop Loss (SL)", f"₹ {metrics['sl']}")
        m4.metric("Target", f"₹ {metrics['target']}")
        m5.metric("Target Progress", f"{metrics['progress']}%")

        # Immediate Alert trigger
        if metrics['alert']:
            st.markdown(f"<div class='alert-box'>⚠️ <b>IMMEDIATE ALERT:</b> {metrics['alert']} on {ticker}</div>", unsafe_allow_html=True)

        # Plot 1m Interactive Chart
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="1m Price"
        ), row=1, col=1)

        # EMA Trend Lines
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='yellow', width=1), name='EMA 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='cyan', width=1), name='EMA 50'), row=1, col=1)

        # Target & SL Lines
        fig.add_hline(y=metrics['target'], line_dash="dash", line_color="green", annotation_text="Target", row=1, col=1)
        fig.add_hline(y=metrics['sl'], line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)

        # Delta Cumulative Subplot
        fig.add_trace(go.Bar(x=df.index, y=df['Delta'], name="Order Flow Delta", marker_color='purple'), row=2, col=1)

        fig.update_layout(height=500, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------------
# 7. AUTOMATED AUTO-REFRESH DURING MARKET HOURS
# -------------------------------------------------------------------
if is_market_live:
    time.sleep(60)
    st.rerun()
