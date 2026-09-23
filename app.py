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

# Page Configuration & Dark Theme (Sidebar Hidden)
st.set_page_config(
    page_title="Shadow AI Agent", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling
st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #0e1117; color: #ffffff; }
    .chat-box { background-color: #1e222d; padding: 18px; border-radius: 12px; border-left: 5px solid #2962ff; margin-bottom: 15px; font-size: 16px; }
    .news-box { background-color: #1a1d24; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #2d313e; }
</style>
""", unsafe_allow_html=True)

# 1. Initialize Gemini API Key
api_key = st.secrets.get("GEMINI_API_KEY", None)
if api_key:
    genai.configure(api_key=api_key)

# Dynamic Stock Symbol Resolver for ALL NSE/BSE Stocks
def resolve_indian_stock_ticker(query: str) -> str:
    """Dynamically converts any Indian stock name or symbol into an NSE/BSE ticker."""
    query_clean = query.upper().strip()
    
    # Common mappings for aliases / popular indices
    alias_map = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
        "RELIANCE": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "INFY": "INFY.NS",
        "INFOSYS": "INFY.NS",
        "HDFC": "HDFCBANK.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "ICICI": "ICICIBANK.NS",
        "SBI": "SBIN.NS",
        "SBIN": "SBIN.NS",
        "TATA MOTORS": "TATAMOTORS.NS",
        "TATAMOTORS": "TATAMOTORS.NS"
    }
    
    for key, ticker in alias_map.items():
        if key in query_clean:
            return ticker

    # Stopwords to clean out of user prompts
    ignore_words = {
        "CHART", "SHOW", "MARK", "LEVEL", "STOCK", "NEWS", "OPEN", "POC", 
        "SUPPORT", "RESISTANCE", "SMA", "GRAPH", "PLOT", "PRICE", "FOR", 
        "OF", "THE", "AND", "IN", "ME", "PLEASE", "WHAT", "IS"
    }
    
    words = [w for w in re.findall(r'\b[A-Z0-9&]+\b', query_clean) if w not in ignore_words]
    
    if not words:
        return "RELIANCE.NS"

    # Try extracted target as NSE symbol first, then BSE symbol
    candidate = words[0]
    if candidate.endswith(".NS") or candidate.endswith(".BO") or candidate.startswith("^"):
        return candidate

    # Test candidate on NSE
    nse_symbol = f"{candidate}.NS"
    try:
        data = yf.Ticker(nse_symbol).history(period="1d")
        if not data.empty:
            return nse_symbol
    except Exception:
        pass

    # Fallback to BSE if NSE fails
    bse_symbol = f"{candidate}.BO"
    try:
        data = yf.Ticker(bse_symbol).history(period="1d")
        if not data.empty:
            return bse_symbol
    except Exception:
        pass

    return nse_symbol

# Helper Data Functions
@st.cache_data(ttl=60)
def fetch_stock_data(symbol: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="15m")
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def fetch_stock_news(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news
        cleaned_news = []
        if raw_news:
            for item in raw_news[:3]:
                title = item.get('title') or item.get('content', {}).get('title', 'Market News Update')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', 'Finance News')
                cleaned_news.append({"title": title, "publisher": publisher})
        return cleaned_news
    except Exception:
        return []

def analyze_market_data(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    latest_close = float(df['Close'].iloc[-1])
    support = float(df['Low'].min())
    resistance = float(df['High'].max())
    df['Price_Bin'] = df['Close'].round(1)
    poc_level = float(df.groupby('Price_Bin')['Volume'].sum().idxmax())
    sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1]) if len(df) >= 20 else latest_close
    return {
        "latest_close": round(latest_close, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "poc": round(poc_level, 2),
        "sma_20": round(sma_20, 2)
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

# --- MAIN CHAT INTERFACE ---
st.title("🤖 SHADOW AI AGENT")
st.caption("Ask anything about ANY NSE/BSE listed stock (e.g. Zomato, Suzlon, JioFin, Tata Power), charts, POC levels, or news.")

# Voice & Text Inputs
col_input1, col_input2 = st.columns([1, 4])
with col_input1:
    spoken_text = speech_to_text(language='ml-IN', start_prompt="🎙️ Speak / സംസാരിക്കാം", stop_prompt="⏹️ Stop", key='voice_input')

with col_input2:
    typed_text = st.text_input("Type stock question here (English / മലയാളം):", key="text_query")

user_query = spoken_text if spoken_text else typed_text

# Process Query
if user_query:
    st.markdown(f"**Your Query:** *{user_query}*")
    
    query_lower = user_query.lower()
    target_symbol = resolve_indian_stock_ticker(user_query)
    
    # Intent Detection
    show_chart_intent = any(w in query_lower for w in ["chart", "show chart", "open chart", "graph", "plot", "poc", "level", "mark", "support", "resistance", "sma"])
    show_news_intent = any(w in query_lower for w in ["news", "update", "latest", "വാർത്ത"])

    # Specific Markers requested
    mark_poc = "poc" in query_lower
    mark_support = "support" in query_lower
    mark_resistance = "resistance" in query_lower
    mark_sma = "sma" in query_lower or "average" in query_lower

    # Default to POC line when a chart is requested
    if show_chart_intent and not (mark_poc or mark_support or mark_resistance or mark_sma):
        mark_poc = True

    # Fetch Data
    df = fetch_stock_data(target_symbol)
    metrics = analyze_market_data(df)
    news_list = fetch_stock_news(target_symbol) if show_news_intent else []

    # 1. Dynamic Conversational AI Agent
    if api_key:
        agent_prompt = f"""
        You are Shadow AI, an expert real-time stock market assistant for Indian listed stocks on NSE and BSE.

        STOCK MARKET DATA FOR {target_symbol}:
        - Latest Price: ₹{metrics.get('latest_close', 'N/A')}
        - Point of Control (POC) Volume Level: ₹{metrics.get('poc', 'N/A')}
        - Support Level: ₹{metrics.get('support', 'N/A')}
        - Resistance Level: ₹{metrics.get('resistance', 'N/A')}
        - 20 Simple Moving Average (SMA): ₹{metrics.get('sma_20', 'N/A')}

        USER QUERY: "{user_query}"

        INSTRUCTIONS:
        1. If the user asked in Malayalam or used Malayalam words, reply in clear Malayalam. Otherwise, answer in English.
        2. Give precise market analysis for {target_symbol}.
        """

        try:
            models_to_try = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
            response_text = None
            for m in models_to_try:
                try:
                    model = genai.GenerativeModel(m)
                    res = model.generate_content(agent_prompt)
                    if res and res.text:
                        response_text = res.text
                        break
                except Exception:
                    continue
            response_ml = response_text if response_text else "Unable to fetch AI response."
        except Exception as e:
            response_ml = f"AI Error: {str(e)}"
    else:
        response_ml = "Please set a valid Gemini API Key."

    # Render AI Answer
    st.markdown(f'<div class="chat-box"><b>🤖 Shadow AI:</b><p>{response_ml}</p></div>', unsafe_allow_html=True)

    # Audio Voice Output
    is_malayalam = any('\u0d00' <= char <= '\u0d7f' for char in response_ml)
    audio_html = generate_audio(response_ml, lang='ml' if is_malayalam else 'en')
    if audio_html:
        st.components.v1.html(audio_html, height=50)

    # 2. Show News if requested
    if show_news_intent and news_list:
        st.subheader(f"📰 Live News for {target_symbol}")
        for article in news_list:
            st.markdown(f'<div class="news-box"><b>{article["publisher"]}:</b> {article["title"]}</div>', unsafe_allow_html=True)

    # 3. Automatically Open Chart and Mark Requested Levels
    if show_chart_intent and not df.empty:
        st.subheader(f"📈 {target_symbol} Chart")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.8])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)

        if mark_poc:
            fig.add_hline(
                y=metrics['poc'], line_dash="dot", line_color="#ab47bc", line_width=2,
                annotation_text=f"POC: ₹{metrics['poc']}", annotation_position="bottom right", row=1, col=1
            )
        if mark_support:
            fig.add_hline(
                y=metrics['support'], line_dash="dash", line_color="#00e676", line_width=2,
                annotation_text=f"Support: ₹{metrics['support']}", annotation_position="bottom left", row=1, col=1
            )
        if mark_resistance:
            fig.add_hline(
                y=metrics['resistance'], line_dash="dash", line_color="#ff5252", line_width=2,
                annotation_text=f"Resistance: ₹{metrics['resistance']}", annotation_position="top right", row=1, col=1
            )
        if mark_sma:
            fig.add_hline(
                y=metrics['sma_20'], line_dash="dashdot", line_color="#ffb74d", line_width=2,
                annotation_text=f"20 SMA: ₹{metrics['sma_20']}", annotation_position="top left", row=1, col=1
            )

        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#2962ff'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    elif show_chart_intent and df.empty:
        st.warning(f"Could not load chart for '{target_symbol}'. Please verify the stock symbol or ticker name.")
