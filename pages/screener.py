import pandas as pd
import streamlit as st

from charts import screener_scatter_chart
from ui import build_snapshot_row, open_stock_page, page_hero, parse_ticker_list


page_hero(
    "Idea Flow",
    "Screener",
    "Filtre rapidement un univers de tickers avec quelques critères simples, puis ouvre directement les idées qui remontent."
)

default_universe = "AAPL, MSFT, NVDA, AMZN, GOOGL, META, ASML, TSM, JPM, V"
universe_raw = st.text_area(
    "Univers de tickers",
    value=default_universe,
    help="Sépare les tickers par des virgules.",
    height=110,
)
universe = parse_ticker_list(universe_raw)

f1, f2, f3, f4 = st.columns(4)
pe_max = f1.number_input("Forward P/E max", min_value=0.0, value=30.0, step=1.0)
revenue_growth_min = f2.number_input("Revenue growth min (%)", value=0.0, step=1.0)
de_max = f3.number_input("Debt / Equity max", min_value=0.0, value=150.0, step=5.0)
market_cap_min = f4.number_input("Market Cap min ($B)", min_value=0.0, value=10.0, step=1.0)

rows = []
invalid = []
with st.spinner("Construction du screener..."):
    for ticker in universe:
        row = build_snapshot_row(ticker)
        if row:
            rows.append(row)
        else:
            invalid.append(ticker)

if not rows:
    st.warning("Aucun ticker exploitable dans l'univers actuel.")
else:
    df_screen = pd.DataFrame(rows)
    filtered = df_screen[
        (df_screen["Forward P/E"].fillna(10_000) <= pe_max)
        & (df_screen["Revenue Growth (%)"].fillna(-10_000) >= revenue_growth_min)
        & (df_screen["Debt / Equity"].fillna(10_000) <= de_max)
        & (df_screen["Market Cap ($B)"].fillna(0) >= market_cap_min)
    ].copy()

    filtered = filtered.sort_values(["Revenue Growth (%)", "1D Change (%)"], ascending=[False, False])

    c1, c2, c3 = st.columns(3)
    c1.metric("Univers", len(df_screen))
    c2.metric("Résultats", len(filtered))
    c3.metric("Tickers exclus", len(invalid))

    if invalid:
        st.caption(f"Tickers ignorés : {', '.join(invalid)}")

    if filtered.empty:
        st.info("Aucun résultat ne passe les filtres actuels.")
    else:
        display = filtered.drop(columns=["Bubble Size"]).copy()
        display["Price"] = display["Price"].map(lambda v: f"${v:.2f}")
        display["1D Change (%)"] = display["1D Change (%)"].map(lambda v: f"{v:+.2f}%")
        display["Forward P/E"] = display["Forward P/E"].map(lambda v: f"{v:.1f}x" if pd.notna(v) else "N/A")
        display["Revenue Growth (%)"] = display["Revenue Growth (%)"].map(lambda v: f"{v:.1f}%")
        display["Net Margin (%)"] = display["Net Margin (%)"].map(lambda v: f"{v:.1f}%")
        display["Debt / Equity"] = display["Debt / Equity"].map(lambda v: f"{v:.0f}" if pd.notna(v) else "N/A")
        display["Market Cap ($B)"] = display["Market Cap ($B)"].map(lambda v: f"${v:.1f}B" if pd.notna(v) else "N/A")

        st.dataframe(display, use_container_width=True, hide_index=True)

        if len(filtered) >= 2:
            fig_screen = screener_scatter_chart(filtered)
            st.plotly_chart(fig_screen, use_container_width=True, config={"displayModeBar": False})

        selected = st.selectbox("Ouvrir un ticker dans Stock Analysis", filtered["Ticker"].tolist())
        if st.button("Ouvrir ce ticker", use_container_width=True):
            open_stock_page(selected)
