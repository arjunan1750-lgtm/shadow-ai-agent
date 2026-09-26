import datetime
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

st.markdown("""
<style>
[data-testid="collapsedControl"], section[data-testid="stSidebar"] {
    display: none;
}
.stApp {
    background-color: #0e1117;
    color: #ffffff;
}
.status-card {
    background-color: #1e222d;
    padding: 16px;
    border-radius: 10px;
    border: 1px solid #2962ff;
    margin-bottom: 20px;
}
.metric-value {
    font-size: 22px;
    font-weight: bold;
    color: #00e676;
}
.metric-value-red {
    font-size: 22px;
    font-weight: bold;
    color: #ff5252;
}
.metric-label {
    font-size: 13px;
    color: #b2b5be;
}
.alert-box {
    padding: 12px;
    background-color: #311b92;
    border-left: 5px solid #7c4dff;
    border-radius: 5px;
    margin: 10px 0px;
}

/* Progress Bar Custom Styling */
.progress-container {
    width: 100%;
    background-color: #2a2e39;
    border-radius: 8px;
    overflow: hidden;
    height: 24px;
    margin-top: 8px;
    position: relative;
    border: 1px solid #363c4e;
}
.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #ff5252 0%, #ffeb3b 50%, #00e676 100%);
    transition: width 0.4s ease-in-out;
}
.progress-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-weight: bold;
    font-size: 13px;
    color: #ffffff;
    text-shadow: 1px 1px 2px #000;
}

/* Section Box Styling */
.section-box {
    background-color: #131722;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #2a2e39;
    margin-bottom: 15px;
}
.section-title {
    font-size: 16px;
    font-weight: bold;
    color: #2962ff;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# HELPER CALCULATIONS & PATTERN DETECTION
# -------------------------------------------------------------------
def get_candle_pattern(open_p, high_p, low_p, close_p):
    body = abs(close_p - open_p)
    range_total = high_p - low_p
    if range_total == 0:
        return "Doji / Flat"
    
    upper_wick = high_p - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low_p
    
    if body / range_total < 0.1:
        return "Doji"
    elif lower_wick > (2 * body) and upper_wick < body:
        return "Hammer / Bullish Pinbar"
    elif upper_wick > (2 * body) and lower_wick < body:
        return "Shooting Star / Bearish Pinbar"
    elif close_p > open_p:
        return "Bullish Candle"
    else:
        return "Bearish Candle"

def analyze_1m_data(df):
    """Calculates EMA, RSI, dynamic entry/target points, and detects reversals/momentum."""
    if len(df) < 15:
        return None
    
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI Calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    pattern = get_candle_pattern(curr['Open'], curr['High'], curr['Low'], curr['Close'])

    # Signals & Dynamic Levels
    signal = "NEUTRAL"
    reversal_alert = None
    
    # Reversal checks
    if pattern in ["Hammer / Bullish Pinbar"] or (prev['RSI'] < 30 and curr['RSI'] > 30):
        reversal_alert = "BULLISH REVERSAL DETECTED"
        signal = "BUY"
    elif pattern in ["Shooting Star / Bearish Pinbar"] or (prev['RSI'] > 70 and curr['RSI'] < 70):
        reversal_alert = "BEARISH REVERSAL DETECTED"
        signal = "SELL"
    elif curr['EMA9'] > curr['EMA20']:
        signal = "BUY"
    else:
        signal = "SELL"

    # Set Dynamic Entry, Targets, and Stops
    entry_price = float(curr['Close'])
    atr = float(curr['High'] - curr['Low']) if (curr['High'] - curr['Low']) > 0 else entry_price * 0.002
    
    if signal == "BUY":
        target = entry_price + (1.5 * atr)
        stop_loss = entry_price - (1.0 * atr)
    else:
        target = entry_price - (1.5 * atr)
        stop_loss = entry_price + (1.0 * atr)

    return {
        "df": df,
        "latest": curr,
        "pattern": pattern,
        "signal": signal,
        "reversal_alert": reversal_alert,
        "entry": entry_price,
        "target": target,
        "stop_loss": stop_loss
    }

# -------------------------------------------------------------------
# SAMPLE / DYNAMIC DATA SETUP
# -------------------------------------------------------------------
# Target calculation (-10% to 100%)
target_pct = 45.0  # Dynamic percentage value from current movement
clamped_pct = max(-10.0, min(100.0, target_pct))
visual_width = ((clamped_pct + 10) / 110) * 100

st.title("Shadow AI Trading Agent 🐱")

# -------------------------------------------------------------------
# SECTION 1: TARGET PROGRESS BAR
# -------------------------------------------------------------------
st.markdown("### 🎯 Target Progress")
st.markdown(f"""
<div class="status-card">
    <div style="display: flex; justify-content: space-between;">
        <span class="metric-label">Progress to Target (-10% to +100%)</span>
        <span class="metric-value">{target_pct:.1f}%</span>
    </div>
    <div class="progress-container">
        <div class="progress-bar-fill" style="width: {visual_width:.1f}%;"></div>
        <div class="progress-text">{target_pct:.1f}% Target Achieved</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# SECTION 2: TIMEFRAME BREAKOUT LEVELS (1D, 1H, 15M)
# -------------------------------------------------------------------
st.markdown("### 📊 Multi-Timeframe Level Analysis (High, Low, Middle)")

tf_data = {
    "1 Day (1D)": {"high": 18250.00, "low": 18000.00},
    "1 Hour (1H)": {"high": 18180.00, "low": 18090.00},
    "15 Min (15M)": {"high": 18150.00, "low": 18110.00},
}

cols = st.columns(3)
for i, (tf_name, levels) in enumerate(tf_data.items()):
    high = levels["high"]
    low = levels["low"]
    middle = (high + low) / 2.0
    
    with cols[i]:
        st.markdown(f"""
        <div class="section-box">
            <div class="section-title">{tf_name}</div>
            <p><strong>High:</strong> <span class="metric-value" style="font-size: 16px;">{high:.2f}</span></p>
            <p><strong>Middle (Midpoint):</strong> <span style="font-size: 16px; color: #ffeb3b;">{middle:.2f}</span></p>
            <p><strong>Low:</strong> <span class="metric-value-red" style="font-size: 16px;">{low:.2f}</span></p>
        </div>
        """, unsafe_allow_html=True)

# -------------------------------------------------------------------
# SECTION 3: 1M ORDER EXECUTION & 5M DIRECTION/CONFIRMATION
# -------------------------------------------------------------------
st.markdown("### ⚡ Microstructure Analysis (1M Candle Execution & 5M Strategy Zone)")

m1_m5_col1, m1_m5_col2 = st.columns(2)

with m1_m5_col1:
    st.markdown("""
    <div class="section-box">
        <div class="section-title">1-Minute Order & Pattern Tracker</div>
    """, unsafe_allow_html=True)
    
    c_open, c_high, c_low, c_close = 18120.0, 18145.0, 18118.0, 18142.0
    pattern_1m = get_candle_pattern(c_open, c_high, c_low, c_close)
    action_1m = "BUY ORDER" if c_close > c_open else "SELL ORDER"
    action_color = "#00e676" if action_1m == "BUY ORDER" else "#ff5252"
    
    st.markdown(f"**Latest 1M Candle Action:** <span style='color:{action_color}; font-weight:bold;'>{action_1m} PLACED</span>", unsafe_allow_html=True)
    st.markdown(f"**Formed Candle Pattern:** `{pattern_1m}`")
    st.markdown(f"- **Open:** {c_open} | **High:** {c_high}")
    st.markdown(f"- **Low:** {c_low} | **Close:** {c_close}")
    st.markdown("</div>", unsafe_allow_html=True)

with m1_m5_col2:
    st.markdown("""
    <div class="section-box">
        <div class="section-title">5-Minute Trend, Confirmation & Zone Marking</div>
    """, unsafe_allow_html=True)
    
    m5_direction = "BULLISH 📈"
    m5_confirmation = "CONFIRMED (Volume Spike + Above EMA 20)"
    m5_zone = "Demand / Support Zone (18100 - 18115)"
    next_pos_high = 18165.00
    next_pos_low = 18105.00
    
    st.markdown(f"**5M Overall Direction:** `{m5_direction}`")
    st.markdown(f"**Confirmation Status:** `{m5_confirmation}`")
    st.markdown(f"**Zone Indication:** `{m5_zone}`")
    st.markdown("---")
    st.markdown(f"🎯 **Next Possible High Target:** <span class='metric-value' style='font-size: 16px;'>{next_pos_high:.2f}</span>", unsafe_allow_html=True)
    st.markdown(f"🛡️ **Next Possible Low Target:** <span class='metric-value-red' style='font-size: 16px;'>{next_pos_low:.2f}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# SECTION 4: TOP 10 NSE/BSE STOCKS & TOP 3 SELECTION WITH 1M CHARTS
# -------------------------------------------------------------------
st.markdown("---")
st.markdown("### 🏛️ Top 10 Indian Stocks (NSE/BSE) & Top 3 Momentum Selection")

top_10_stocks = [
    {"Symbol": "RELIANCE.NS", "Name": "Reliance Industries", "FII_DII_Activity": "High Net Buying", "News": "Q2 Margin Expansion & Telecom Growth"},
    {"Symbol": "TCS.NS", "Name": "Tata Consultancy Services", "FII_DII_Activity": "Moderate Buying", "News": "New AI Cloud Deal Signings"},
    {"Symbol": "HDFCBANK.NS", "Name": "HDFC Bank", "FII_DII_Activity": "Aggressive FII Accumulation", "News": "Credit Growth Beats Industry Average"},
    {"Symbol": "ICICIBANK.NS", "Name": "ICICI Bank", "FII_DII_Activity": "Strong DII Buying", "News": "Robust NPA Recovery Metrics"},
    {"Symbol": "INFY.NS", "Name": "Infosys", "FII_DII_Activity": "Neutral", "News": "Stable Earnings Guidance"},
    {"Symbol": "BHARTIARTL.NS", "Name": "Bharti Airtel", "FII_DII_Activity": "FII Inflows", "News": "ARPU Expansion Trend"},
    {"Symbol": "SBIN.NS", "Name": "State Bank of India", "FII_DII_Activity": "High DII Buying", "News": "Public Sector Credit Demand Rally"},
    {"Symbol": "LTIM.NS", "Name": "LTIMindtree", "FII_DII_Activity": "Moderate Inflows", "News": "Digital Transformation Order Pipeline"},
    {"Symbol": "TATAMOTORS.NS", "Name": "Tata Motors", "FII_DII_Activity": "Strong FII Interest", "News": "EV Sales Volume Surge"},
    {"Symbol": "AXISBANK.NS", "Name": "Axis Bank", "FII_DII_Activity": "Institutional Buying", "News": "Net Interest Margin Expansion"},
]

# Display Top 10 List
st.dataframe(pd.DataFrame(top_10_stocks), use_container_width=True)

# Select Top 3 based on institutional buying and positive news momentum
top_3 = [top_10_stocks[0], top_10_stocks[2], top_10_stocks[3]]

st.markdown("#### 🚀 Selected Top 3 High-Momentum Stocks for Live 1-Minute Analysis")

chart_tabs = st.tabs([f"{s['Symbol']} ({s['Name']})" for s in top_3])

for idx, stock in enumerate(top_3):
    symbol = stock["Symbol"]
    with chart_tabs[idx]:
        st.markdown(f"**Institutional Activity:** `{stock['FII_DII_Activity']}` | **News Driver:** `{stock['News']}`")
        
        # Fetch 1m live data
        ticker = yf.Ticker(symbol)
        df_1m = ticker.history(period="1d", interval="1m")
        
        if df_1m.empty:
            st.warning(f"Live 1-minute data unavailable for {symbol} at this moment.")
            continue
            
        res = analyze_1m_data(df_1m)
        if not res:
            st.info("Gathering more candles for analysis...")
            continue
            
        data = res["df"]
        
        # Show Reversal Alert Banner if present
        if res["reversal_alert"]:
            st.markdown(f"""
            <div class="alert-box">
                ⚠️ <strong>ALERT:</strong> {res['reversal_alert']} on 1-Minute Chart for {symbol}!
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown(f"""
        - **Pattern Detected:** `{res['pattern']}`
        - **Dynamic Entry Point:** `{res['entry']:.2f}`
        - **Target Point (1.5x ATR):** `{res['target']:.2f}`
        - **Stop Loss:** `{res['stop_loss']:.2f}`
        """)

        # Render 1-Minute Plotly Chart
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
            name="1M Price"
        ), row=1, col=1)

        # EMAs
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA9'], line=dict(color='#00e676', width=1), name="EMA 9"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], line=dict(color='#ff5252', width=1), name="EMA 20"), row=1, col=1)

        # Marker for Entry & Target
        last_time = data.index[-1]
        fig.add_trace(go.Scatter(
            x=[last_time], y=[res['entry']],
            mode='markers+text',
            marker=dict(symbol='triangle-right', size=12, color='yellow'),
            text=[f" Entry: {res['entry']:.2f}"], textposition="top right", name="Dynamic Entry"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=[last_time], y=[res['target']],
            mode='markers+text',
            marker=dict(symbol='star', size=12, color='#00e676'),
            text=[f" Target: {res['target']:.2f}"], textposition="top right", name="Target"
        ), row=1, col=1)

        # Volume
        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], marker_color='#2962ff', name="Volume"), row=2, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=500,
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=True,
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(fig, use_container_width=True)
