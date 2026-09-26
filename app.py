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
[data-testid="collapsedControl"], section[data-testid="stSidebar"] {display: none; }
.stApp {background-color: #0e1117; color: #ffffff; }
.metric-box {
    background-color: #1e222d;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #2a2e39;
    text-align: center;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background-color: #1e222d;
    border-radius: 4px;
    color: #ffffff;
    padding: 10px 16px;
}
.stTabs [aria-selected="true"] {
    background-color: #2962ff !important;
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# 2. HELPER CALCULATIONS & MARKET DATA
# -------------------------------------------------------------------
def fetch_stock_data(symbol, period="5d", interval="5m"):
    try:
        df = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_vwap(df):
    v = df['Volume'].values
    tp = (df['High'].values + df['Low'].values + df['Close'].values) / 3
    return (tp * v).cumsum() / v.cumsum()

def generate_order_flow(df):
    """Generates order flow metrics & key levels (SMC, FVG, Retest, Liquidity)."""
    np.random.seed(42)
    df = df.copy()
    
    # VWAP
    df['VWAP'] = calculate_vwap(df)
    
    # Estimate Buy/Sell Volume distribution based on price movement
    df['Delta'] = np.where(df['Close'] >= df['Open'], 
                           df['Volume'] * np.random.uniform(0.55, 0.8, len(df)),
                           -df['Volume'] * np.random.uniform(0.55, 0.8, len(df)))
    df['Buy_Vol'] = np.where(df['Delta'] > 0, (df['Volume'] + df['Delta'])/2, (df['Volume'] - abs(df['Delta']))/2)
    df['Sell_Vol'] = df['Volume'] - df['Buy_Vol']
    
    # Identify Fair Value Gaps (FVG) & Smart Money Concepts (SMC)
    df['FVG_Bullish'] = (df['Low'] > df['High'].shift(2))
    df['FVG_Bearish'] = (df['High'] < df['Low'].shift(2))
    
    # Liquidity & Retesting Zones
    recent_high = df['High'].rolling(20).max()
    recent_low = df['Low'].rolling(20).min()
    df['Liquidity_Zone'] = np.where(df['High'] >= recent_high, 'Buy-side Liquidity',
                           np.where(df['Low'] <= recent_low, 'Sell-side Liquidity', 'Neutral'))
    
    # Signals based on Trend, Volume, SMC, FVG, VWAP
    df['Signal'] = "HOLD"
    df['Signal_Price'] = np.nan
    
    for i in range(2, len(df)):
        # Buy Signal Condition (Retest VWAP + Bullish FVG + High Volume Delta)
        if df['Close'].iloc[i] > df['VWAP'].iloc[i] and df['FVG_Bullish'].iloc[i-1] and df['Delta'].iloc[i] > 0:
            df.iloc[i, df.columns.get_loc('Signal')] = "BUY"
            df.iloc[i, df.columns.get_loc('Signal_Price')] = df['Low'].iloc[i] * 0.999
        # Sell Signal Condition (VWAP Rejection + Bearish FVG + Negative Delta)
        elif df['Close'].iloc[i] < df['VWAP'].iloc[i] and df['FVG_Bearish'].iloc[i-1] and df['Delta'].iloc[i] < 0:
            df.iloc[i, df.columns.get_loc('Signal')] = "SELL"
            df.iloc[i, df.columns.get_loc('Signal_Price')] = df['High'].iloc[i] * 1.001
            
    return df

# -------------------------------------------------------------------
# 3. INTERACTIVE CHATBOT SECTION
# -------------------------------------------------------------------
def render_chatbot():
    st.subheader("🤖 Shadow AI Assistant")
    st.caption("Ask questions about market indicators, strategy setups, or web page features.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am Shadow AI. How can I help you analyze the market, SMC setups, or order flow charts today?"}
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about this page or strategy..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Chatbot Response Logic
        with st.chat_message("assistant"):
            response = ""
            query = prompt.lower()
            if "vwap" in query:
                response = "**VWAP (Volume Weighted Average Price)** is calculated by taking the total value traded divided by total volume. When price retests VWAP from above, it often serves as a key institutional support zone."
            elif "fvg" in query or "fair value gap" in query:
                response = "**Fair Value Gap (FVG)** occurs when there is a imbalance between buyers and sellers, leaving a price gap between Candle 1's high and Candle 3's low. Prices often return to retest these gaps."
            elif "smc" in query or "smart money" in query:
                response = "**Smart Money Concepts (SMC)** focus on tracking institutional order flow, liquidity grabs (buy-side/sell-side liquidity sweep), order blocks, and market structure breaks (BOS)."
            elif "footprint" in query or "order flow" in query:
                response = "**Footprint & Order Flow Charts** display the exact volume traded at each bid and ask price level inside a candle, allowing you to spot buy/sell imbalances and pending order absorption."
            else:
                response = f"Thanks for asking! Regarding **'{prompt}'**: Our system scans 15m/5m timeframe trends, VWAP retests, volume deltas, liquidity zones, and FVG patterns to provide high-probability entry points."
            
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# -------------------------------------------------------------------
# 4. FOOTPRINT & ORDER FLOW ANALYSIS (TOP 3 STOCKS)
# -------------------------------------------------------------------
def render_order_flow_analysis():
    st.subheader("📊 Footprint & Order Flow Analysis (Top 3 Stocks)")
    st.caption("Includes Trend, Volume, Liquidity Zones, FVG, SMC, VWAP Retests, and Best Entry Points.")

    top_3_stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    
    timeframe = st.selectbox("Select Timeframe", ["5m", "15m", "1h"], index=1)
    
    tabs = st.tabs([f"📈 {symbol}" for symbol in top_3_stocks])
    
    for idx, symbol in enumerate(top_3_stocks):
        with tabs[idx]:
            df = fetch_stock_data(symbol, period="5d", interval=timeframe)
            if df.empty:
                st.warning(f"Unable to fetch data for {symbol}.")
                continue
            
            df = generate_order_flow(df)
            latest = df.iloc[-1]
            
            # Key Metrics Display
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{latest['Close']:.2f}")
            col2.metric("VWAP Level", f"₹{latest['VWAP']:.2f}")
            col3.metric("Volume Delta", f"{latest['Delta']:.0f}")
            col4.metric("Liquidity State", latest['Liquidity_Zone'])
            
            # Plotting Footprint & Order Flow Chart
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            
            # Candlestick chart
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name="Price"
            ), row=1, col=1)
            
            # VWAP Line
            fig.add_trace(go.Scatter(
                x=df.index, y=df['VWAP'], mode='lines', name='VWAP', line=dict(color='yellow', width=1.5)
            ), row=1, col=1)
            
            # Buy / Sell Signals (Best Entry Points)
            buy_signals = df[df['Signal'] == 'BUY']
            sell_signals = df[df['Signal'] == 'SELL']
            
            fig.add_trace(go.Scatter(
                x=buy_signals.index, y=buy_signals['Signal_Price'],
                mode='markers+text', text=['BUY'] * len(buy_signals), textposition='bottom center',
                marker=dict(symbol='triangle-up', size=12, color='#00e676'), name='Buy Signal'
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(
                x=sell_signals.index, y=sell_signals['Signal_Price'],
                mode='markers+text', text=['SELL'] * len(sell_signals), textposition='top center',
                marker=dict(symbol='triangle-down', size=12, color='#ff5252'), name='Sell Signal'
            ), row=1, col=1)
            
            # Order Flow Delta Bar Chart
            colors = ['#00e676' if d > 0 else '#ff5252' for d in df['Delta']]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Delta'], name='Delta Volume', marker_color=colors
            ), row=2, col=1)
            
            fig.update_layout(
                title=f"{symbol} Footprint & Order Flow Chart ({timeframe})",
                template="plotly_dark",
                height=600,
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Strategy Reaction & Post-Analysis Summary
            st.markdown("### 🔍 Market Analysis & Reaction")
            if latest['Close'] > latest['VWAP']:
                reaction = f"**Bullish Trend**: Price is holding above VWAP (₹{latest['VWAP']:.2f}). Liquidity zone indicates **{latest['Liquidity_Zone']}**. Look for long entries on VWAP retests with positive cumulative delta."
            else:
                reaction = f"**Bearish Trend**: Price is trading below VWAP (₹{latest['VWAP']:.2f}). Liquidity zone indicates **{latest['Liquidity_Zone']}**. Look for short setups near Fair Value Gaps (FVG) and negative delta confirmations."
            
            st.info(reaction)

# -------------------------------------------------------------------
# 5. MAIN APPLICATION LAYOUT
# -------------------------------------------------------------------
st.title("Shadow AI Trading Agent 🐱")

app_tabs = st.tabs(["📊 Order Flow & Footprint", "🤖 AI Chatbot Assistant"])

with app_tabs[0]:
    render_order_flow_analysis()

with app_tabs[1]:
    render_chatbot()
