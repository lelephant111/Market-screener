import pandas as pd
import streamlit as st

from charts import relative_performance_chart
from data import get_stock_history
from ui import page_hero


page_hero(
    "Pair View",
    "Relative Performance",
    "Compare deux actions sur une base 100 et observe le ratio de prix pour repérer les écarts relatifs."
)

p1, p2, p3 = st.columns([1, 1, 1])
ticker_a = p1.text_input("Ticker A", value="MSFT").upper().strip()
ticker_b = p2.text_input("Ticker B", value="AAPL").upper().strip()
pair_period = p3.selectbox("Période", ["3mo", "6mo", "1y", "2y", "5y"], index=2)

if ticker_a and ticker_b:
    with st.spinner("Chargement de la comparaison..."):
        hist_a = get_stock_history(ticker_a, pair_period)
        hist_b = get_stock_history(ticker_b, pair_period)

    if hist_a.empty or hist_b.empty:
        st.error("Impossible de charger l'un des deux historiques.")
    else:
        fig_pair = relative_performance_chart(hist_a, hist_b, ticker_a, ticker_b)
        st.plotly_chart(fig_pair, width='stretch', config={"displayModeBar": False})

        merged = pd.concat(
            [hist_a["Close"].rename(ticker_a), hist_b["Close"].rename(ticker_b)],
            axis=1
        ).dropna()
        if merged.empty or len(merged) < 2:
            st.warning("Pas assez de points communs entre les deux historiques pour calculer un ratio fiable.")
            st.stop()
        ratio = merged[ticker_a] / merged[ticker_b]
        ratio_std = ratio.std()
        zscore = ((ratio.iloc[-1] - ratio.mean()) / ratio_std) if pd.notna(ratio_std) and ratio_std != 0 else 0
        perf_a = (merged[ticker_a].iloc[-1] / merged[ticker_a].iloc[0] - 1) * 100
        perf_b = (merged[ticker_b].iloc[-1] / merged[ticker_b].iloc[0] - 1) * 100

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric(f"Perf {ticker_a}", f"{perf_a:+.1f}%")
        rc2.metric(f"Perf {ticker_b}", f"{perf_b:+.1f}%")
        rc3.metric("Z-score du ratio", f"{zscore:+.2f}")

        signal = "Écart large vs moyenne" if abs(zscore) >= 2 else "Zone neutre"
        st.caption(f"Lecture rapide : {signal}. Ratio actuel {ticker_a}/{ticker_b} = {ratio.iloc[-1]:.3f}")
