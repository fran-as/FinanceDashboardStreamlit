import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")

# --------- RUTAS ---------
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")

# --------- AUTOREFRESH CADA 5 MINUTOS ---------
st_autorefresh(interval=5 * 60 * 1000, key="auto_refresh")

st.title("📈 Finance Dashboard")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --------- HELPERS VISUALES ---------
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

def format_usd(x):
    try:
        return f"{x:,.2f}"
    except Exception:
        return x

# --------- YAHOO FINANCE ---------
@st.cache_data(show_spinner="🔄 Consultando Yahoo Finance...")
def fetch_yahoo(symbols):
    rows = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
            hist = ticker.history(period="2d")

            price = hist["Close"][-1] if "Close" in hist else None
            prev  = hist["Close"][-2] if "Close" in hist else None
            pe    = info.get("trailingPE", None)
            desc  = info.get("longName", None)

            rows.append({
                "Symbol": sym,
                "Price": price,
                "Previous Close": prev,
                "P/E": pe,
                "Description": desc
            })
        except Exception:
            rows.append({
                "Symbol": sym,
                "Price": None,
                "Previous Close": None,
                "P/E": None,
                "Description": None
            })
    return pd.DataFrame(rows)

# --------- CARGA Y MERGE PRINCIPAL ---------
@st.cache_data(show_spinner="📥 Cargando portafolio…")
def load_portfolio(path):
    df = pd.read_csv(path)
    rename_map = {
        "symbol": "Symbol",
        "description": "Description",
        "total_quantity": "Quantity",
        "avg_cost_per_share": "Cost/Share"
    }
    df = df.rename(columns=rename_map)

    # Tipos numéricos
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["Cost/Share"] = pd.to_numeric(df["Cost/Share"], errors="coerce")

    # Normalizar tickers
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()

    return df

# --------- EJECUCIÓN ---------
if os.path.exists(PORTFOLIO_PATH):
    static_df = load_portfolio(PORTFOLIO_PATH)
    yahoo_df  = fetch_yahoo(static_df["Symbol"].tolist())

    # Merge por Symbol, priorizando descripción de Yahoo si está disponible
    df = pd.merge(static_df, yahoo_df, on="Symbol", how="left")
    df["Description"] = df["Description_yahoo"].combine_first(df["Description"])
    df = df.drop(columns=["Description_yahoo"], errors="ignore")

    # Cálculos
    df["Market Value"] = df["Quantity"] * df["Price"]
    df["Cost Basis"]   = df["Quantity"] * df["Cost/Share"]
    df["Gain/Loss $"]  = df["Market Value"] - df["Cost Basis"]
    df["Gain/Loss %"]  = df["Gain/Loss $"] / df["Cost Basis"] * 100
    df["Day Change %"] = (df["Price"] - df["Previous Close"]) / df["Previous Close"] * 100
    df["Day Change $"] = df["Quantity"] * (df["Price"] - df["Previous Close"])

    # Totales
    tmv  = df["Market Value"].sum()
    tcb  = df["Cost Basis"].sum()
    tgl  = df["Gain/Loss $"].sum()
    tglp = (tgl / tcb * 100) if tcb else 0
    tdc  = df["Day Change $"].sum()
    tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
    cash = 2519.36  # valor configurable
    tav  = tmv + cash
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

    # 📊 Detalles
    st.markdown("## 📊 Equities - Position details")
    base_cols = ["Symbol","Description","Quantity","Cost/Share","Price","Previous Close",
                 "Day Change %","Day Change $","P/E","Market Value","Gain/Loss %","% of Acct"]
    for col in base_cols:
        if col not in df.columns:
            df[col] = None

    styled = df[base_cols].style.map(
        highlight_positive_negative,
        subset=["Day Change %","Day Change $","Gain/Loss %"]
    )
    num_cols = df[base_cols].select_dtypes("number").columns
    st.dataframe(
        styled.format(format_usd, subset=num_cols),
        use_container_width=True, height=420
    )

    # 🔝 Top Movers
    st.markdown("## 🟢 Top Movers")
    def show_table(sub_df, title):
        st.markdown(f"### {title}")
        renamed = sub_df.rename(columns={
            "Market Value": "Mkt Val",
            "Day Change $": "Price Chng $",
            "Day Change %": "Price Chng %"
        })
        table_cols = ["Symbol","Description","Price","Mkt Val","Price Chng $","Price Chng %","Gain/Loss %","% of Acct"]
        for col in table_cols:
            if col not in renamed.columns:
                renamed[col] = None
        styled_tbl = renamed[table_cols].style.map(
            highlight_positive_negative,
            subset=["Price Chng %","Price Chng $","Gain/Loss %"]
        )
        st.dataframe(
            styled_tbl.format(format_usd, subset=table_cols[2:]),
            use_container_width=True, height=360
        )

    day_sorted = df.sort_values("Day Change $", ascending=False).copy()
    show_table(day_sorted.head(10), "Top Gainers (Day)")
    show_table(day_sorted.tail(10), "Top Losers (Day)")

else:
    st.error("No se encontró el archivo CSyRacional.csv en la carpeta Data.")
