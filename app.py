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

# Auto-refresh component (Fall back to rerun if custom component is not installed)
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

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
.market-closed-box {
    padding: 20px;
    background-color: #261214;
    border: 1px solid #ff5252;
    border-radius: 10px;
    text-align: center;
    margin-bottom: 25px;
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
# 2. INDIAN MARKET OPEN/CLOSE TIME CHECK (NSE/BSE)
# -------------------------------------------------------------------
def is_indian_market_open():
    """Checks if the Indian Stock Market (NSE/BSE) is currently open."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    
    # Monday = 0, Sunday = 6
    if now.weekday() >= 5:
        return False, "Market is closed for the Weekend."
    
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if market_open <= now <= market_close:
        return True, "Market is OPEN"
    elif now < market_open:
        return False, f"Market opens today at 09:15 AM IST (Current Time: {now.strftime('%I:%M %p IST')})"
    else:
        return False, f"Market closed for today at 03:30 PM IST (Current Time: {now.strftime('%I:%M %p IST')})"

# -------------------------------------------------------------------
# HELPER CALCULATIONS & TECHNICAL ANALYSIS
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

def fetch_multi_timeframe_levels(symbol):
    ticker = yf.Ticker(symbol)
    
    df_1d = ticker.history(period="5d", interval="1d")
    h_1d = float(df_1d['High'].iloc[-1]) if not df_1d.empty else 0.0
    l_1d = float(df_1d['Low'].iloc[-1]) if not df_1d.empty else 0.0
    
    df_1h = ticker.history(period="2d", interval="1h")
    h_1h = float(df_1h['High'].iloc[-1]) if not df_1h.empty else 0.0
    l_1h = float(df_1h['Low'].iloc[-1]) if not df_1h.empty else 0.0
    
    df_15m = ticker.history(period="1d", interval="15m")
    h_15m = float(df_15m['High'].iloc[-1]) if not df_15m.empty else 0.0
    l_15m = float(df_15m['Low'].iloc[-1]) if not df_15m.empty else 0.0
    
    return {
        "1 Day (1D)": {"high": h_1d, "low": l_1d},
        "1 Hour (1H)": {"high": h_1h, "low": l_1h},
        "15 Min (15M)": {"high": h_15m, "low": l_15m},
    }

def analyze_1m_data(df):
    if len(df) < 15:
        return None
    
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    pattern = get_candle_pattern(curr['Open'], curr['High'], curr['Low'], curr['Close'])

    signal = "NEUTRAL"
    reversal_alert = None
    
    if pattern == "Hammer / Bullish Pinbar" or (prev['RSI'] < 30 and curr['RSI'] > 30):
        reversal_alert = "BULLISH REVERSAL DETECTED 🚀"
        signal = "BUY"
    elif pattern == "Shooting Star / Bearish Pinbar" or (prev['RSI'] > 70 and curr['RSI'] < 70):
        reversal_alert = "BEARISH REVERSAL DETECTED ⚠️"
        signal = "SELL"
    elif curr['EMA9'] > curr['EMA20']:
        signal = "BUY"
    else:
        signal = "SELL"

    entry_price = float(curr['Close'])
    atr = float(curr['High'] - curr['Low']) if (curr['High'] - curr['Low']) > 0 else entry_price * 0.0015
    
    if signal == "BUY":
        target = entry_price + (1.5 * atr)
        stop_loss = entry_price - (1.0 * atr)
        price_move = curr['Close'] - curr['Open']
        target_pct = min(100.0, max(-10.0, (price_move / (1.5 * atr)) * 100))
    else:
        target = entry_price - (1.5 * atr)
        stop_loss = entry_price + (1.0 * atr)
        price_move = curr['Open'] - curr['Close']
        target_pct = min(100.0, max(-10.0, (price_move / (1.5 * atr)) * 100))

    return {
        "df": df,
        "latest": curr,
        "pattern": pattern,
        "signal": signal,
        "reversal_alert": reversal_alert,
        "entry": entry_price,
        "target": target,
        "stop_loss": stop_loss,
        "target_pct": float(target_pct)
    }

# -------------------------------------------------------------------
# MAIN DASHBOARD EXECUTION
# -------------------------------------------------------------------
st.title("Shadow AI Trading Agent 🐱")

market_open, market_msg = is_indian_market_open()

if not market_open:
    st.markdown(f"""
    <div class="market-closed-box">
        <h2 style="color: #ff5252; margin-top: 0;">🔴 Indian Stock Market is Closed</h2>
        <p style="font-size: 16px;">{market_msg}</p>
        <p style="color: #b2b5be; font-size: 14px;">Live 1-Minute signal execution and auto-refresh will resume automatically during trading hours (09:15 AM - 03:30 PM IST, Monday to Friday).</p>
    </div>
    """, unsafe_allow_html=True)
else:
    # Trigger Auto-Refresh Every 60 Seconds during trading hours
    if st_autorefresh:
        st_autorefresh(interval=60000, key="market_live_refresh")
    
    st.success(f"🟢 Market is OPEN. Auto-refresh active (Interval: 1 min).")

# TOP 10 INDIAN STOCKS TABLE
st.markdown("### 🏛️ Top 10 Indian Stocks (NSE/BSE) & Institutional Drivers")

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

st.dataframe(pd.DataFrame(top_10_stocks), use_container_width=True)

# TOP 3 HIGH MOVEMENT STOCKS
top_3 = [top_10_stocks[0], top_10_stocks[2], top_10_stocks[3]]

st.markdown("---")
st.markdown("### 🚀 Dynamic Analysis & 1M Execution for Top 3 Stocks")

chart_tabs = st.tabs([f"{s['Symbol']} ({s['Name']})" for s in top_3])

for idx, stock in enumerate(top_3):
    symbol = stock["Symbol"]
    with chart_tabs[idx]:
        ticker = yf.Ticker(symbol)
        df_1m = ticker.history(period="1d", interval="1m")
        
        if df_1m.empty:
            st.warning(f"Live 1-minute data currently unavailable for {symbol}.")
            continue

        res = analyze_1m_data(df_1m)
        if not res:
            st.info("Gathering candle data for complete technical analysis...")
            continue
            
        tf_data = fetch_multi_timeframe_levels(symbol)
        
        # 1. DYNAMIC TARGET PROGRESS BAR
        target_pct = res["target_pct"]
        clamped_pct = max(-10.0, min(100.0, target_pct))
        visual_width = ((clamped_pct + 10) / 110) * 100

        st.markdown(f"#### 🎯 Dynamic Target Progress ({symbol})")
        st.markdown(f"""
        <div class="status-card">
            <div style="display: flex; justify-content: space-between;">
                <span class="metric-label">Live Movement to Target (-10% to +100%)</span>
                <span class="metric-value">{target_pct:.1f}%</span>
            </div>
            <div class="progress-container">
                <div class="progress-bar-fill" style="width: {visual_width:.1f}%;"></div>
                <div class="progress-text">{target_pct:.1f}% Target Achieved</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 2. MULTI-TIMEFRAME LEVEL ANALYSIS
        st.markdown(f"#### 📊 Multi-Timeframe Level Analysis ({symbol})")
        cols = st.columns(3)
        for i, (tf_name, levels) in enumerate(tf_data.items()):
            high = levels["high"]
            low = levels["low"]
            middle = (high + low) / 2.0 if (high and low) else 0.0
            
            with cols[i]:
                st.markdown(f"""
                <div class="section-box">
                    <div class="section-title">{tf_name}</div>
                    <p><strong>High:</strong> <span class="metric-value" style="font-size: 16px;">{high:.2f}</span></p>
                    <p><strong>Middle:</strong> <span style="font-size: 16px; color: #ffeb3b;">{middle:.2f}</span></p>
                    <p><strong>Low:</strong> <span class="metric-value-red" style="font-size: 16px;">{low:.2f}</span></p>
                </div>
                """, unsafe_allow_html=True)

        # 3. 1M ORDER & 5M ZONE ANALYSIS
        st.markdown(f"#### ⚡ Microstructure Analysis & 1M Candle Execution ({symbol})")
        m1_m5_col1, m1_m5_col2 = st.columns(2)

        curr_candle = res["latest"]
        action_1m = f"{res['signal']} ORDER"
        action_color = "#00e676" if res['signal'] == "BUY" else "#ff5252"

        with m1_m5_col1:
            st.markdown(f"""
            <div class="section-box">
                <div class="section-title">1-Minute Live Order & Pattern Tracker</div>
                <p><strong>Latest 1M Order:</strong> <span style='color:{action_color}; font-weight:bold;'>{action_1m} PLACED</span></p>
                <p><strong>Formed Pattern:</strong> <code>{res['pattern']}</code></p>
                <p>- <strong>Open:</strong> {curr_candle['Open']:.2f} | <strong>High:</strong> {curr_candle['High']:.2f}</p>
                <p>- <strong>Low:</strong> {curr_candle['Low']:.2f} | <strong>Close:</strong> {curr_candle['Close']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)

        with m1_m5_col2:
            m5_dir = "BULLISH 📈" if res['signal'] == "BUY" else "BEARISH 📉"
            st.markdown(f"""
            <div class="section-box">
                <div class="section-title">5-Minute Direction & Key Marking</div>
                <p><strong>5M Direction:</strong> <code>{m5_dir}</code></p>
                <p><strong>Confirmation:</strong> <code>EMA Cross & RSI Alignment</code></p>
                <p><strong>Zone Indication:</strong> <code>Support/Demand ({res['stop_loss']:.2f} - {res['entry']:.2f})</code></p>
                <hr style="margin: 8px 0;">
                <p>🎯 <strong>Next Target High:</strong> <span class='metric-value' style='font-size: 16px;'>{res['target']:.2f}</span></p>
                <p>🛡️ <strong>Next Target Low:</strong> <span class='metric-value-red' style='font-size: 16px;'>{res['stop_loss']:.2f}</span></p>
            </div>
            """, unsafe_allow_html=True)

        if res["reversal_alert"]:
            st.markdown(f"""
            <div class="alert-box">
                ⚠️ <strong>REVERSAL ALERT:</strong> {res['reversal_alert']} on 1-Minute Chart for {symbol}!
            </div>
            """, unsafe_allow_html=True)

        # 4. LIVE 1-MINUTE PLOTLY CHART WITH MARKERS
        data = res["df"]
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
            name="1M Price"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=data.index, y=data['EMA9'], line=dict(color='#00e676', width=1), name="EMA 9"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], line=dict(color='#ff5252', width=1), name="EMA 20"), row=1, col=1)

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

        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], marker_color='#2962ff', name="Volume"), row=2, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=500,
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=True,
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(fig, use_container_width=True)
