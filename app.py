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
# refresh_count será 0 en la primera carga, >0 en cada recarga automática
refresh_count = st_autorefresh(interval=300_000, limit=None, key="datarefresh")

# --------- LIMPIAR CACHÉ EN AUTORELOAD O BOTÓN ---------
if refresh_count > 0 or st.button("🔄 Refrescar datos"):
    st.cache_data.clear()

# --------- HORA DE ÚLTIMA ACTUALIZACIÓN ---------
st.write("Última actualización:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

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
    except (ValueError, TypeError):
        return x

# --------- CARGA Y PROCESADO (cacheado) ---------
@st.cache_data(show_spinner="Cargando datos del portafolio…")
def cargar_datos_y_procesar(portfolio_path, cache_path):
    df       = pd.read_csv(portfolio_path)
    cache_df = pd.read_csv(cache_path)
    merged   = pd.merge(df, cache_df, on='Symbol', how='left')

    # Cálculos dinámicos
    merged['Market Value'] = merged['Quantity'] * merged['Price']
    merged['Cost Basis']    = merged['Quantity'] * merged['Cost/Share']
    merged['Gain/Loss $']   = merged['Market Value'] - merged['Cost Basis']
    merged['Gain/Loss %']   = (merged['Gain/Loss $'] / merged['Cost Basis']) * 100
    merged['Day Change %']  = (merged['Price'] - merged['Previous Close']) \
                              / merged['Previous Close'] * 100
    merged['Day Change $']  = merged['Quantity'] * \
                              (merged['Price'] - merged['Previous Close'])
    return merged

# --------- EJECUCIÓN DEL DASHBOARD ---------
if os.path.exists(PORTFOLIO_PATH) and os.path.exists(CACHE_PATH):
    merged_df = cargar_datos_y_procesar(PORTFOLIO_PATH, CACHE_PATH)

    # Totales y métricas
    total_market_value    = merged_df['Market Value'].sum()
    total_cost_basis      = merged_df['Cost Basis'].sum()
    total_gain_loss       = merged_df['Gain/Loss $'].sum()
    total_gain_loss_pct   = (total_gain_loss / total_cost_basis) * 100 if total_cost_basis else 0
    total_day_change      = merged_df['Day Change $'].sum()
    total_day_change_pct  = (total_day_change / (total_market_value - total_day_change)) * 100 \
                            if (total_market_value - total_day_change) else 0
    total_cash            = 5109.34
    total_accounts_value  = total_market_value + total_cash

    # 💼 Account Summary
    st.markdown("## 💼 Account Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Accounts Value",   f"$ {total_accounts_value:,.2f}")
    c2.metric("Total Cash & Cash Invest", f"$ {total_cash:,.2f}")
    c3.metric("Total Market Value",     f"$ {total_market_value:,.2f}")
    c4.metric("Total Day Change",       f"$ {total_day_change:+,.2f}", f"{total_day_change_pct:+.2f}%")
    c5.metric("Total Cost Basis",       f"$ {total_cost_basis:,.2f}")
    c6.metric("Total Gain/Loss",        f"$ {total_gain_loss:+,.2f}", f"{total_gain_loss_pct:+.2f}%")

    # 📊 Equities - Position details
    st.markdown("## 📊 Equities - Position details")
    display_cols = [
        'Symbol','Description','Quantity','Cost/Share','Price','Previous Close',
        'Day Change %','Day Change $','P/E','Market Value','Gain/Loss $','Gain/Loss %'
    ]
    styled = merged_df[display_cols].style.map(
        highlight_positive_negative,
        subset=['Day Change %','Day Change $','Gain/Loss $','Gain/Loss %']
    )
    num_cols = merged_df[display_cols].select_dtypes(include='number').columns
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
    top_perf = merged_df.sort_values('Gain/Loss %', ascending=False).head(5)
    st.dataframe(
        top_perf[['Symbol','Description','Price','Gain/Loss %']]
                .style.format(format_eur_safe, subset=['Price','Gain/Loss %']),
        use_container_width=True, hide_index=True
    )

    # 📉 Bottom 5 Performers (Total Gain %)
    st.markdown("### 📉 Bottom 5 Performers (Total Gain %)")
    bottom = merged_df.sort_values('Gain/Loss %').head(5)
    st.dataframe(
        bottom[['Symbol','Description','Price','Gain/Loss %']]
              .style.format(format_eur_safe, subset=['Price','Gain/Loss %']),
        use_container_width=True, hide_index=True
    )

    # 📈 Top 5 Gainers (Day Change %)
    st.markdown("### 📈 Top 5 Gainers (Day Change %)")
    gainers = merged_df.sort_values('Day Change %', ascending=False).head(5)
    st.dataframe(
        gainers[['Symbol','Description','Day Change %','Price']]
               .style.format(format_eur_safe, subset=['Day Change %','Price']),
        use_container_width=True, hide_index=True
    )

    # 📉 Top 5 Losers (Day Change %)
    st.markdown("### 📉 Top 5 Losers (Day Change %)")
    losers = merged_df.sort_values('Day Change %').head(5)
    st.dataframe(
        losers[['Symbol','Description','Day Change %','Price']]
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
