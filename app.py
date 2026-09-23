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

# 1. Page Configuration & Dark Theme with Cat Icon 🐱
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
    .bias-card { background-color: #1e222d; padding: 15px; border-radius: 10px; border: 1px solid #2962ff; margin-bottom: 10px; }
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

# Dynamic Ticker Resolver
def resolve_indian_stock_ticker(query: str) -> str:
    query_clean = query.upper().strip()
    alias_map = {
        "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
        "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
        "INFOSYS": "INFY.NS", "HDFC": "HDFCBANK.NS", "HDFCBANK": "HDFCBANK.NS",
        "ICICI": "ICICIBANK.NS", "SBI": "SBIN.NS", "SUZLON": "SUZLON.NS",
        "TATA MOTORS": "TATAMOTORS.NS", "TATAMOTORS": "TATAMOTORS.NS"
    }
    for key, ticker in alias_map.items():
        if key in query_clean:
            return ticker

    if query_clean.endswith(".NS") or query_clean.endswith(".BO") or query_clean.startswith("^"):
        return query_clean

    return f"{query_clean}.NS"

# Fetch Stock Data Dynamically
@st.cache_data(ttl=60)
def fetch_stock_data(symbol: str, period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
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

# Technical & Smart Money Engine
def analyze_smc_data(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 5:
        return {}

    latest_close = float(df['Close'].iloc[-1])
    day_high = float(df['High'].max())
    day_low = float(df['Low'].min())
    
    # VWAP Calculation
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['TP'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    vwap_val = float(df['VWAP'].iloc[-1])

    # EMAs
    ema_20 = float(df['Close'].ewm(span=min(20, len(df)), adjust=False).mean().iloc[-1])
    ema_50 = float(df['Close'].ewm(span=min(50, len(df)), adjust=False).mean().iloc[-1])

    # Volume Profile & POC
    df['Price_Bin'] = df['Close'].round(1)
    poc_level = float(df.groupby('Price_Bin')['Volume'].sum().idxmax())

    # Supply & Demand Zones
    demand_zone = float(df[df['Close'] < vwap_val]['Low'].min()) if not df[df['Close'] < vwap_val].empty else day_low
    supply_zone = float(df[df['Close'] > vwap_val]['High'].max()) if not df[df['Close'] > vwap_val].empty else day_high

    # Trend & Structure
    trend = "BULLISH 📈" if ema_20 > ema_50 else "BEARISH 📉"
    structure = "Breakout (BOS)" if len(df) >= 5 and latest_close > df['High'].iloc[-5:-1].max() else ("Breakdown (CHoCH)" if len(df) >= 5 and latest_close < df['Low'].iloc[-5:-1].min() else "Consolidation (Range)")

    # Order Flow Delta
    bullish_vol = df[df['Close'] >= df['Open']]['Volume'].sum()
    bearish_vol = df[df['Close'] < df['Open']]['Volume'].sum()
    order_flow = "Buying Delta 🟢" if bullish_vol > bearish_vol else "Selling Delta 🔴"

    # Bias Signal
    if latest_close > vwap_val and ema_20 > ema_50:
        bias = "STRONG BUY 🟢"
    elif latest_close < vwap_val and ema_20 < ema_50:
        bias = "STRONG SELL 🔴"
    else:
        bias = "NEUTRAL / HOLD 🟡"

    return {
        "latest_close": round(latest_close, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "poc": round(poc_level, 2),
        "vwap": round(vwap_val, 2),
        "ema_20": round(ema_20, 2),
        "ema_50": round(ema_50, 2),
        "supply_zone": round(supply_zone, 2),
        "demand_zone": round(demand_zone, 2),
        "trend": trend,
        "structure": structure,
        "order_flow": order_flow,
        "bias": bias
    }

def generate_audio(text: str, lang: str = 'en'):
    try:
        tts = gtts.gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64_audio = base64.b64encode(fp.read()).decode()
        return f'<audio autoplay controls src="data:audio/mp3;base64,{b64_audio}"></audio>'
    except Exception:
        return ""

# --- NAVIGATION TABS ---
tab_market, tab_dashboard, tab_journal = st.tabs(["📈 Market & Chart Analysis", "📊 Capital & Target Dashboard", "📓 Stock Journal"])

# ==========================================
# TAB 1: MARKET & CHART ANALYSIS
# ==========================================
with tab_market:
    st.title("🐱 Shadow AI Market & Chart Engine")
    st.caption("Enter Stock Name in Box 1. Add multiple analysis commands separated by semicolon (;) in Box 2.")

    # Voice Input
    spoken_text = speech_to_text(language='ml-IN', start_prompt="🎙️ Voice Input (English / മലയാളം)", stop_prompt="⏹️ Stop", key='voice_input')

    # BOX 1: Stock Name Input
    stock_query = st.text_input("1️⃣ Stock Name / Ticker (e.g. SUZLON, RELIANCE, TCS, ZOMATO):", key="stock_name")

    # BOX 2: Conditions Input (Unlocked when Box 1 is filled)
    condition_input = ""
    if stock_query or spoken_text:
        condition_input = st.text_input(
            "2️⃣ Conditions / Technical Commands (Separate multiple conditions with semicolon ';'):",
            placeholder="e.g. 1day high; supply zone; demand zone; poc; vwap; news",
            key="conditions_input"
        )
    else:
        st.info("👈 Enter a Stock Name in Box 1 to unlock condition search.")

    target_stock = spoken_text if spoken_text else stock_query

    if target_stock:
        target_symbol = resolve_indian_stock_ticker(target_stock)

        # Timeframe & Interval Selection
        st.markdown("---")
        col_tf1, col_tf2 = st.columns(2)

        with col_tf1:
            timeframe = st.selectbox(
                "📅 Chart Time Horizon:",
                options=["1 Day (1D)", "5 Days (5D)", "1 Month (1M)", "6 Months (6M)", "1 Year (1Y)"],
                index=0
            )

        tf_map = {
            "1 Day (1D)": ("1d", "5m"),
            "5 Days (5D)": ("5d", "15m"),
            "1 Month (1M)": ("1mo", "1h"),
            "6 Months (6M)": ("6mo", "1d"),
            "1 Year (1Y)": ("1y", "1d")
        }
        
        default_period, default_interval = tf_map[timeframe]

        with col_tf2:
            if default_period == "1d":
                valid_intervals = ["1m", "2m", "5m", "15m", "30m", "1h"]
            elif default_period == "5d":
                valid_intervals = ["5m", "15m", "30m", "1h"]
            elif default_period == "1mo":
                valid_intervals = ["30m", "1h", "1d"]
            else:
                valid_intervals = ["1d", "1wk", "1mo"]

            interval = st.selectbox(
                "⏱️ Candle Interval:",
                options=valid_intervals,
                index=valid_intervals.index(default_interval) if default_interval in valid_intervals else 0
            )

        # Fetch Data & Analyze
        df = fetch_stock_data(target_symbol, period=default_period, interval=interval)
        metrics = analyze_smc_data(df)

        raw_conditions = [c.strip().lower() for c in condition_input.split(";") if c.strip()] if condition_input else []

        # Technical Flag Triggers
        mark_high = any("high" in c or "1day high" in c for c in raw_conditions)
        mark_low = any("low" in c or "1day low" in c for c in raw_conditions)
        mark_poc = any("poc" in c for c in raw_conditions)
        mark_vwap = any("vwap" in c for c in raw_conditions)
        mark_supply = any("supply" in c or "ob" in c for c in raw_conditions)
        mark_demand = any("demand" in c for c in raw_conditions)
        mark_ema = any("ema" in c or "sma" in c for c in raw_conditions)

        if not raw_conditions:
            mark_poc = True
            mark_high = True
            mark_low = True

        # AI Analysis Box
        if api_key and not df.empty:
            agent_prompt = f"""
            You are Shadow AI, an expert stock market analyst.
            Provide a concise analysis for {target_symbol}:
            - Current Price: ₹{metrics.get('latest_close')}
            - Bias: {metrics.get('bias')} | Trend: {metrics.get('trend')}
            - Supply Level: ₹{metrics.get('supply_zone')} | Demand Level: ₹{metrics.get('demand_zone')}
            - POC: ₹{metrics.get('poc')} | VWAP: ₹{metrics.get('vwap')}
            - Conditions Requested: {', '.join(raw_conditions) if raw_conditions else 'General Overview'}
            """
            response_text = None
            for m in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro']:
                try:
                    model = genai.GenerativeModel(m)
                    res = model.generate_content(agent_prompt)
                    if res and res.text:
                        response_text = res.text
                        break
                except Exception:
                    continue
            response_ml = response_text if response_text else f"Stock: {target_symbol} | Price: ₹{metrics.get('latest_close')} | Bias: {metrics.get('bias')}"
        else:
            response_ml = f"Stock: {target_symbol} | Price: ₹{metrics.get('latest_close', 'N/A')} | Bias: {metrics.get('bias', 'N/A')}"

        st.markdown(f'<div class="chat-box"><b>🤖 Shadow AI Auto-Analysis:</b><br>{response_ml}</div>', unsafe_allow_html=True)

        is_malayalam = any('\u0d00' <= char <= '\u0d7f' for char in response_ml)
        audio_html = generate_audio(response_ml, lang='ml' if is_malayalam else 'en')
        if audio_html:
            st.components.v1.html(audio_html, height=50)

        # Plot Interactive Chart
        if not df.empty:
            st.subheader(f"📈 {target_symbol} ({timeframe} View - {interval} Candles)")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.8])

            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"
            ), row=1, col=1)

            if mark_ema:
                df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='#ffb74d', width=1), name="20 EMA"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='#29b6f6', width=1), name="50 EMA"), row=1, col=1)

            if mark_high:
                fig.add_hline(y=metrics['day_high'], line_dash="dash", line_color="#00e676", annotation_text=f"High: ₹{metrics['day_high']}", row=1, col=1)

            if mark_low:
                fig.add_hline(y=metrics['day_low'], line_dash="dash", line_color="#ff5252", annotation_text=f"Low: ₹{metrics['day_low']}", row=1, col=1)

            if mark_supply:
                fig.add_hline(y=metrics['supply_zone'], line_color="#d50000", annotation_text=f"Supply: ₹{metrics['supply_zone']}", row=1, col=1)

            if mark_demand:
                fig.add_hline(y=metrics['demand_zone'], line_color="#00c853", annotation_text=f"Demand: ₹{metrics['demand_zone']}", row=1, col=1)

            if mark_vwap:
                fig.add_hline(y=metrics['vwap'], line_dash="dash", line_color="#ff4081", annotation_text=f"VWAP: ₹{metrics['vwap']}", row=1, col=1)

            if mark_poc:
                fig.add_hline(y=metrics['poc'], line_dash="dot", line_color="#ab47bc", annotation_text=f"POC: ₹{metrics['poc']}", row=1, col=1)

            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#2962ff'), row=2, col=1)
            fig.update_layout(template="plotly_dark", height=480, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # Columns Below Chart
            col_news, col_signal = st.columns([1, 1])

            with col_news:
                st.subheader(f"📰 Live News for {target_symbol}")
                news_items = fetch_stock_news(target_symbol)
                if news_items:
                    for item in news_items:
                        st.markdown(f'<div class="news-box"><b>{item["publisher"]}</b><br>{item["title"]}</div>', unsafe_allow_html=True)
                else:
                    st.info("No recent news updates found.")

            with col_signal:
                st.subheader("🎯 Buy/Sell Signal & Breakdown")
                st.markdown(f"""
                <div class="bias-card">
                    <h3>Signal: {metrics.get('bias')}</h3>
                    <p><b>Market Trend:</b> {metrics.get('trend')}</p>
                    <p><b>Market Structure:</b> {metrics.get('structure')}</p>
                    <p><b>Order Flow Delta:</b> {metrics.get('order_flow')}</p>
                    <hr>
                    <p><b>Target (Supply):</b> ₹{metrics.get('supply_zone')}</p>
                    <p><b>Stop Loss (Demand):</b> ₹{metrics.get('demand_zone')}</p>
                    <p><b>Key Volume Control (POC):</b> ₹{metrics.get('poc')}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error(f"Unable to load market data for '{target_symbol}'. Check ticker name.")

# ==========================================
# TAB 2: CAPITAL & TARGET DASHBOARD
# ==========================================
with tab_dashboard:
    st.title("📊 Capital & Financial Target Dashboard")

    col_cap1, col_cap2 = st.columns(2)
    with col_cap1:
        st.session_state.initial_capital = st.number_input("Starting Capital (₹):", value=st.session_state.initial_capital, step=5000.0)
    with col_cap2:
        st.session_state.target_capital = st.number_input("Target Goal Capital (₹):", value=st.session_state.target_capital, step=10000.0)

    st.subheader("➕ Update Daily Profit / Loss")
    c_date, c_pnl, c_btn = st.columns([2, 2, 1])
    update_date = c_date.date_input("Date:", key="pnl_date")
    daily_pnl = c_pnl.number_input("Profit / Loss Amount (₹):", value=0.0, step=500.0, key="pnl_val")

    if c_btn.button("Update Capital Balance"):
        current_total = st.session_state.initial_capital + st.session_state.daily_updates["Daily P&L"].sum() + daily_pnl
        new_row = pd.DataFrame([{"Date": str(update_date), "Daily P&L": daily_pnl, "Total Capital": current_total}])
        st.session_state.daily_updates = pd.concat([st.session_state.daily_updates, new_row], ignore_index=True)
        st.success("Capital updated successfully!")

    # Dynamic Capital Calculations
    total_pnl = st.session_state.daily_updates["Daily P&L"].sum() if not st.session_state.daily_updates.empty else 0.0
    current_balance = st.session_state.initial_capital + total_pnl
    growth_pct = ((current_balance - st.session_state.initial_capital) / st.session_state.initial_capital) * 100
    
    distance_to_target = st.session_state.target_capital - current_balance
    target_pct_remaining = (distance_to_target / st.session_state.target_capital) * 100 if st.session_state.target_capital > 0 else 0

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Balance", f"₹{current_balance:,.2f}")
    m2.metric("Total Capital Growth", f"{growth_pct:+.2f}%", f"₹{total_pnl:,.2f}")
    m3.metric("Target Goal", f"₹{st.session_state.target_capital:,.2f}")
    m4.metric("Distance to Target", f"₹{distance_to_target:,.2f}", f"{target_pct_remaining:.1f}% remaining")

    st.progress(min(max(current_balance / st.session_state.target_capital, 0.0), 1.0))

    if not st.session_state.daily_updates.empty:
        st.subheader("📈 Capital Growth Progress Curve")
        st.line_chart(st.session_state.daily_updates.set_index("Date")["Total Capital"])

# ==========================================
# TAB 3: STOCK JOURNAL & DYNAMIC R:R ASSISTANT
# ==========================================
with tab_journal:
    st.title("📓 Trade Journal & Dynamic AI Risk:Reward Calculator")

    col_j1, col_j2 = st.columns([2, 1])

    with col_j1:
        st.subheader("📝 Log Executed Trade")
        with st.form("trade_form"):
            tf_stock = st.text_input("Stock Ticker (e.g. SUZLON)")
            tf_type = st.selectbox("Type", ["BUY", "SELL"])
            tf_entry = st.number_input("Entry Price (₹)", min_value=0.1, step=1.0)
            tf_exit = st.number_input("Target / Exit Price (₹)", min_value=0.1, step=1.0)
            tf_sl = st.number_input("Stop Loss Price (₹)", min_value=0.1, step=1.0)
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
        st.subheader("🤖 Dynamic AI Risk:Reward Calculator")
        calc_entry = st.number_input("Entry Price (₹)", value=100.0, key="c_entry")
        calc_sl = st.number_input("Stop Loss (₹)", value=95.0, key="c_sl")
        calc_target = st.number_input("Target Price (₹)", value=115.0, key="c_tgt")
        max_risk_amount = st.number_input("Max Risk Allowed (₹)", value=2000.0, key="c_risk")

        risk_per_share = abs(calc_entry - calc_sl)
        reward_per_share = abs(calc_target - calc_entry)
        
        if risk_per_share > 0:
            rr = reward_per_share / risk_per_share
            suggested_qty = int(max_risk_amount / risk_per_share)
            st.markdown(f"### R:R Ratio: **1 : {rr:.2f}**")
            st.info(f"💡 **Suggested Position Size:** {suggested_qty} shares (Max Risk: ₹{max_risk_amount})")
            
            if rr < 1.5:
                st.warning("⚠️ Poor Risk:Reward ratio (< 1.5). Adjust entry or target for better expectancy.")
            else:
                st.success("✅ Excellent Trade Setup with high expectancy.")
        else:
            st.error("Stop Loss cannot equal Entry Price.")

    st.markdown("---")
    st.subheader("📋 Trade History Logs")
    if not st.session_state.journal_logs.empty:
        st.dataframe(st.session_state.journal_logs, use_container_width=True)
    else:
        st.info("No trade logs recorded yet.")
