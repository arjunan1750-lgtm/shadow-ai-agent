import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import gtts
import base64
import io
import google.generativeai as genai
from streamlit_mic_recorder import speech_to_text

st.set_page_config(page_title="Shadow AI Agent", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .chat-box { background-color: #1e222d; padding: 15px; border-radius: 10px; border-left: 5px solid #2962ff; margin-bottom: 10px; }
    .news-box { background-color: #1a1d24; padding: 10px 15px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #2d313e; }
</style>
""", unsafe_allow_html=True)

# 1. Initialize Gemini API Key from Secrets or Sidebar
api_key = st.secrets.get("GEMINI_API_KEY", None)

if not api_key:
    api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)

# 2. Market Data Retrieval
@st.cache_data(ttl=60)
def fetch_stock_data(symbol: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        return ticker.history(period="5d", interval="15m")
    except Exception:
        return pd.DataFrame()

def fetch_stock_news(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.news[:3] if ticker.news else []
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
    sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])

    return {
        "latest_close": round(latest_close, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "poc": round(poc_level, 2),
        "sma_20": round(sma_20, 2)
    }

def generate_malayalam_audio(text: str):
    tts = gtts.gTTS(text=text, lang='ml')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    b64_audio = base64.b64encode(fp.read()).decode()
    return f'<audio autoplay controls src="data:audio/mp3;base64,{b64_audio}"></audio>'

# Main Dashboard
st.title("🤖 SHADOW AI AGENT (Autonomous Stock Analyst)")

watchlist = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS", "SBIN.NS"]
selected_stock = st.sidebar.selectbox("Select Indian Stock:", watchlist)

df = fetch_stock_data(selected_stock)
metrics = analyze_market_data(df)
news_list = fetch_stock_news(selected_stock)

if not df.empty and metrics:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Price", f"₹{metrics['latest_close']}")
    col2.metric("Support", f"₹{metrics['support']}")
    col3.metric("Resistance", f"₹{metrics['resistance']}")
    col4.metric("POC Level", f"₹{metrics['poc']}")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_width=[0.2, 0.8])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_hline(y=metrics['resistance'], line_dash="dash", line_color="#ff5252", row=1, col=1)
    fig.add_hline(y=metrics['support'], line_dash="dash", line_color="#00e676", row=1, col=1)
    fig.add_hline(y=metrics['poc'], line_dash="dot", line_color="#ab47bc", row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#2962ff'), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # Market News
    st.subheader("📰 Live Market News")
    if news_list:
        for article in news_list:
            title = article.get('title', 'News Update')
            publisher = article.get('publisher', 'Market News')
            st.markdown(f'<div class="news-box"><b>{publisher}:</b> {title}</div>', unsafe_allow_html=True)

    # Voice Input & Dynamic Reasoning Engine
    st.markdown("---")
    st.subheader("🎙️ Dynamic Voice Chat with Shadow AI")
    spoken_text = speech_to_text(language='ml-IN', start_prompt="🎙️ Click & Speak (ചോദിക്കാം)", stop_prompt="⏹️ Stop", key='voice_input')
    user_query = spoken_text if spoken_text else st.text_input("അല്ലെങ്കിൽ നിങ്ങളുടെ ചോദ്യം ഇവിടെ ടൈപ്പ് ചെയ്യുക:")

    if user_query:
        st.info(f"**ചോദ്യം:** {user_query}")

        if api_key:
            news_titles = [n.get('title', '') for n in news_list]
            news_context = ". ".join(news_titles) if news_titles else "No specific news updates today."

            agent_prompt = f"""
            You are Shadow AI, a professional real-time stock market research agent.
            
            REAL-TIME DATA CONTEXT FOR {selected_stock}:
            - Current Price: ₹{metrics['latest_close']}
            - Key Support Level: ₹{metrics['support']}
            - Key Resistance Level: ₹{metrics['resistance']}
            - Point of Control (POC Volume Level): ₹{metrics['poc']}
            - 20 SMA Trendline: ₹{metrics['sma_20']}
            - Live Market News: {news_context}

            USER QUERY: "{user_query}"

            INSTRUCTIONS:
            1. Act as a real financial analyst agent.
            2. Answer the user's query dynamically using the live context provided above.
            3. Respond in natural, conversational Malayalam language.
            4. Keep the explanation clear, actionable, and accurate to the data.
            """

            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(agent_prompt)
                response_ml = response.text
            except Exception as e:
                response_ml = f"AI Error: {str(e)}"
        else:
            response_ml = "ദയവായി ഒരു Gemini API Key ക്രമീകരിക്കുക."

        st.markdown(f'<div class="chat-box"><b>🤖 ഷാഡോ:</b><p>{response_ml}</p></div>', unsafe_allow_html=True)
        try:
            st.components.v1.html(generate_malayalam_audio(response_ml), height=60)
        except Exception:
            pass
