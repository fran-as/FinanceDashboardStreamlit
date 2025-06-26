import streamlit as st
import pandas as pd
import yfinance as yf
import os
import matplotlib.pyplot as plt
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# Rutas
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH     = os.path.join("Data", "cached_data.csv")

# Autorefresh cada 5 minutos
refresh_count = st_autorefresh(interval=300_000, limit=None, key="datarefresh")

# Botón de recarga manual
if refresh_count > 0 or st.button("🔄 Refrescar datos"):
    st.cache_data.clear()

# Mostrar hora local del cliente
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

# Auxiliares
def highlight_positive_negative(val):
    if isinstance(val, (int, float)):
        return f"color: {'green' if val>0 else 'red' if val<0 else 'black'}"
    return ""

def format_eur_safe(x):
    try:
        return "{:,.2f}".format(float(x)).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return x

# Fetch dinámico desde Yahoo
@st.cache_data(show_spinner="📡 Obteniendo precios de Yahoo…")
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

# Carga estática y merge
@st.cache_data(show_spinner="📥 Cargando datos estáticos…")
def load_static(portfolio_path, cache_path):
    p_df = pd.read_csv(portfolio_path)          # Symbol, Description, Quantity, Cost/Share, Sector…
    c_df = pd.read_csv(cache_path).drop(columns=["Price","Previous Close"], errors="ignore")
    return pd.merge(p_df, c_df, on="Symbol", how="left")

# Ejecución
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

    # Totales
    tmv  = df["Market Value"].sum()
    tcb  = df["Cost Basis"].sum()
    tgl  = df["Gain/Loss $"].sum()
    tglp = (tgl / tcb * 100) if tcb else 0
    tdc  = df["Day Change $"].sum()
    tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
    cash = 5109.34
    tav  = tmv + cash

    # Account Summary
    st.markdown("## 💼 Account Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Accounts Value",   f"$ {tav:,.2f}")
    c2.metric("Total Cash & Cash Invest", f"$ {cash:,.2f}")
    c3.metric("Total Market Value",     f"$ {tmv:,.2f}")
    c4.metric("Total Day Change",       f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
    c5.metric("Total Cost Basis",       f"$ {tcb:,.2f}")
    c6.metric("Total Gain/Loss",        f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

    # Position details
    st.markdown("## 📊 Equities - Position details")
    display = ["Symbol","Description","Quantity","Cost/Share","Price","Previous Close",
               "Day Change %","Day Change $","P/E","Market Value","Gain/Loss $","Gain/Loss %"]
    styled = df[display].style.map(highlight_positive_negative,
                                   subset=["Day Change %","Day Change $","Gain/Loss $","Gain/Loss %"])
    nums   = df[display].select_dtypes("number").columns
    st.dataframe(styled.format(format_eur_safe, subset=nums),
                 use_container_width=True, hide_index=True)

    # Top 5 por Market Value
    st.markdown("### 🏆 Top 5 Holdings by Market Value")
    top5 = df.nlargest(5, "Market Value")
    cols = ["Symbol","Description","Quantity","Price","Market Value","Cost Basis","Gain/Loss %"]
    st.dataframe(top5[cols].style.format(format_eur_safe,
                 subset=top5[cols].select_dtypes("number").columns),
                 use_container_width=True, hide_index=True)

    # Pie Chart por Sector
    st.markdown("### 📊 Exposure by Sector")
    sector_sum = df.groupby("Sector", as_index=False)["Market Value"].sum()
    fig, ax = plt.subplots()
    ax.pie(sector_sum["Market Value"], labels=sector_sum["Sector"], autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)

else:
    st.warning("❗ Asegúrate de tener ambos CSV en la carpeta Data.")
