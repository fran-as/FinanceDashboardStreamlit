import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dateutil.tz import tzlocal
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# --------- RUTAS ---------
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH     = os.path.join("Data", "cached_data.csv")

# --------- AUTOREFRESH CADA 5 MINUTOS ---------
# devuelve 0 la primera vez, >0 en cada recarga automática
refresh_count = st_autorefresh(interval=300_000, limit=None, key="datarefresh")

# --------- LIMPIAR CACHÉ EN AUTORELOAD O BOTÓN ---------
if refresh_count > 0 or st.button("🔄 Refrescar datos"):
    st.cache_data.clear()

# --------- HORA DE ÚLTIMA ACTUALIZACIÓN (JS en cliente) ---------
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

# --------- FUNCIONES AUXILIARES ---------
def highlight_positive_negative(val):
    if isinstance(val, (int, float)):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}'
    return ''

def format_eur_safe(x):
    try:
        return "{:,.2f}".format(float(x)) \
                 .replace(",", "X") \
                 .replace(".", ",") \
                 .replace("X", ".")
    except:
        return x

# --------- CARGA Y PROCESADO (cacheado según timestamp de archivos) ---------
@st.cache_data(show_spinner="Cargando datos del portafolio…")
def cargar_datos_y_procesar(portfolio_path, cache_path, p_mtime, c_mtime):
    df       = pd.read_csv(portfolio_path)
    cache_df = pd.read_csv(cache_path)
    merged   = pd.merge(df, cache_df, on='Symbol', how='left')

    merged['Market Value'] = merged['Quantity'] * merged['Price']
    merged['Cost Basis']    = merged['Quantity'] * merged['Cost/Share']
    merged['Gain/Loss $']   = merged['Market Value'] - merged['Cost Basis']
    merged['Gain/Loss %']   = (merged['Gain/Loss $'] / merged['Cost Basis']) * 100
    merged['Day Change %']  = (merged['Price'] - merged['Previous Close']) \
                              / merged['Previous Close'] * 100
    merged['Day Change $']  = merged['Quantity'] * \
                              (merged['Price'] - merged['Previous Close'])
    return merged

if os.path.exists(PORTFOLIO_PATH) and os.path.exists(CACHE_PATH):
    # pasar también las mtime para invalidar cache si cambian los CSV
    p_mtime = os.path.getmtime(PORTFOLIO_PATH)
    c_mtime = os.path.getmtime(CACHE_PATH)
    merged_df = cargar_datos_y_procesar(PORTFOLIO_PATH, CACHE_PATH, p_mtime, c_mtime)

    # Totales y métricas
    tmv  = merged_df['Market Value'].sum()
    tcb  = merged_df['Cost Basis'].sum()
    tgl  = merged_df['Gain/Loss $'].sum()
    tglp = (tgl / tcb * 100) if tcb else 0
    tdc  = merged_df['Day Change $'].sum()
    tdcp = (tdc / (tmv - tdc) * 100) if (tmv - tdc) else 0
    cash = 5109.34
    tav  = tmv + cash

    # 💼 Account Summary
    st.markdown("## 💼 Account Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Accounts Value",   f"$ {tav:,.2f}")
    c2.metric("Total Cash & Cash Invest", f"$ {cash:,.2f}")
    c3.metric("Total Market Value",     f"$ {tmv:,.2f}")
    c4.metric("Total Day Change",       f"$ {tdc:+,.2f}", f"{tdcp:+.2f}%")
    c5.metric("Total Cost Basis",       f"$ {tcb:,.2f}")
    c6.metric("Total Gain/Loss",        f"$ {tgl:+,.2f}", f"{tglp:+.2f}%")

    # 📊 Equities - Position details
    st.markdown("## 📊 Equities - Position details")
    cols = [
        'Symbol','Description','Quantity','Cost/Share','Price','Previous Close',
        'Day Change %','Day Change $','P/E','Market Value','Gain/Loss $','Gain/Loss %'
    ]
    styled = merged_df[cols].style.map(
        highlight_positive_negative,
        subset=['Day Change %','Day Change $','Gain/Loss $','Gain/Loss %']
    )
    num_cols = merged_df[cols].select_dtypes(include='number').columns
    st.dataframe(
        styled.format(format_eur_safe, subset=num_cols),
        use_container_width=True, hide_index=True
    )

    # 🏆 Top 5 Holdings by Market Value
    st.markdown("### 🏆 Top 5 Holdings by Market Value")
    top5 = merged_df.sort_values('Market Value', ascending=False).head(5)
    top5_cols = ['Symbol','Description','Quantity','Price','Market Value','Cost Basis','Gain/Loss %']
    st.dataframe(
        top5.style.format(format_eur_safe, subset=top5[top5_cols].select_dtypes(include='number').columns),
        use_container_width=True, hide_index=True
    )

    # 📈 Top 5 Performers (Total Gain %)
    st.markdown("### 📈 Top 5 Performers (Total Gain %)")
    tp = merged_df.sort_values('Gain/Loss %', ascending=False).head(5)
    st.dataframe(
        tp[['Symbol','Description','Price','Gain/Loss %']]
          .style.format(format_eur_safe, subset=['Price','Gain/Loss %']),
        use_container_width=True, hide_index=True
    )

    # 📉 Bottom 5 Performers (Total Gain %)
    st.markdown("### 📉 Bottom 5 Performers (Total Gain %)")
    bp = merged_df.sort_values('Gain/Loss %').head(5)
    st.dataframe(
        bp[['Symbol','Description','Price','Gain/Loss %']]
          .style.format(format_eur_safe, subset=['Price','Gain/Loss %']),
        use_container_width=True, hide_index=True
    )

    # 📈 Top 5 Gainers (Day Change %)
    st.markdown("### 📈 Top 5 Gainers (Day Change %)")
    tg = merged_df.sort_values('Day Change %', ascending=False).head(5)
    st.dataframe(
        tg[['Symbol','Description','Day Change %','Price']]
          .style.format(format_eur_safe, subset=['Day Change %','Price']),
        use_container_width=True, hide_index=True
    )

    # 📉 Top 5 Losers (Day Change %)
    st.markdown("### 📉 Top 5 Losers (Day Change %)")
    tl = merged_df.sort_values('Day Change %').head(5)
    st.dataframe(
        tl[['Symbol','Description','Day Change %','Price']]
          .style.format(format_eur_safe, subset=['Day Change %','Price']),
        use_container_width=True, hide_index=True
    )

    # 📊 Exposure by Sector (Pie Chart)
    st.markdown("### 📊 Exposure by Sector")
    sector_data = merged_df.groupby('Sector', as_index=False)['Market Value'].sum()
    fig = px.pie(sector_data, names='Sector', values='Market Value',
                 title='Portfolio Exposure by Sector')
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("❗ Asegurate de tener CSyRacional.csv y cached_data.csv en la carpeta Data.")
