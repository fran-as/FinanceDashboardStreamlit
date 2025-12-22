import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
import plotly.express as px

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
    # Formato numérico estándar con separador de miles
    try:
        return f"{x:,.2f}"
    except Exception:
        return x

# --------- YAHOO FINANCE ---------
def fetch_yahoo(symbols):
    rows = []
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="2d")
            price = hist["Close"][-1]
            prev  = hist["Close"][-2]
        except Exception:
            price = None
            prev  = None
        rows.append({"Symbol": sym, "Price": price, "Previous Close": prev})
    return pd.DataFrame(rows)

# --------- CARGA ESTÁTICA Y MERGE ---------
@st.cache_data(show_spinner="📥 Cargando datos estáticos…")
def load_static(portfolio_path, cache_path):
    # Lee el CSV consolidado (CSyRacional.csv)
    p_df = pd.read_csv(portfolio_path)

    # 🔧 ARREGLO MÍNIMO: mapear columnas del consolidado a lo que espera el app
    # El CSV trae: ['symbol','description','total_quantity','total_cost_basis','avg_cost_per_share']
    rename_map = {
        "symbol": "Symbol",
        "description": "Description",
        "total_quantity": "Quantity",
        "avg_cost_per_share": "Cost/Share",
    }
    # Si ya vinieron con mayúsculas, esto no afecta
    p_df = p_df.rename(columns=rename_map)

    # Asegurar columnas mínimas para el flujo del app
    for col in ["Symbol", "Description", "Quantity", "Cost/Share"]:
        if col not in p_df.columns:
            p_df[col] = None

    # Tipos numéricos
    p_df["Quantity"]   = pd.to_numeric(p_df["Quantity"], errors="coerce")
    p_df["Cost/Share"] = pd.to_numeric(p_df["Cost/Share"], errors="coerce")

    # Normalizar tickers
    p_df["Symbol"] = p_df["Symbol"].astype(str).str.strip().str.upper()

    # Lee el cache si existe (con símbolos previos, P/E u otros campos derivados)
    try:
        c_df = pd.read_csv(cache_path)
    except FileNotFoundError:
        c_df = pd.DataFrame(columns=["Symbol"])

    # Si el cache usa 'symbol' en minúsculas, normalizar
    if "symbol" in c_df.columns and "Symbol" not in c_df.columns:
        c_df = c_df.rename(columns={"symbol": "Symbol"})

    if "Symbol" in c_df.columns:
        c_df["Symbol"] = c_df["Symbol"].astype(str).str.strip().str.upper()

    # Evitar duplicar precios aquí; se refrescan con Yahoo
    c_df = c_df.drop(columns=["Price", "Previous Close"], errors="ignore")

    # Merge por Symbol (tal como estaba)
    return pd.merge(p_df, c_df, on="Symbol", how="left")

# --------- EJECUCIÓN PRINCIPAL ---------
if os.path.exists(PORTFOLIO_PATH) and os.path.exists(CACHE_PATH):
    static_df = load_static(PORTFOLIO_PATH, CACHE_PATH)
    yahoo_df  = fetch_yahoo(static_df["Symbol"].tolist())
    df = pd.merge(static_df, yahoo_df, on="Symbol", how="left")

    # Cálculos dinámicos
    df["Market Value"] = df["Quantity"] * df["Price"]
    df["Cost Basis"]   = df["Quantity"] * df["Cost/Share"]
    df["Gain/Loss $"]  = df["Market Value"] - df["Cost Basis"]
    df["Gain/Loss %"]  = df["Gain/Loss $"] / df["Cost Basis"] * 100
    df["Day Change %"] = (df["Price"] - df["Previous Close"]) / df["Previous Close"] * 100
    df["Day Change $"] = df["Quantity"] * (df["Price"] - df["Previous Close"])

    # Totales y % de cuenta
    tmv  = df["Market Value"].sum()
    tcb  = df["Cost Basis"].sum()
    tgl  = df["Gain/Loss $"].sum()
    tglp = (tgl / tcb * 100) if tcb else 0
    tdc  = df["Day Change $"].sum()
    tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
    cash = 2519.36  # valor usado por el app original
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

    # 📊 Position details
    st.markdown("## 📊 Equities - Position details")
    base_cols = ["Symbol","Description","Quantity","Cost/Share","Price","Previous Close",
                 "Day Change %","Day Change $","P/E","Market Value","Gain/Loss %","% of Acct"]

    # columnas faltantes (por si el cache no las trae)
    for missing in base_cols:
        if missing not in df.columns:
            df[missing] = None

    styled = df[base_cols].style.map(
        highlight_positive_negative,
        subset=["Day Change %","Day Change $","Gain/Loss %"]
    )
    num_cols = df[base_cols].select_dtypes("number").columns
    st.dataframe(
        styled.format(format_eur_safe, subset=num_cols),
        use_container_width=True, height=420
    )

    # 🟢 Top movers
    st.markdown("## 🟢 Top Movers")
    def show_table(sub_df, title):
        st.markdown(f"### {title}")
        # Renombrar columnas según requerimiento
        renamed = sub_df.rename(columns={
            "Market Value": "Mkt Val",
            "Day Change $": "Price Chng $",
            "Day Change %": "Price Chng %"
        })
        table_cols = ["Symbol","Description","Price","Mkt Val","Price Chng $","Price Chng %","Gain/Loss %","% of Acct"]
        # columnas faltantes por seguridad
        for c in table_cols:
            if c not in renamed.columns:
                renamed[c] = None
        styled_tbl = renamed[table_cols].style.map(
            highlight_positive_negative,
            subset=["Price Chng %","Price Chng $","Gain/Loss %"]
        )
        st.dataframe(
            styled_tbl.format(format_eur_safe, subset=table_cols[2:]),
            use_container_width=True, height=360
        )

    # Top Gainers / Losers (día)
    day_sorted = df.sort_values("Day Change $", ascending=False).copy()
    show_table(day_sorted.head(10), "Top Gainers (Day)")
    show_table(day_sorted.tail(10), "Top Losers (Day)")

else:
    st.error("No se encontraron los archivos requeridos en la carpeta Data (CSyRacional.csv y cached_data.csv).")
    st.write("Verifica las rutas:")
    st.code(f"PORTFOLIO_PATH = {PORTFOLIO_PATH}\nCACHE_PATH = {CACHE_PATH}")
