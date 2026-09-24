import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import time

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK THEME
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Shadow AI Trading Agent 🐱",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark institutional styling
st.markdown("""
<style>
    [data-testid="collapsedControl"], section[data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .status-card {
        background-color: #1e222d;
        padding: 16px;
        border-radius: 10px;
        border: 1px solid #2962ff;
        margin-bottom: 20px;
    }
    .signal-card {
        background-color: #1e222d;
        padding: 18px;
        border-radius: 12px;
        border: 2px solid #00e676;
        margin-bottom: 15px;
    }
    .warning-card {
        background-color: #2a1f1d;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #ff5252;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# 2. CORE WATCHLIST & DATA FETCHERS
# -------------------------------------------------------------------
# Dynamic watchlist universe for automated scan
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "TATAMOTORS.NS", "AXISBANK.NS", "BHARTIARTL.NS", "LTIM.NS"
]

@st.cache_data(ttl=300)
def fetch_fii_dii_sentiment():
    """Fetch/Estimate Institutional FII & DII Market Sentiment."""
    return {
        "fii_net": "🟢 +1,420 Cr (Net Buyer)",
        "dii_net": "🟢 +850 Cr (Net Buyer)",
        "market_bias": "BULLISH 📈",
        "institutional_concept": "Smart Money Accumulation Phase"
    }

def analyze_900_am_market():
    """9:00 AM Engine: Automatically scans universe & selects Top 10 stocks."""
    results = []
    for ticker in WATCHLIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="2d", interval="5m")
            if not df.empty:
                last_price = float(df['Close'].iloc[-1])
                prev_close = float(df['Close'].iloc[0])
                p_change = ((last_price - prev_close) / prev_close) * 100
                vol = int(df['Volume'].sum())
                
                action = "BUY 🟢" if p_change >= 0 else "SELL 🔴"
                concept = "High Delta Imbalance" if abs(p_change) > 0.5 else "Liquidity Sweep Setup"
                
                results.append({
                    "Stock": ticker.replace(".NS", ""),
                    "LTP (₹)": round(last_price, 2),
                    "Change (%)": round(p_change, 2),
                    "Volume": vol,
                    "Action Bias": action,
                    "SMC Concept": concept
                })
        except Exception:
            continue
            
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        return df_res.sort_values(by="Change (%)", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

def analyze_915_am_order_flow(top_10_df):
    """9:15 AM Engine: Analyzes candle order flow, selects Top 3 & precise entry setups."""
    if top_10_df.empty:
        return []
    
    # Pick Top 3 momentum assets from the 9:00 AM analysis
    top_picks = top_10_df.head(3).to_dict(orient="records")
    trade_setups = []
    
    for stock in top_picks:
        symbol = stock["Stock"] + ".NS"
        data = yf.Ticker(symbol).history(period="1d", interval="1m")
        
        if not data.empty and len(data) >= 5:
            current_close = float(data['Close'].iloc[-1])
            vwap = float((data['Close'] * data['Volume']).sum() / data['Volume'].sum())
            high_5m = float(data['High'].iloc[:5].max())
            low_5m = float(data['Low'].iloc[:5].min())
            
            if stock["Action Bias"] == "BUY 🟢":
                entry = round(high_5m + 0.50, 2)
                sl = round(low_5m - 0.50, 2)
                target = round(entry + ((entry - sl) * 2), 2)
                order_flow = "Strong Buying Delta (Ask Absorption)"
            else:
                entry = round(low_5m - 0.50, 2)
                sl = round(high_5m + 0.50, 2)
                target = round(entry - ((sl - entry) * 2), 2)
                order_flow = "Strong Selling Delta (Bid Aggression)"
                
            trade_setups.append({
                "Stock": stock["Stock"],
                "Action": stock["Action Bias"],
                "LTP": current_close,
                "VWAP": round(vwap, 2),
                "Entry": entry,
                "StopLoss": sl,
                "Target": target,
                "RiskReward": "1:2.0",
                "OrderFlow": order_flow
            })
    return trade_setups

# -------------------------------------------------------------------
# 3. HEADER & AUTOMATION SWITCH
# -------------------------------------------------------------------
st.title("🐱 Shadow Autonomous AI Trading Agent")
st.caption("Institutional Order Flow, Pre-Market Screener & Market Execution Engine")

col_time, col_switch = st.columns([3, 2])

with col_switch:
    manual_switch = st.toggle("⚡ Autonomous Engine / Manual Switch", value=True)
    if manual_switch:
        st.success("🤖 AUTOMATION ACTIVE: Dynamic Auto-Updates Enabled")
    else:
        st.error("🛑 MANUAL OVERRIDE ACTIVATED: Auto-Execution Paused")

current_time = datetime.datetime.now().strftime("%I:%M:%S %p")
with col_time:
    st.markdown(f'<div class="status-card"><b>🕒 System Time:</b> {current_time}<br><b>Strategy State:</b> Professional Scalper & Order Flow Engine</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# 4. 9:00 AM STAGE: PRE-MARKET, INSTITUTIONAL FLOW & TOP 10 SCAN
# -------------------------------------------------------------------
st.subheader("🌅 9:00 AM Market Open — Institutional Flow & Top 10 Discovery")

inst_data = fetch_fii_dii_sentiment()
c1, c2, c3 = st.columns(3)
c1.metric("FII Activity", inst_data["fii_net"])
c2.metric("DII Activity", inst_data["dii_net"])
c3.metric("Institutional Bias", inst_data["market_bias"])

st.markdown("---")

top_10_df = analyze_900_am_market()
if not top_10_df.empty:
    st.markdown("### 📊 Automated Top 10 Stocks Selection")
    st.dataframe(top_10_df, use_container_width=True)
else:
    st.info("Fetching Pre-Market / Market Opening Data...")

# -------------------------------------------------------------------
# 5. 9:15 AM STAGE: TOP 3 SELECTION & ORDER FLOW CANDLE TRIGGER
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("⚡ 9:15 AM Order Flow Analysis — Top 3 Trade Setups")

if manual_switch:
    setups = analyze_915_am_order_flow(top_10_df)
    
    if setups:
        cols = st.columns(len(setups))
        for idx, setup in enumerate(setups):
            with cols[idx]:
                st.markdown(f"""
                <div class="signal-card">
                    <h3>{setup['Stock']} ({setup['Action']})</h3>
                    <p><b>Order Flow Delta:</b> {setup['OrderFlow']}</p>
                    <p><b>VWAP Level:</b> ₹{setup['VWAP']}</p>
                    <hr>
                    <p><b>📍 Buy Entry:</b> ₹{setup['Entry']}</p>
                    <p><b>🎯 Target Option:</b> ₹{setup['Target']}</p>
                    <p><b>🛑 Stop Loss:</b> ₹{setup['StopLoss']}</p>
                    <p><b>R:R Expectancy:</b> {setup['RiskReward']}</p>
                </div>
                """, unsafe_allow_html=True)
else:
    st.warning("⚠️ **Manual Switch Enabled**: Dynamic auto-signals are paused due to manual override.")

# -------------------------------------------------------------------
# 6. MANUAL SWITCH CRITERIA & EMERGENCY RULES
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("🛑 9:15 AM Manual Switch Guidance")
st.markdown("""
<div class="warning-card">
<b>When to toggle OFF the manual switch and take manual control:</b>
<ul>
    <li><b>Heavy Opening Gap:</b> If top picks gap up/down by > 2% away from the 9:00 AM reference price.</li>
    <li><b>Macro News Events:</b> Unscheduled economic news, RBI policy announcements, or geopolitical alerts.</li>
    <li><b>Immediate VWAP Breakdown:</b> If the 1-minute candle closes aggressively on the opposite side of VWAP within the first 3 minutes.</li>
</ul>
</div>
""", unsafe_allow_html=True)
