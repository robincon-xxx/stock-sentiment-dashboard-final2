import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Stock Sentiment Dashboard", layout="wide")
st.title("📊 Stock Sentiment Dashboard: BTC & ETF")

start_date_raw = datetime.today() - timedelta(days=180)
today = datetime.today()
start_date = min(start_date_raw, today).strftime('%Y-%m-%d')

# ------------------ API Keys ------------------
import os
twelvedata_api_key = os.gentev ("TWELVEDATA_API_KEY")
fred_api_key = os.gentev ("FRED_API_KEY")


# ------------------ API Calls ------------------

@st.cache_data(ttl=43200)
def get_bitcoin_data():
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {"vs_currency": "eur", "days": "180"}
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('Date', inplace=True)
        return df[['price']]
    except Exception as e:
        st.warning(f"⚠️ Failed to load Bitcoin data: {e}")
        return pd.DataFrame(columns=['price'])

@st.cache_data(ttl=43200)
def get_vix_data():
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "VIXCLS",
            "api_key": fred_api_key,
            "file_type": "json",
            "observation_start": start_date
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()['observations']
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['date'])
        df['Close'] = pd.to_numeric(df['value'], errors='coerce')
        df.set_index('Date', inplace=True)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.warning(f"⚠️ Failed to load VIX data: {e}")
        return pd.DataFrame(columns=['Date', 'Close'])

@st.cache_data(ttl=43200)
def get_msci_data():
    try:
        symbol = "VEA"  # MSCI World Proxy ETF
        url = f"https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 180,
            "apikey": twelvedata_api_key
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        if "values" not in data:
            raise ValueError(f"No MSCI World data returned ({symbol})")

        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.rename(columns={"datetime": "Date", "close": "Close"})
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.set_index("Date").sort_index()
        return df
    except Exception as e:
        st.warning(f"⚠️ Failed to load MSCI World proxy data (VEA): {e}")
        return pd.DataFrame(columns=['Date', 'Close'])

@st.cache_data(ttl=43200)
def get_fgi_history():
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=180&format=json")
        response.raise_for_status()
        data = response.json()['data']
        values = [int(day['value']) for day in reversed(data)]
        dates = [pd.to_datetime(day['timestamp'], unit='s') for day in reversed(data)]
        return pd.DataFrame({'Date': dates, 'Value': values})
    except Exception as e:
        st.warning(f"⚠️ Failed to load Fear & Greed data: {e}")
        return pd.DataFrame(columns=['Date', 'Value'])

# Load data
btc_data = get_bitcoin_data()
vix_data = get_vix_data()
msci_data = get_msci_data()
fgi_df = get_fgi_history()

crypto_fgi = fgi_df['Value'].iloc[-1] if not fgi_df.empty else "N/A"
crypto_fgi_prev = fgi_df['Value'].iloc[-2] if len(fgi_df) > 1 else "N/A"

# ------------------ Evaluation Functions ------------------

def sentiment_score_fgi(value):
    if value == "N/A":
        return "N/A", "⚪ Neutral"
    elif value < 25:
        return value, "🔴 Extreme Fear (Buy Opportunity?)"
    elif value < 50:
        return value, "🟠 Fear"
    elif value < 75:
        return value, "🟢 Greed"
    else:
        return value, "🟢🟢 Extreme Greed (Caution)"

def sentiment_score_vix(value):
    if value < 15:
        return "🟢 Calm (Low Volatility)"
    elif value < 25:
        return "🟠 Elevated Volatility"
    else:
        return "🔴 High Fear (Risk-Off Mode)"

# ------------------ Slider ------------------

st.sidebar.header("⏳ Date Range Selection")
day_range = st.sidebar.slider("Select number of days to display", min_value=7, max_value=180, value=180, step=1)
start_display_date = datetime.today() - timedelta(days=day_range)
btc_data = btc_data[btc_data.index >= start_display_date]
vix_data = vix_data[vix_data.index >= start_display_date]
msci_data = msci_data[msci_data.index >= start_display_date]
fgi_df = fgi_df[fgi_df['Date'] >= start_display_date]

# ------------------ Layout ------------------

st.header("🟧 Bitcoin Section")
col1, col2 = st.columns(2)
if not btc_data.empty:
    col1.metric("Bitcoin Price (EUR)", f"{btc_data['price'].iloc[-1]:,.0f}".replace(",", "."))
score_val, score_label = sentiment_score_fgi(crypto_fgi)
col2.metric("Crypto Fear & Greed Index", f"{score_val}", delta=f"{int(score_val) - int(crypto_fgi_prev)}" if score_val != "N/A" else "N/A")
st.write(f"**Crypto Sentiment Evaluation:** {score_label}")

st.subheader("📉 Bitcoin Price Trend")
if not btc_data.empty:
    fig_btc, ax_btc = plt.subplots()
    ax_btc.plot(btc_data.index, btc_data['price'], color='orange')
    ax_btc.set_title("Bitcoin Price (EUR)")
    ax_btc.set_ylabel("EUR")
    ax_btc.grid(True)
    ax_btc.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
    ax_btc.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", ".")))
    fig_btc.autofmt_xdate()
    st.pyplot(fig_btc)

st.subheader("📊 Crypto Fear & Greed Index")
if not fgi_df.empty:
    fig_fgi, ax_fgi = plt.subplots()
    ax_fgi.plot(fgi_df['Date'], fgi_df['Value'], color='purple')
    ax_fgi.set_title("Crypto Fear & Greed Index")
    ax_fgi.set_ylabel("Index Value")
    ax_fgi.set_ylim(0, 100)
    ax_fgi.grid(True)
    ax_fgi.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
    fig_fgi.autofmt_xdate()
    st.pyplot(fig_fgi)
else:
    st.warning("Could not load Fear & Greed data.")

st.markdown("---")

st.header("🌍 Market Section")
col3, col4 = st.columns(2)
if not msci_data.empty:
    col3.metric("MSCI World Proxy (VEA)", f"{msci_data['Close'].iloc[-1]:.2f}")
if not vix_data.empty:
    vix_sentiment = sentiment_score_vix(vix_data['Close'].iloc[-1])
    col4.metric("VIX Index", f"{vix_data['Close'].iloc[-1]:.2f}")
    st.write(f"**VIX Evaluation:** {vix_sentiment}")

st.subheader("📉 MSCI World Proxy (VEA) Trend")
if not msci_data.empty:
    fig_msci, ax_msci = plt.subplots()
    ax_msci.plot(msci_data.index, msci_data['Close'], color='green')
    ax_msci.set_title("MSCI World Proxy (VEA)")
    ax_msci.set_ylabel("USD")
    ax_msci.grid(True)
    ax_msci.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
    fig_msci.autofmt_xdate()
    st.pyplot(fig_msci)

st.subheader("📉 VIX Index Trend")
if not vix_data.empty:
    fig_vix, ax_vix = plt.subplots()
    ax_vix.plot(vix_data.index, vix_data['Close'], color='blue')
    ax_vix.set_title("VIX Index")
    ax_vix.set_ylabel("Volatility")
    ax_vix.grid(True)
    ax_vix.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
    fig_vix.autofmt_xdate()
    st.pyplot(fig_vix)
