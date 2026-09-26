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

# -------------------------------------------------------------------
# SAMPLE / DYNAMIC DATA SETUP
# -------------------------------------------------------------------
# Target calculation (-10% to 100%)
target_pct = 45.0  # Dynamic percentage value from current movement
clamped_pct = max(-10.0, min(100.0, target_pct))
# Scale -10% -> 100% into 0% -> 100% width for the CSS bar
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

# Mock structure representing 1D, 1H, 15M candle metrics
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
    
    # 1M Live Signal / Pattern Simulation
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
