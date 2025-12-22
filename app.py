import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")

# --------- RUTAS ---------
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH     = os.path.join("Data", "cached_data.csv")

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

def format_eur_safe(x):
    try:
        return f"{x:,.2f}"
    except Exception:
        return x

# --------- CARGA YAHOO FINANCE ---------
def fetch_yahoo(symbols):
    rows = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            info = ticker.info
            price = hist["Close"][-1]
            prev  = hist["Close"][-2]
            pe_ratio = info.get("trailingPE")
            long_name = info.get("longName", "")
        except Exception:
            price = None
            prev  = None
            pe_ratio = None
            long_name = ""
        rows.append({
            "Symbol": sym,
            "Price": price,
            "Previous Close": prev,
            "P/E": pe_ratio,
            "Description": long_name
        })
    return pd.DataFrame(rows)

# --------- CARGA ESTÁTICA Y MERGE ---------
@st.cache_data(show_spinner="📥 Cargando datos…")
def load_static(portfolio_path, cache_path):
    p_df = pd.read_csv(portfolio_path)

    # ✅ Renombrar columnas según estructura real
    rename_map = {
        "symbol": "Symbol",
        "description": "Description",
        "total_quantity": "Quantity",
        "avg_cost_per_share": "Cost/Share",
        "total_cost_basis": "Cost Basis"
    }
    p_df = p_df.rename(columns=rename_map)

    for col in ["Symbol", "Quantity", "Cost/Share"]:
        p_df[col] = pd.to_numeric(p_df[col], errors="coerce")
    p_df["Symbol"] = p_df["Symbol"].astype(str).str.strip().str.upper()

    # Cache opcional si existiera
    try:
        c_df = pd.read_csv(cache_path)
        if "symbol" in c_df.columns and "Symbol" not in c_df.columns:
            c_df = c_df.rename(columns={"symbol": "Symbol"})
        c_df["Symbol"] = c_df["Symbol"].astype(str).str.strip().str.upper()
        c_df = c_df.drop(columns=["Price", "Previous Close"], errors="ignore")
    except FileNotFoundError:
        c_df = pd.DataFrame(columns=["Symbol"])

    return pd.merge(p_df, c_df, on="Symbol", how="left")

# --------- MAIN ---------
if os.path.exists(PORTFOLIO_PATH):
    static_df = load_static(PORTFOLIO_PATH, CACHE_PATH)
    yahoo_df = fetch_yahoo(static_df["Symbol"].tolist())
    df = pd.merge(static_df, yahoo_df, on="Symbol", how="left")

    # Calcular dinámicos
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
    cash = 2519.36  # hardcoded cash value
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

    # 📊 Tabla
    st.markdown("## 📊 Equities - Position details")
    base_cols = [
        "Symbol","Description","Quantity","Cost/Share","Price","Previous Close",
        "Day Change %","Day Change $","P/E","Market Value","Gain/Loss %","% of Acct"
    ]
    for col in base_cols:
        if col not in df.columns:
            df[col] = None

    styled = df[base_cols].style.map(
        highlight_positive_negative,
        subset=["Day Change %","Day Change $","Gain/Loss %"]
    )
    st.dataframe(
        styled.format(format_eur_safe, subset=df.select_dtypes("number").columns),
        use_container_width=True, height=450
    )

    # 🟢 Top Movers
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
            styled_tbl.format(format_eur_safe, subset=table_cols[2:]),
            use_container_width=True, height=360
        )

    sorted_day = df.sort_values("Day Change $", ascending=False)
    show_table(sorted_day.head(10), "Top Gainers (Day)")
    show_table(sorted_day.tail(10), "Top Losers (Day)")

else:
    st.error("No se encontró el archivo CSyRacional.csv")
