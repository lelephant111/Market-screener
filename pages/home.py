import streamlit as st

from ui import (
    MARKET_PAGE,
    PAIR_PAGE,
    SCREENER_PAGE,
    STOCK_PAGE,
    WATCHLIST_PAGE,
    open_page,
    open_stock_page,
)


st.title("Hedge Fund Tool")
st.caption("Choisis simplement l'outil à ouvrir.")

st.divider()

quick_ticker = st.text_input(
    "Ticker rapide",
    placeholder="ex: AAPL, MSFT, ASML",
    key="home_quick_ticker",
)

if st.button("Ouvrir Stock Analysis", use_container_width=True, type="primary"):
    open_stock_page(quick_ticker or "AAPL")

st.divider()

col1, col2 = st.columns(2)

if col1.button("Stock Analysis", use_container_width=True):
    open_page(STOCK_PAGE)

if col2.button("Market Overview", use_container_width=True):
    open_page(MARKET_PAGE)

if col1.button("Screener", use_container_width=True):
    open_page(SCREENER_PAGE)

if col2.button("Relative Performance", use_container_width=True):
    open_page(PAIR_PAGE)

if col1.button("Watchlist", use_container_width=True):
    open_page(WATCHLIST_PAGE)
