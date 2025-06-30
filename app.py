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
refresh_count = st_autorefresh(interval=300_000, limit=None, key="datarefresh")
if refresh_count > 0 or st.button("🔄 Refrescar datos"):
    st.cache_data.clear()

# --------- HORA DE ÚLTIMA ACTUALIZACIÓN (CLIENTE) ---------
components.html(
    """
    <div style="font-size:1.1em; margin-bottom:1em;">
      Última actualización (hora local): <span id="client-time"></span>
    </div>
    <script>
      function updateTime() {
        document.getElementById("client-time").innerText = new Date().toLocaleString();
      }
      updateTime();
      setInterval(updateTime, 60*1000);
    </script>
    """,
    height=70,
)

# --------- UTILITIES ---------
def highlight_positive_negative(val):
    if isinstance(val, (int, float)):
        return f"color: {'green' if val>0 else 'red' if val<0 else 'black'}"
    return ""

def format_eur_safe(x):
    try:
        return "{:,.2f}".format(float(x)) \
                 .replace(",", "X") \
                 .replace(".", ",") \
                 .replace("X", ".")
    except:
        return x

# --------- FETCH DINÁMICO DESDE YAHOO ---------
@st.cache_data(show_spinner="📡 Obteniendo precios de Yahoo…")
def fetch_yahoo(symbols):
    rows = []
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="2d")
            price = hist["Close"][-1]
            prev  = hist["Close"][-2]
        except:
            price = None
            prev  = None
        rows.append({"Symbol": sym, "Price": price, "Previous Close": prev})
    return pd.DataFrame(rows)

# --------- CARGA ESTÁTICA Y MERGE ---------
@st.cache_data(show_spinner="📥 Cargando datos estáticos…")
def load_static(portfolio_path, cache_path):
    p_df = pd.read_csv(portfolio_path)
    c_df = pd.read_csv(cache_path).drop(columns=["Price","Previous Close"], errors="ignore")
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
    cash = 4151.72
    tav  = tmv + cash
    df["% of Acct"] = df["Market Value"] / tav * 100

    # 💼 Account Summary
    st.markdown("## 💼 Account Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Accounts Value",   f"$ {tav:,.2f}")
    c2.metric("Total Cash & Cash Invest", f"$ {cash:,.2f}")
    c3.metric("Total Market Value",     f"$ {tmv:,.2f}")
    c4.metric("Total Day Change",       f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
    c5.metric("Total Cost Basis",       f"$ {tcb:,.2f}")
    c6.metric("Total Gain/Loss",        f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

    # 📊 Position details
    st.markdown("## 📊 Equities - Position details")
    base_cols = ["Symbol","Description","Quantity","Cost/Share","Price","Previous Close",
                 "Day Change %","Day Change $","P/E","Market Value","Gain/Loss %","% of Acct"]
    styled = df[base_cols].style.map(
        highlight_positive_negative,
        subset=["Day Change %","Day Change $","Gain/Loss %"]
    )
    num_cols = df[base_cols].select_dtypes("number").columns
    st.dataframe(
        styled.format(format_eur_safe, subset=num_cols),
        use_container_width=True, hide_index=True
    )

    # Función para mostrar tablas Top/Bottom
    def show_table(sub_df, title):
        st.markdown(f"### {title}")
        # Renombrar columnas según requerimiento
        renamed = sub_df.rename(columns={
            "Market Value": "Mkt Val",
            "Day Change $": "Price Chng $",
            "Day Change %": "Price Chng %"
        })
        table_cols = ["Symbol","Description","Price","Mkt Val","Price Chng $","Price Chng %","Gain/Loss %","% of Acct"]
        styled_tbl = renamed[table_cols].style.map(
            highlight_positive_negative,
            subset=["Price Chng %","Price Chng $","Gain/Loss %"]
        )
        st.dataframe(
            styled_tbl.format(format_eur_safe, subset=table_cols[2:]),
            use_container_width=True, hide_index=True
        )

    # 🏆 Top 5 Holdings by Market Value (Mejores y Peores)
    show_table(df.nlargest(5, "Market Value"), "🏆 Top 5 Holdings by Market Value (Mejores)")
    show_table(df.nsmallest(5, "Market Value"), "📉 Top 5 Holdings by Market Value (Peores)")

    # 📈 Top/Bottom 5 por Day Change %
    show_table(df.nlargest(5, "Day Change %"), "📈 Top 5 by Day Change %")
    show_table(df.nsmallest(5, "Day Change %"), "📉 Bottom 5 by Day Change %")

    # 📊 Exposure by Sector (Pie Chart)
    st.markdown("### 📊 Exposure by Sector")
    sector_sum = df.groupby("Sector", as_index=False)["Market Value"].sum()
    fig = px.pie(sector_sum, names="Sector", values="Market Value",
                 title="Portfolio Exposure by Sector")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("❗ Asegúrate de tener ambos CSV en la carpeta Data.")
