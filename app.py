import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import gtts
import base64
import io

# Page Configuration & Dark Theme
st.set_page_config(page_title="Shadow AI Agent", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .chat-box { background-color: #1e222d; padding: 15px; border-radius: 10px; border-left: 5px solid #2962ff; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# Data Fetching
@st.cache_data(ttl=60) # Live update every 60 seconds
def fetch_stock_data(symbol: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        return ticker.history(period="5d", interval="15m")
    except Exception:
        return pd.DataFrame()

def analyze_market_data(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    latest_close = float(df['Close'].iloc[-1])
    support = float(df['Low'].min())
    resistance = float(df['High'].max())
    
    df['Price_Bin'] = df['Close'].round(1)
    poc_level = float(df.groupby('Price_Bin')['Volume'].sum().idxmax())
    sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])

    if latest_close > poc_level and latest_close > sma_20:
        action = "BUY (വാങ്ങുക)"
        reason_ml = f"വില POC ലെവലിനും (₹{poc_level:.2f}) 20 SMA യ്ക്കും മുകളിലാണ്. ബുള്ളിഷ് മൊമെന്റം നിലനിൽക്കുന്നു."
    elif latest_close < poc_level and latest_close < sma_20:
        action = "SELL (വിൽക്കുക)"
        reason_ml = f"വില POC ലെവലിനും (₹{poc_level:.2f}) 20 SMA യ്ക്കും താഴെയാണ്. ബെയറിഷ് പ്രഷർ നിലനിൽക്കുന്നു."
    else:
        action = "HOLD / NEUTRAL (കാത്തിരിക്കുക)"
        reason_ml = f"വില സപ്പോർട്ടിനും (₹{support:.2f}) റെസിസ്റ്റൻസിനും (₹{resistance:.2f}) ഇടയിൽ റേഞ്ച് ബോണ്ടിലാണ്."

    return {
        "latest_close": round(latest_close, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "poc": round(poc_level, 2),
        "action": action,
        "reason_ml": reason_ml
    }

def generate_malayalam_audio(text: str):
    tts = gtts.gTTS(text=text, lang='ml')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    audio_bytes = fp.read()
    b64_audio = base64.b64encode(audio_bytes).decode()
    return f'<audio autoplay controls src="data:audio/mp3;base64,{b64_audio}"></audio>'

# UI Header
st.title("🤖 SHADOW AI AGENT (24/7 Live Malayalam Voice Chat)")

# Sidebar Ticker Select
watchlist = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS", "SBIN.NS"]
selected_stock = st.sidebar.selectbox("Select Indian Stock:", watchlist)

df = fetch_stock_data(selected_stock)
metrics = analyze_market_data(df)

if not df.empty and metrics:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Price", f"₹{metrics['latest_close']}")
    col2.metric("Support", f"₹{metrics['support']}")
    col3.metric("Resistance", f"₹{metrics['resistance']}")
    col4.metric("POC Level", f"₹{metrics['poc']}")

    # Chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.8])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_hline(y=metrics['resistance'], line_dash="dash", line_color="#ff5252", row=1, col=1)
    fig.add_hline(y=metrics['support'], line_dash="dash", line_color="#00e676", row=1, col=1)
    fig.add_hline(y=metrics['poc'], line_dash="dot", line_color="#ab47bc", row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#2962ff'), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Voice Chat Section
    st.markdown("---")
    st.subheader("💬 Ask Shadow AI (മലയാളത്തിൽ ചോദിക്കാം)")
    user_query = st.text_input("നിങ്ങളുടെ ചോദ്യം ഇവിടെ ടൈപ്പ് ചെയ്യുക:", placeholder="e.g. വാങ്ങണോ വിൽക്കണോ?, POC ലെവൽ എത്രയാണ്?")

    if user_query:
        query_lower = user_query.lower()
        if "poc" in query_lower or "പി ഒ സി" in query_lower:
            response_ml = f"{selected_stock} ന്റെ പോയിന്റ് ഓഫ് കൺട്രോൾ (POC) ലെവൽ ₹{metrics['poc']} ആണ്."
        elif "buy" in query_lower or "sell" in query_lower or "വാങ്ങണോ" in query_lower or "വിൽക്കണോ" in query_lower:
            response_ml = f"{selected_stock} ലെ തീരുമാനം: {metrics['action']}. കാരണം: {metrics['reason_ml']}"
        else:
            response_ml = f"{selected_stock} ലെ വില ₹{metrics['latest_close']} ആണ്. സപ്പോർട്ട്: ₹{metrics['support']}, റെസിസ്റ്റൻസ്: ₹{metrics['resistance']}."

        st.markdown(f'<div class="chat-box"><b>🤖 ഷാഡോ:</b><p>{response_ml}</p></div>', unsafe_allow_html=True)
        try:
            st.components.v1.html(generate_malayalam_audio(response_ml), height=60)
        except Exception:
            pass
