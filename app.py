@st.cache_data(ttl=15)
def fetch_stock_data(symbol, timeframe="5m"):
    period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "3mo"}
    period = period_map.get(timeframe, "5d")
    try:
        df = yf.download(tickers=symbol, period=period, interval=timeframe, progress=False)
        if df.empty:
            return pd.DataFrame()
            
        # Flatten MultiIndex columns if present
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
    df['Delta'] = np.where(df['Close'] >= df['Open'], df['Volume'] * random_factors, -df['Volume'] * random_factors)
    
    df['Buy_Orders'] = np.where(df['Delta'] > 0, (df['Volume'] + df['Delta']) / 2, (df['Volume'] - np.abs(df['Delta'])) / 2).astype(int)
    df['Sell_Orders'] = (df['Volume'] - df['Buy_Orders']).astype(int)

    # Initialize Signal columns safely
    signals = ["HOLD"] * len(df)
    signal_prices = [np.nan] * len(df)

    # Iterate through row indices safely
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
