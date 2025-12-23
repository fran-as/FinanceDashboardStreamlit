import streamlit as st
import pandas as pd
import yfinance as yf
import os
import json
import urllib.request
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

st.set_page_config(layout="wide")

# --------- RUTAS ---------
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH     = os.path.join("Data", "cached_data.csv")
CRYPTO_PATH    = os.path.join("Data", "crypto_portfolio_quantities.csv")

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

def badge_html(value, label):
    is_pos = value >= 0
    arrow = "▲" if is_pos else "▼"
    bg = "#E7F6EC" if is_pos else "#FDECEC"
    fg = "#137333" if is_pos else "#B3261E"
    return (
        "<span style='"
        "font-size:0.78em;"
        "padding:2px 8px;"
        "border-radius:999px;"
        f"background:{bg};"
        f"color:{fg};"
        "font-weight:600;"
        "margin-left:6px;"
        "vertical-align:middle;"
        f"'> {arrow} {value:+.2f}% {label}</span>"
    )

@st.cache_data(show_spinner="🪙 Cargando cripto…", ttl=300)
def load_crypto_data():
    if not os.path.exists(CRYPTO_PATH):
        return pd.DataFrame(columns=["Symbol", "Description", "Quantity"])
    df = pd.read_csv(CRYPTO_PATH)
    df.rename(
        columns={
            "symbol": "Symbol",
            "description": "Description",
            "total_quantity": "Quantity",
        },
        inplace=True,
    )
    for col in ["Symbol", "Description", "Quantity"]:
        if col not in df.columns:
            df[col] = None
    return df[["Symbol", "Description", "Quantity"]]

@st.cache_data(show_spinner="🪙 Consultando CoinGecko…", ttl=300)
def fetch_coingecko_prices(symbols):
    id_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "STETH": "staked-ether",
        "WETH": "weth",
        "UNI": "uniswap",
        "LINK": "chainlink",
        "DAI": "dai",
        "DAI2": "dai",
        "USDT": "tether",
        "STMATIC": "staked-matic",
    }
    ids = [id_map.get(sym) for sym in symbols if id_map.get(sym)]
    if not ids:
        return pd.DataFrame(columns=["Symbol", "Price", "Day Change %"])

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={','.join(sorted(set(ids)))}&vs_currencies=usd&include_24hr_change=true"
    )
    with urllib.request.urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rows = []
    for sym in symbols:
        cg_id = id_map.get(sym)
        if not cg_id:
            rows.append({"Symbol": sym, "Price": None, "Day Change %": None})
            continue
        data = payload.get(cg_id, {})
        rows.append(
            {
                "Symbol": sym,
                "Price": data.get("usd"),
                "Day Change %": data.get("usd_24h_change"),
            }
        )
    return pd.DataFrame(rows)

def load_cached_yahoo():
    if not os.path.exists(CACHE_PATH):
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Price",
                "Previous Close",
                "P/E",
                "Description_yahoo",
                "Sector",
                "Updated",
            ]
        )

    df = pd.read_csv(CACHE_PATH)
    df.rename(
        columns={
            "Description": "Description_yahoo",
            "Prev Close": "Previous Close",
        },
        inplace=True,
    )
    for col in [
        "Symbol",
        "Price",
        "Previous Close",
        "P/E",
        "Description_yahoo",
        "Sector",
        "Updated",
    ]:
        if col not in df.columns:
            df[col] = None
    return df[
        [
            "Symbol",
            "Price",
            "Previous Close",
            "P/E",
            "Description_yahoo",
            "Sector",
            "Updated",
        ]
    ]

