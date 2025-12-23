import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

st.set_page_config(layout="wide")

# --------- RUTAS ---------
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH     = os.path.join("Data", "cached_data.csv")

# --------- AUTOREFRESH CADA 5 MINUTOS ---------
st_autorefresh(interval=5 * 60 * 1000, key="auto_refresh")

st.title("📈 Finance Dashboard")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --------- HELPERS ---------
def highlight_positive_negative(val):
    try:
        v = float(val)
    except Exception:
        return ""
    if v > 0:
        return "color: green;"
    if v < 0:
        return "color: crimson;"
    return ""

def format_usd_safe(x):
    try:
        return f"${x:,.2f}"
    except:
        return x

@st.cache_data(show_spinner="📥 Cargando datos…")
def load_static_data():
    df = pd.read_csv(PORTFOLIO_PATH)
    df.rename(columns={
        "symbol": "Symbol",
        "description": "Description",
        "total_quantity": "Quantity",
        "avg_cost_per_share": "Cost/Share"
    }, inplace=True)
    return df

def fetch_yahoo_info(symbols):
    data = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            info = ticker.info
            data.append({
                "Symbol": sym,
                "Price": hist["Close"][-1] if len(hist) > 1 else None,
                "Previous Close": hist["Close"][-2] if len(hist) > 1 else None,
                "P/E": info.get("trailingPE", None),
                "Description_yahoo": info.get("longName", None),
                "Sector": info.get("sector", "Unknown")
            })
        except Exception:
            data.append({
                "Symbol": sym,
                "Price": None,
                "Previous Close": None,
                "P/E": None,
                "Description_yahoo": None,
                "Sector": "Unknown"
            })
    return pd.DataFrame(data)

# --------- MAIN ---------
df_static = load_static_data()
symbols = df_static["Symbol"].dropna().unique().tolist()
df_yahoo = fetch_yahoo_info(symbols)

df = pd.merge(df_static, df_yahoo, on="Symbol", how="left")

# Asegurar que Description no sea NaN
df["Description"] = df["Description_yahoo"].combine_first(df["Description"])

# Cálculos financieros
df["Market Value"] = df["Quantity"] * df["Price"]
df["Cost Basis"]   = df["Quantity"] * df["Cost/Share"]
df["Gain/Loss $"]  = df["Market Value"] - df["Cost Basis"]
df["Gain/Loss %"]  = df["Gain/Loss $"] / df["Cost Basis"] * 100
df["Day Change %"] = (df["Price"] - df["Previous Close"]) / df["Previous Close"] * 100
df["Day Change $"] = df["Quantity"] * (df["Price"] - df["Previous Close"])

# Totales
cash = 2519.36  # efectivo manual
tmv  = df["Market Value"].sum()
tcb  = df["Cost Basis"].sum()
tgl  = df["Gain/Loss $"].sum()
tav  = tmv + cash
tdc  = df["Day Change $"].sum()
tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
tglp = (tgl / tcb * 100) if tcb else 0
df["% of Acct"] = df["Market Value"] / tav * 100

# 💼 Account Summary
st.markdown("## 💼 Account Summary")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Accounts Value",       f"$ {tav:,.2f}")
c2.metric("Total Cash & Cash Invest",   f"$ {cash:,.2f}")
c3.metric("Total Market Value",         f"$ {tmv:,.2f}")
c4.metric("Total Day Change",           f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
c5.metric("Total Cost Basis",           f"$ {tcb:,.2f}")
c6.metric("Total Gain/Loss",            f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

# 📊 Tabla
st.markdown("## 📊 Posiciones")
table_cols = ["Symbol", "Description", "Quantity", "Cost/Share", "Price", "Previous Close", "Day Change %", "Day Change $", "P/E", "Market Value", "Gain/Loss %", "% of Acct"]

for col in table_cols:
    if col not in df.columns:
        df[col] = None

styled = df[table_cols].style.map(
    highlight_positive_negative,
    subset=["Day Change %", "Day Change $", "Gain/Loss %"]
)

num_cols = df[table_cols].select_dtypes("number").columns
st.dataframe(styled.format(format_usd_safe, subset=num_cols), use_container_width=True, height=420)

# 📈 Pie chart por sector
st.markdown("## 🧭 Exposición por Sector")
df_sector = (
    df.groupby("Sector")["Market Value"]
    .sum()
    .reset_index()
    .sort_values("Market Value", ascending=False)
)

fig = px.pie(
    df_sector,
    values="Market Value",
    names="Sector",
    title="Distribución por Sector",
    hole=0.4
)
st.plotly_chart(fig, use_container_width=True)
