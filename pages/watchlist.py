import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import load_watchlist, save_watchlist
from ui import C, WATCHLIST_PATH, build_snapshot_row, open_stock_page, page_hero, parse_ticker_list


page_hero(
    "Tracking",
    "Watchlist",
    f"Suivi local de tes tickers favoris, sauvegardé dans {WATCHLIST_PATH.name} pour retrouver rapidement tes dossiers."
)

current_watchlist = load_watchlist()
add_col, remove_col = st.columns(2)

with add_col:
    new_tickers_raw = st.text_input(
        "Ajouter des tickers",
        placeholder="ex: AAPL, MSFT, OR.PA",
    )
    if st.button("Ajouter à la watchlist", use_container_width=True):
        additions = parse_ticker_list(new_tickers_raw)
        updated = current_watchlist[:]
        for ticker in additions:
            if ticker not in updated:
                updated.append(ticker)
        save_watchlist(updated)
        st.rerun()

with remove_col:
    if current_watchlist:
        to_remove = st.multiselect("Retirer", current_watchlist)
        if st.button("Supprimer la sélection", use_container_width=True):
            save_watchlist([ticker for ticker in current_watchlist if ticker not in to_remove])
            st.rerun()

if not current_watchlist:
    st.info("La watchlist est vide pour l'instant.")
else:
    rows = []
    with st.spinner("Chargement de la watchlist..."):
        for ticker in current_watchlist:
            row = build_snapshot_row(ticker)
            if row:
                rows.append(row)

    if rows:
        df_watch = pd.DataFrame(rows).sort_values("1D Change (%)", ascending=False)
        display = df_watch[[
            "Ticker", "Name", "Price", "1D Change (%)", "Forward P/E",
            "Revenue Growth (%)", "Net Margin (%)", "Market Cap ($B)"
        ]].copy()
        display["Price"] = display["Price"].map(lambda v: f"${v:.2f}")
        display["1D Change (%)"] = display["1D Change (%)"].map(lambda v: f"{v:+.2f}%")
        display["Forward P/E"] = display["Forward P/E"].map(lambda v: f"{v:.1f}x" if pd.notna(v) else "N/A")
        display["Revenue Growth (%)"] = display["Revenue Growth (%)"].map(lambda v: f"{v:.1f}%")
        display["Net Margin (%)"] = display["Net Margin (%)"].map(lambda v: f"{v:.1f}%")
        display["Market Cap ($B)"] = display["Market Cap ($B)"].map(lambda v: f"${v:.1f}B" if pd.notna(v) else "N/A")
        st.dataframe(display, use_container_width=True, hide_index=True)

        focus = st.selectbox("Analyser un ticker de la watchlist", df_watch["Ticker"].tolist())
        if st.button("Ouvrir dans Stock Analysis", use_container_width=True):
            open_stock_page(focus)

        perf_series = pd.DataFrame(rows)[["Ticker", "1D Change (%)"]].sort_values("1D Change (%)")
        fig_watch = go.Figure(go.Bar(
            x=perf_series["1D Change (%)"],
            y=perf_series["Ticker"],
            orientation="h",
            marker_color=[C["red"] if x < 0 else C["green"] for x in perf_series["1D Change (%)"]],
            text=[f"{x:+.2f}%" for x in perf_series["1D Change (%)"]],
            textposition="outside",
        ))
        fig_watch.update_layout(
            plot_bgcolor=C["card"],
            paper_bgcolor=C["card"],
            font=dict(color=C["text"]),
            height=320,
            margin=dict(l=0, r=50, t=20, b=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_watch, use_container_width=True, config={"displayModeBar": False})
