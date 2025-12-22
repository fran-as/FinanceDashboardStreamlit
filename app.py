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

st_autorefresh(interval=5 * 60 * 1000, key="auto_refresh")

st.title("📈 Finance Dashboard")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --------- HELPERS ---------
def highlight_positive_negative(val):
    try:
        v = float(val)
        if v > 0:
            return "color: green;"
        elif v < 0:
            return "color: crimson;"
    except Exception:
        pass
    return ""

def format_eur_safe(x):
    try:
        return f"{x:,.2f}"
    except Exception:
        return x

# --------- CARGA ESTÁTICA ---------
@st.cache_data(show_spinner="📥 Cargando datos...")
def load_static(path):
    df = pd.read_csv(path)
    df = df.rename(columns={
        "symbol": "Symbol",
        "description": "Description",
        "total_quantity": "Quantity",
        "avg_cost_per_share": "Cost/Share",
        "total_cost_basis": "Cost Basis"
    })

    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["Cost/Share"] = pd.to_numeric(df["Cost/Share"], errors="coerce")
    return df

# --------- YAHOO FINANCE + CACHE UPDATE ---------
def fetch_yahoo_and_update_cache(symbols, cache_path):
    try:
        cache = pd.read_csv(cache_path)
        cache["Symbol"] = cache["Symbol"].astype(str).str.strip().str.upper()
    except FileNotFoundError:
        cache = pd.DataFrame(columns=["Symbol", "Price", "Previous Close", "P/E", "Description"])

    updated_rows = []
    for sym in symbols:
        if not sym or sym.strip().upper() == "NAN":
            continue
        if sym in cache["Symbol"].values:
            continue  # ya está cacheado

        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            price = hist["Close"][-1]
            prev = hist["Close"][-2]
            pe = ticker.info.get("trailingPE")
            name = ticker.info.get("longName", "")
        except Exception:
            price, prev, pe, name = None, None, None, ""

        updated_rows.append({
            "Symbol": sym,
            "Price": price,
            "Previous Close": prev,
            "P/E": pe,
            "Description": name
        })

    if updated_rows:
        new_cache = pd.concat([cache, pd.DataFrame(updated_rows)], ignore_index=True)
        new_cache = new_cache.drop_duplicates(subset="Symbol", keep="last")
        new_cache.to_csv(cache_path, index=False)
        return new_cache
    else:
        return cache

# --------- MAIN ---------
if os.path.exists(PORTFOLIO_PATH):
    df_static = load_static(PORTFOLIO_PATH)
    symbols = df_static["Symbol"].dropna().unique().tolist()
    df_cache = fetch_yahoo_and_update_cache(symbols, CACHE_PATH)
    df = pd.merge(df_static, df_cache, on="Symbol", how="left")

    # Cálculos
    df["Market Value"] = df["Quantity"] * df["Price"]
    df["Cost Basis"] = df["Quantity"] * df["Cost/Share"]
    df["Gain/Loss $"] = df["Market Value"] - df["Cost Basis"]
    df["Gain/Loss %"] = df["Gain/Loss $"] / df["Cost Basis"] * 100
    df["Day Change %"] = (df["Price"] - df["Previous Close"]) / df["Previous Close"] * 100
    df["Day Change $"] = df["Quantity"] * (df["Price"] - df["Previous Close"])

    tmv = df["Market Value"].sum()
    tcb = df["Cost Basis"].sum()
    tgl = df["Gain/Loss $"].sum()
    tglp = (tgl / tcb * 100) if tcb else 0
    tdc = df["Day Change $"].sum()
    tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
    cash = 2519.36
    tav = tmv + cash
    df["% of Acct"] = df["Market Value"] / tav * 100

    # 💼 Summary
    st.markdown("## 💼 Account Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Accounts Value", f"$ {tav:,.2f}")
    c2.metric("Total Cash & Cash Invest", f"$ {cash:,.2f}")
    c3.metric("Total Market Value", f"$ {tmv:,.2f}")
    c4.metric("Total Day Change", f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
    c5.metric("Total Cost Basis", f"$ {tcb:,.2f}")
    c6.metric("Total Gain/Loss", f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

    # 📊 Tabla principal
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
    styled_cols = df[base_cols].select_dtypes("number").columns
    st.dataframe(
        styled.format(format_eur_safe, subset=styled_cols),
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
    st.error("⚠️ No se encontró el archivo consolidado CSyRacional.csv")
