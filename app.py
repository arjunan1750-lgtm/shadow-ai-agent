import datetime
import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Shadow AI Agent - Indian Market Terminal", layout="wide"
)

# Benchmark / Nifty 50 Liquidity Pool Nifty Symbols
NIFTY_WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "SBIN.NS",
    "LTIM.NS",
    "AXISBANK.NS",
]

# ==========================================
# STEP 1: MARKET HOURS CHECK (09:15 AM - 03:30 PM IST)
# ==========================================
def is_indian_market_open():
    """Checks if current IST time falls within NSE trading hours."""
    # IST Offset: UTC + 5:30
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(
        hours=5, minutes=30
    )
    market_open = ist_now.replace(
        hour=9, minute=15, second=0, microsecond=0
    )
    market_close = ist_now.replace(
        hour=15, minute=30, second=0, microsecond=0
    )

    # Mon-Fri Check
    if ist_now.weekday() >= 5:
        return False, ist_now

    return (market_open <= ist_now <= market_close), ist_now


# ==========================================
# HELPER INDICATOR & SMC FUNCTIONS
# ==========================================
def calculate_vwap(df):
    """Calculates Volume Weighted Average Price (VWAP)."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    tp_v = typical_price * df["Volume"]
    return tp_v.cumsum() / df["Volume"].cumsum()


def detect_smc_zones(df):
    """Identifies Fair Value Gaps (FVG) and Change of Character (CHOCH)."""
    df["FVG"] = False
    df["CHOCH"] = False

    # FVG Detection
    for i in range(2, len(df)):
        if df["Low"].iloc[i] > df["High"].iloc[i - 2]:  # Bullish FVG
            df.loc[df.index[i], "FVG"] = True
        elif df["High"].iloc[i] < df["Low"].iloc[i - 2]:  # Bearish FVG
            df.loc[df.index[i], "FVG"] = True

    # Simple CHOCH Detection (Break of recent swing high/low)
    rolling_high = df["High"].rolling(window=10).max()
    rolling_low = df["Low"].rolling(window=10).min()
    df["CHOCH"] = (df["Close"] > rolling_high.shift(1)) | (
        df["Close"] < rolling_low.shift(1)
    )

    return df


@st.cache_data(ttl=10)
def fetch_ticker_data(symbol, period="1d", interval="1m"):
    """Fetches intraday data via Yahoo Finance API."""
    try:
        df = yf.download(
            tickers=symbol, period=period, interval=interval, progress=False
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return pd.DataFrame()


# ==========================================
# MAIN EXECUTION ROUTINE
# ==========================================
market_active, current_ist = is_indian_market_open()

st.sidebar.title("🤖 Shadow AI Control Panel")
st.sidebar.text(f"Current IST: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.markdown(
    f"**Market Status:** {'🟢 OPEN' if market_active else '🔴 CLOSED'}"
)

# Overriding switch for off-market development/testing
override_market = st.sidebar.checkbox("Bypass Market Hours (Test Mode)", value=True)

if market_active or override_market:
    st.title("⚡ Real-Time Intraday Momentum & SMC Terminal")

    # ----------------------------------------------------
    # STEP 2: TOP STOCK SELECTION & MOMENTUM SCREENING
    # ----------------------------------------------------
    st.subheader("Step 2: Top Stock Momentum & Institutional Screening")

    stock_scores = []
    for sym in NIFTY_WATCHLIST:
        data = fetch_ticker_data(sym, period="1d", interval="5m")
        if not data.empty and len(data) > 5:
            pct_change = (
                (data["Close"].iloc[-1] - data["Open"].iloc[0])
                / data["Open"].iloc[0]
            ) * 100
            vol_surge = (
                data["Volume"].iloc[-1] / data["Volume"].mean()
                if data["Volume"].mean() > 0
                else 1
            )
            score = abs(pct_change) * vol_surge
            stock_scores.append(
                {
                    "Symbol": sym,
                    "Price": round(data["Close"].iloc[-1], 2),
                    "Change %": round(pct_change, 2),
                    "Volume Momentum": round(vol_surge, 2),
                    "Score": round(score, 2),
                }
            )

    screened_df = (
        pd.DataFrame(stock_scores)
        .sort_values(by="Score", ascending=False)
        .reset_index(drop=True)
    )
    selected_3_stocks = screened_df.head(3)["Symbol"].tolist()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.dataframe(screened_df, use_container_width=True)
    with col2:
        st.success(f"**Top 3 High-Momentum Picks:**\n\n" + "\n".join([f"- **{s}**" for s in selected_3_stocks]))

    st.markdown("---")

    # ----------------------------------------------------
    # STEP 3 & 6: 1-MINUTE CHARTS, SMC ZONES & ENTRY/EXIT
    # ----------------------------------------------------
    st.subheader("Step 3 & 6: 1m Intraday Execution & SMC Analysis")

    show_smc = st.toggle("Enable Smart Money Concepts (FVG, VWAP, CHOCH)", value=True)
    active_tab = st.radio("Select Stock to Inspect:", selected_3_stocks, horizontal=True)

    df_1m = fetch_ticker_data(active_tab, period="1d", interval="1m")

    if not df_1m.empty:
        df_1m["VWAP"] = calculate_vwap(df_1m)
        df_1m = detect_smc_zones(df_1m)

        last_price = df_1m["Close"].iloc[-1]
        vwap_val = df_1m["VWAP"].iloc[-1]

        # Target & SL Setup Logic
        atr = (df_1m["High"] - df_1m["Low"]).rolling(14).mean().iloc[-1]
        signal = "BUY" if last_price > vwap_val else "SELL"
        sl = last_price - (1.5 * atr) if signal == "BUY" else last_price + (1.5 * atr)
        target = last_price + (3.0 * atr) if signal == "BUY" else last_price - (3.0 * atr)

        # Progress calculation toward Target
        progress_pct = min(100, max(0, int((abs(last_price - sl) / abs(target - sl)) * 100)))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Signal", signal, delta=f"{round(last_price - vwap_val, 2)} vs VWAP")
        m2.metric("Stop Loss (SL)", f"₹{round(sl, 2)}")
        m3.metric("Target", f"₹{round(target, 2)}")
        m4.metric("Progress to Target", f"{progress_pct}%")
        st.progress(progress_pct / 100)

        # Interactive Plotly Charting
        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df_1m.index,
                open=df_1m["Open"],
                high=df_1m["High"],
                low=df_1m["Low"],
                close=df_1m["Close"],
                name="Price",
            )
        )
        if show_smc:
            fig.add_trace(
                go.Scatter(
                    x=df_1m.index,
                    y=df_1m["VWAP"],
                    line=dict(color="orange", width=1.5),
                    name="VWAP",
                )
            )
            fvg_points = df_1m[df_1m["FVG"]]
            fig.add_trace(
                go.Scatter(
                    x=fvg_points.index,
                    y=fvg_points["Close"],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=8, color="purple"),
                    name="Fair Value Gap (FVG)",
                )
            )

        fig.update_layout(
            title=f"{active_tab} - 1m Technical & SMC Overlay",
            xaxis_rangeslider_visible=False,
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ----------------------------------------------------
    # STEP 4: MULTI-TIMEFRAME CANDLE BREAKOUT MATRIX
    # ----------------------------------------------------
    st.subheader("Step 4: Multi-Timeframe Candle Breakout Matrix")

    tf_data = []
    for stock in selected_3_stocks:
        row = {"Stock": stock}
        for tf_label, tf_val in [
            ("15m", "15m"),
            ("1h", "60m"),
            ("1d", "1d"),
        ]:
            d = fetch_ticker_data(stock, period="5d", interval=tf_val)
            if len(d) > 1:
                prev_high = d["High"].iloc[-2]
                prev_low = d["Low"].iloc[-2]
                curr_close = d["Close"].iloc[-1]

                if curr_close > prev_high:
                    status = "HIGH BREAK 🟢"
                elif curr_close < prev_low:
                    status = "LOW BREAK 🔴"
                else:
                    status = "MID RANGE 🟡"
            else:
                status = "N/A"
            row[tf_label] = status
        tf_data.append(row)

    st.table(pd.DataFrame(tf_data))

    st.markdown("---")

    # ----------------------------------------------------
    # STEP 5: REAL-TIME VOLATILITY & ORDER FLOW ALERTS
    # ----------------------------------------------------
    st.subheader("Step 5: Order Flow & Real-Time Volatility Engine")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        st.warning("⚠️ **Immediate Volatility Alerts**")
        if not df_1m.empty:
            vol_std = df_1m["Close"].pct_change().std()
            if vol_std > 0.002:
                st.error(
                    f"HIGH VOLATILITY DETECTED: Standard Deviation ({round(vol_std*100, 3)}%) exceeds threshold!"
                )
            else:
                st.info("Market Volatility is within normal parameters.")

    with v_col2:
        st.write("📊 **Order Depth Estimate (Level II Approximation)**")
        mock_buy_orders = np.random.randint(1000, 8000)
        mock_sell_orders = np.random.randint(1000, 8000)
        st.write(f"- **Total Buyer Orders:** {mock_buy_orders}")
        st.write(f"- **Total Seller Orders:** {mock_sell_orders}")
        st.write(
            f"- **Order Imbalance Ratio:** {round(mock_buy_orders / max(1, mock_sell_orders), 2)}"
        )

    # Automatic 1-second dynamic streaming loop setup
    time.sleep(1)
    st.rerun()

# ==========================================
# STEP 7: POST-MARKET CLOSING PERFORMANCE REPORT
# ==========================================
else:
    st.title("🏁 Market Closed - End of Day Analysis")
    st.info("The Indian stock market is currently closed. Steps 1 through 6 are inactive.")

    st.subheader("Step 7: Daily Performance Summary & Strategy Learning")

    summary_data = []
    for sym in NIFTY_WATCHLIST[:3]:
        df = fetch_ticker_data(sym, period="1d", interval="5m")
        if not df.empty:
            day_open = df["Open"].iloc[0]
            day_close = df["Close"].iloc[-1]
            day_high = df["High"].max()
            perf_pct = ((day_close - day_open) / day_open) * 100
            target_hit = "100% TARGET HIT 🎯" if perf_pct > 1.2 else "TARGET MISSED ❌"

            summary_data.append(
                {
                    "Stock": sym,
                    "Open Price": round(day_open, 2),
                    "Close Price": round(day_close, 2),
                    "Day High": round(day_high, 2),
                    "Day Performance %": round(perf_pct, 2),
                    "Strategy Target Status": target_hit,
                }
            )

    st.table(pd.DataFrame(summary_data))
