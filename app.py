import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(page_title="Shadow AI Agent", layout="wide")

# --- Helper Technical Indicators ---
def calculate_vwap(df):
    """Calculates Volume Weighted Average Price (VWAP)."""
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    tp_v = typical_price * df['Volume']
    cum_tp_v = tp_v.cumsum()
    cum_v = df['Volume'].cumsum()
    return cum_tp_v / cum_v

def calculate_rsi(df, period=14):
    """Calculates Relative Strength Index (RSI)."""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

# --- Data Fetching & Enrichment ---
@st.cache_data(ttl=15)
def fetch_stock_data(symbol, timeframe="5m"):
    period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "3mo"}
    period = period_map.get(timeframe, "5d")
    try:
        df = yf.download(tickers=symbol, period=period, interval=timeframe, progress=False)
        if df.empty:
            return pd.DataFrame()
            
        # Flatten MultiIndex columns if present (yfinance v0.2.x+ compatibility)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.dropna()
        return df
    except Exception:
        return pd.DataFrame()

def enrich_stock_signals(df):
    if df.empty or len(df) < 3:
        return df

    df = df.copy()
    df['VWAP'] = calculate_vwap(df)
    df['RSI'] = calculate_rsi(df)

    np.random.seed(42)
    # Generate mock Delta & Order volume flow safely
    random_factors = np.random.uniform(0.55, 0.85, len(df))
    df['Delta'] = np.where(
        df['Close'] >= df['Open'], 
        df['Volume'] * random_factors, 
        -df['Volume'] * random_factors
    )

    df['Buy_Orders'] = np.where(
        df['Delta'] > 0, 
        (df['Volume'] + df['Delta']) / 2, 
        (df['Volume'] - np.abs(df['Delta'])) / 2
    ).astype(int)
    df['Sell_Orders'] = (df['Volume'] - df['Buy_Orders']).astype(int)

    # Initialize Signal columns safely
    signals = ["HOLD"] * len(df)
    signal_prices = [np.nan] * len(df)

    # Convert columns to NumPy arrays to prevent type/indexing errors
    close_vals = df['Close'].values
    vwap_vals = df['VWAP'].values
    rsi_vals = df['RSI'].values
    delta_vals = df['Delta'].values
    low_vals = df['Low'].values
    high_vals = df['High'].values

    for i in range(2, len(df)):
        # Buy Signal Condition
        if (close_vals[i] > vwap_vals[i] and rsi_vals[i] > 45 and rsi_vals[i-1] <= 45 and delta_vals[i] > 0):
            signals[i] = "BUY"
            signal_prices[i] = low_vals[i] * 0.999
        # Sell Signal Condition
        elif (close_vals[i] < vwap_vals[i] and rsi_vals[i] < 55 and rsi_vals[i-1] >= 55 and delta_vals[i] < 0):
            signals[i] = "SELL"
            signal_prices[i] = high_vals[i] * 1.001

    df['Signal'] = signals
    df['Signal_Price'] = signal_prices
    return df

# --- Streamlit Dashboard UI ---
st.title("⚡ Shadow AI Trading Agent")

sidebar_symbol = st.sidebar.text_input("Stock Symbol (NSE/Yahoo)", value="RELIANCE.NS")
timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=1)

if sidebar_symbol:
    data = fetch_stock_data(sidebar_symbol, timeframe=timeframe)
    
    if not data.empty:
        data_enriched = enrich_stock_signals(data)
        
        # Display latest signal summary
        latest_row = data_enriched.iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"₹{latest_row['Close']:.2f}")
        col2.metric("VWAP", f"₹{latest_row['VWAP']:.2f}")
        col3.metric("RSI", f"{latest_row['RSI']:.2f}")
        col4.metric("Signal", latest_row['Signal'])
        
        st.subheader("Market Data & Technical Signals")
        st.dataframe(data_enriched.tail(20), use_container_width=True)
    else:
        st.warning(f"No data retrieved for symbol `{sidebar_symbol}`. Please check the ticker symbol.")