def save_cached_yahoo(df_yahoo):
    df_yahoo.to_csv(CACHE_PATH, index=False)

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
    cached = load_cached_yahoo()
    if not cached.empty:
        cached = cached.drop_duplicates(subset=["Symbol"], keep="last").set_index("Symbol", drop=False)

    data = []
    for sym in symbols:
        cached_row = cached.loc[sym] if not cached.empty and sym in cached.index else None
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            info = ticker.info or {}
            row = {
                "Symbol": sym,
                "Price": hist["Close"].iloc[-1] if len(hist) >= 1 else None,
                "Previous Close": hist["Close"].iloc[-2] if len(hist) >= 2 else None,
                "P/E": info.get("trailingPE", None),
                "Description_yahoo": info.get("longName", None),
                "Sector": info.get("sector", "Unknown"),
                "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if cached_row is not None:
                for key in ["Price", "Previous Close", "P/E", "Description_yahoo", "Sector"]:
                    if row[key] is None or (key == "Sector" and row[key] == "Unknown"):
                        row[key] = cached_row.get(key)
            data.append(row)
        except Exception:
            if cached_row is not None:
                data.append(cached_row.to_dict())
            else:
                data.append({
                    "Symbol": sym,
                    "Price": None,
                    "Previous Close": None,
                    "P/E": None,
                    "Description_yahoo": None,
                    "Sector": "Unknown",
                    "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
    df_yahoo = pd.DataFrame(data)
    save_cached_yahoo(df_yahoo)
    return df_yahoo

# --------- MAIN ---------
df_static = load_static_data()
symbols = df_static["Symbol"].dropna().unique().tolist()
df_yahoo = fetch_yahoo_info(symbols)

df = pd.merge(df_static, df_yahoo, on="Symbol", how="left")

# --------- CRYPTO ---------
df_crypto = load_crypto_data()
crypto_symbols = df_crypto["Symbol"].dropna().unique().tolist()
df_crypto_prices = fetch_coingecko_prices(crypto_symbols)
df_crypto = pd.merge(df_crypto, df_crypto_prices, on="Symbol", how="left")
df_crypto["Market Value"] = df_crypto["Quantity"] * df_crypto["Price"]
df_crypto["Day Change $"] = df_crypto["Market Value"] * df_crypto["Day Change %"] / 100

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
tcmv = df_crypto["Market Value"].sum()
tcd  = df_crypto["Day Change $"].sum()
tcb  = df["Cost Basis"].sum()
tgl  = df["Gain/Loss $"].sum()
tav  = tmv + tcmv + cash
tdc_eq = df["Day Change $"].sum()
tdc  = tdc_eq + tcd
tdcp = (tdc / ((tmv + tcmv) - tdc) * 100) if ((tmv + tcmv) - tdc) else 0
tglp = (tgl / tcb * 100) if tcb else 0
tdc_eqp = (tdc_eq / (tmv - tdc_eq) * 100) if (tmv - tdc_eq) else 0
tdc_cp = (tcd / (tcmv - tcd) * 100) if (tcmv - tcd) else 0
df["% of Acct"] = df["Market Value"] / tav * 100

# 💼 Account Summary
st.markdown("## 💼 Account Summary")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Accounts Value",       f"$ {tav:,.2f}")
c2.metric("Total Cash & Cash Invest",   f"$ {cash:,.2f}")
c3.metric("Total Market Value",         f"$ {(tmv + tcmv):,.2f}")
c4.metric("Total Day Change",           f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
c5.metric("Total Cost Basis",           f"$ {tcb:,.2f}")
c6.metric("Total Gain/Loss",            f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

# 📊 Tabla
eq_color_period = "green" if tglp >= 0 else "crimson"
eq_color_day = "green" if tdc_eqp >= 0 else "crimson"
st.markdown(
    "## 📊 Acciones y ETF"
    "<div style='margin-top:4px;font-size:0.88em;color:#4B5563;'>"
    f"$ {tmv:,.2f}"
    f"{badge_html(tglp, 'total')}"
    f"{badge_html(tdc_eqp, 'diario')}"
    "</div>",
    unsafe_allow_html=True,
)
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

# 🪙 Crypto
crypto_color_day = "green" if tdc_cp >= 0 else "crimson"
st.markdown(
    "## 🪙 Cripto"
    "<div style='margin-top:4px;font-size:0.88em;color:#4B5563;'>"
    f"$ {tcmv:,.2f}"
    f"{badge_html(tdc_cp, 'diario')}"
    "</div>",
    unsafe_allow_html=True,
)
crypto_cols = [
    "Symbol",
    "Description",
    "Quantity",
    "Price",
    "Day Change %",
    "Day Change $",
    "Market Value",
]
for col in crypto_cols:
    if col not in df_crypto.columns:
        df_crypto[col] = None

crypto_styled = df_crypto[crypto_cols].style.map(
    highlight_positive_negative,
    subset=["Day Change %", "Day Change $"],
)
crypto_styled = crypto_styled.format(
    {
        "Quantity": "{:,.6f}",
        "Price": "${:,.2f}",
        "Day Change %": "{:+.2f}%",
        "Day Change $": "${:+,.2f}",
        "Market Value": "${:,.2f}",
    }
)
st.dataframe(crypto_styled, use_container_width=True, height=320)

# 📈 Pie chart por sector
st.markdown("## 🧭 Exposición por Sector")
df_sector = (
    df.groupby("Sector")["Market Value"]
    .sum()
    .reset_index()
    .sort_values("Market Value", ascending=False)
)
df_sector = pd.concat(
    [
        df_sector,
        pd.DataFrame(
            [{"Sector": "Crypto", "Market Value": df_crypto["Market Value"].sum()}]
        ),
    ],
    ignore_index=True,
)
df_sector = df_sector.groupby("Sector", as_index=False)["Market Value"].sum()
df_sector = df_sector.sort_values("Market Value", ascending=False)

fig = px.pie(
    df_sector,
    values="Market Value",
    names="Sector",
    title="Distribución por Sector",
    hole=0.4
)
st.plotly_chart(fig, use_container_width=True)
