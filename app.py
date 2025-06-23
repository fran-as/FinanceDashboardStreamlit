import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

st.set_page_config(layout="wide")

# Rutas
PORTFOLIO_PATH = os.path.join("Data", "CSyRacional.csv")
CACHE_PATH = os.path.join("Data", "cached_data.csv")

# Autorefresco cada 5 minutos (300000 ms)
st_autorefresh(interval=300000, limit=None, key="datarefresh")

# Función para colorear positivos y negativos
def highlight_positive_negative(val):
    if isinstance(val, (int, float)):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}'
    return ''

# Función de formato europeo segura
def format_eur_safe(x):
    try:
        return "{:,.2f}".format(float(x)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return x

# Cargar portafolio base y cache
if os.path.exists(PORTFOLIO_PATH) and os.path.exists(CACHE_PATH):
    df = pd.read_csv(PORTFOLIO_PATH)
    cache_df = pd.read_csv(CACHE_PATH)
    merged_df = pd.merge(df, cache_df, on='Symbol', how='left')

    # Cálculos dinámicos
    merged_df['Market Value'] = merged_df['Quantity'] * merged_df['Price']
    merged_df['Cost Basis'] = merged_df['Quantity'] * merged_df['Cost/Share']
    merged_df['Gain/Loss $'] = merged_df['Market Value'] - merged_df['Cost Basis']
    merged_df['Gain/Loss %'] = (merged_df['Gain/Loss $'] / merged_df['Cost Basis']) * 100
    merged_df['Day Change %'] = (merged_df['Price'] - merged_df['Previous Close']) / merged_df['Previous Close'] * 100
    merged_df['Day Change $'] = merged_df['Quantity'] * (merged_df['Price'] - merged_df['Previous Close'])

    total_market_value = merged_df['Market Value'].sum()
    total_cost_basis = merged_df['Cost Basis'].sum()
    total_gain_loss = merged_df['Gain/Loss $'].sum()
    total_gain_loss_pct = (total_gain_loss / total_cost_basis) * 100
    total_day_change = merged_df['Day Change $'].sum()
    total_day_change_pct = (total_day_change / (total_market_value - total_day_change)) * 100
    total_cash = 5109.34
    total_accounts_value = total_market_value + total_cash

    # Account summary
    st.markdown("## 💼 Account Summary")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Accounts Value", f"$ {total_accounts_value:,.2f}")
    col2.metric("Total Cash & Cash Invest", f"$ {total_cash:,.2f}")
    col3.metric("Total Market Value", f"$ {total_market_value:,.2f}")
    col4.metric("Total Day Change", f"$ {total_day_change:+,.2f}", f"{total_day_change_pct:+.2f}%")
    col5.metric("Total Cost Basis", f"$ {total_cost_basis:,.2f}")
    col6.metric("Total Gain/Loss", f"$ {total_gain_loss:+,.2f}", f"{total_gain_loss_pct:+.2f}%")

    # Equities - Position details
    st.markdown("## 📊 Equities - Position details")
    display_cols = ['Symbol', 'Description', 'Quantity', 'Cost/Share', 'Price', 'Previous Close',
                    'Day Change %', 'Day Change $', 'P/E', 'Market Value', 'Gain/Loss $', 'Gain/Loss %']
    styled_df = merged_df[display_cols].style.map(
        highlight_positive_negative,
        subset=['Day Change %', 'Day Change $', 'Gain/Loss $', 'Gain/Loss %']
    )
    numeric_cols = merged_df[display_cols].select_dtypes(include='number').columns
    st.dataframe(styled_df.format(format_eur_safe, subset=numeric_cols), use_container_width=True, hide_index=True)

    # Top 5 Holdings by Market Value
    st.markdown("### 🏆 Top 5 Holdings by Market Value")
    top5 = merged_df.sort_values(by='Market Value', ascending=False).head(5)
    top5_cols = ['Symbol', 'Description', 'Quantity', 'Price', 'Market Value', 'Cost Basis', 'Gain/Loss %']
    st.dataframe(top5.style.format(format_eur_safe, subset=top5[top5_cols].select_dtypes(include='number').columns),
                 use_container_width=True, hide_index=True)

    # Top 5 Performers
    st.markdown("### 📈 Top 5 Performers (Total Gain %)")
    top_perf = merged_df.sort_values(by='Gain/Loss %', ascending=False).head(5)
    top_perf_cols = ['Symbol', 'Description', 'Price', 'Gain/Loss %']
    st.dataframe(top_perf[top_perf_cols].style.format(format_eur_safe, subset=top_perf[top_perf_cols].select_dtypes(include='number').columns),
                 use_container_width=True, hide_index=True)

    # Bottom 5 Performers
    st.markdown("### 📉 Bottom 5 Performers (Total Gain %)")
    bottom_perf = merged_df.sort_values(by='Gain/Loss %').head(5)
    bottom_perf_cols = ['Symbol', 'Description', 'Price', 'Gain/Loss %']
    st.dataframe(bottom_perf[bottom_perf_cols].style.format(format_eur_safe, subset=bottom_perf[bottom_perf_cols].select_dtypes(include='number').columns),
                 use_container_width=True, hide_index=True)

    # Top 5 Gainers (Day)
    st.markdown("### 📈 Top 5 Gainers (Day Change %)")
    top_gainers = merged_df.sort_values(by='Day Change %', ascending=False).head(5)
    cols = ['Symbol', 'Description', 'Day Change %', 'Price']
    st.dataframe(top_gainers[cols].style.format(format_eur_safe, subset=top_gainers[cols].select_dtypes(include='number').columns),
                 use_container_width=True, hide_index=True)

    # Top 5 Losers (Day)
    st.markdown("### 📉 Top 5 Losers (Day Change %)")
    top_losers = merged_df.sort_values(by='Day Change %').head(5)
    st.dataframe(top_losers[cols].style.format(format_eur_safe, subset=top_losers[cols].select_dtypes(include='number').columns),
                 use_container_width=True, hide_index=True)

    # Pie Chart por sector
    st.markdown("### 📊 Exposure by Sector")
    sector_data = merged_df.groupby('Sector', as_index=False)['Market Value'].sum()
    fig = px.pie(sector_data, names='Sector', values='Market Value', title='Portfolio Exposure by Sector')
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("❗ Asegurate de tener CSyRacional.csv y cached_data.csv cargados.")
