import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import sqlite3
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK THEME
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Shadow AI Trading Agent 🐱",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    .metric-value { font-size: 24px; font-weight: bold; color: #00e676; }
    .metric-label { font-size: 14px; color: #b2b5be; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# 2. PERSISTENT DATABASE ENGINE (SQLite)
# -------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("shadow_trading.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_state (
            id INTEGER PRIMARY KEY,
            capital REAL,
            target REAL,
            initial_capital REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            action TEXT,
            price REAL,
            quantity REAL,
            pnl REAL
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM account_state")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO account_state (id, capital, target, initial_capital) VALUES (1, 1222.0, 100000.0, 1222.0)")
    conn.commit()
    conn.close()

def get_state():
    conn = sqlite3.connect("shadow_trading.db")
    cursor = conn.cursor()
    cursor.execute("SELECT capital, target, initial_capital FROM account_state WHERE id = 1")
    capital, target, initial_capital = cursor.fetchone()
    conn.close()
    return capital, target, initial_capital

def update_capital(new_capital):
    conn = sqlite3.connect("shadow_trading.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE account_state SET capital = ? WHERE id = 1", (new_capital,))
    conn.commit()
    conn.close()

def log_trade(symbol, action, price, quantity, pnl):
    conn = sqlite3.connect("shadow_trading.db")
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO trade_history (timestamp, symbol, action, price, quantity, pnl)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, symbol, action, price, quantity, pnl))
    conn.commit()
    conn.close()

def get_trade_logs():
    conn = sqlite3.connect("shadow_trading.db")
    df = pd.read_sql_query("SELECT * FROM trade_history ORDER BY id DESC", conn)
    conn.close()
    return df

# Initialize DB state
init_db()

# -------------------------------------------------------------------
# 3. HEADER & CORE DASHBOARD METRICS
# -------------------------------------------------------------------
capital, target, initial_capital = get_state()
total_profit = capital - initial_capital
progress = min(max((capital - initial_capital) / (target - initial_capital), 0.0), 1.0)

st.title("Shadow AI Trading Agent 🐱 (1x Spot / No Leverage)")

st.markdown('<div class="status-card">', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="metric-label">Current Capital</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">₹{capital:,.2f}</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="metric-label">Target Capital</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">₹{target:,.2f}</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="metric-label">Total Realized Profit</div>', unsafe_allow_html=True)
    pnl_color = "#00e676" if total_profit >= 0 else "#ff5252"
    st.markdown(f'<div class="metric-value" style="color:{pnl_color}">₹{total_profit:,.2f}</div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="metric-label">Progress to Target</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">{progress * 100:.2f}%</div>', unsafe_allow_html=True)

st.progress(progress)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# 4. MARKET DATA & PAPER TRADING EXECUTION
# -------------------------------------------------------------------
symbol = st.selectbox("Select Asset for Trading", ["RELIANCE.NS", "TCS.NS", "INFY.NS", "BTC-USD"], index=0)

data = yf.download(symbol, period="1d", interval="1m")

if not data.empty:
    latest_price = float(data['Close'].iloc[-1].item())
    
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader(f"Live Price Chart - {symbol}")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'],
            low=data['Low'], close=data['Close'],
            name=symbol
        ))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
    with col_right:
        st.subheader("Paper Trade Controls")
        st.write(f"**Current Price:** ₹{latest_price:,.2f}")
        
        trade_amount = st.number_input("Capital Allocation (₹)", min_value=100.0, max_value=float(capital), value=float(capital))
        
        col_buy, col_sell = st.columns(2)
        
        # Spot buy simulation (1x leverage)
        if col_buy.button("Simulate Buy (1x Spot)", use_container_width=True):
            qty = trade_amount / latest_price
            log_trade(symbol, "BUY", latest_price, qty, 0.0)
            st.success(f"Bought {qty:.4f} units of {symbol} at ₹{latest_price:,.2f}")
            
        # Profit / Loss Realization Simulation
        if col_sell.button("Simulate Take Profit (+2%)", use_container_width=True):
            pnl = trade_amount * 0.02
            new_balance = capital + pnl
            update_capital(new_balance)
            qty = trade_amount / latest_price
            log_trade(symbol, "SELL (TP)", latest_price * 1.02, qty, pnl)
            st.success(f"Profit of ₹{pnl:.2f} saved to system!")
            st.rerun()

# -------------------------------------------------------------------
# 5. SAVED TRADE RECORDS & AUDIT LOGS
# -------------------------------------------------------------------
st.subheader("Persistent Trade History Log")
trade_df = get_trade_logs()

if not trade_df.empty:
    st.dataframe(trade_df, use_container_width=True)
else:
    st.info("No recorded trades yet. Executed paper trades will be stored here automatically across restarts.")
