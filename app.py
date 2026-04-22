import streamlit as st

from ui import (
    HOME_PAGE,
    MARKET_PAGE,
    PAIR_PAGE,
    SCREENER_PAGE,
    STOCK_PAGE,
    WATCHLIST_PAGE,
    configure_app,
)


configure_app()

navigation = st.navigation(
    [
        st.Page(HOME_PAGE, title="Home", icon=":material/dashboard:"),
        st.Page(STOCK_PAGE, title="Stock Analysis", icon=":material/query_stats:"),
        st.Page(MARKET_PAGE, title="Market Overview", icon=":material/public:"),
        st.Page(SCREENER_PAGE, title="Screener", icon=":material/filter_alt:"),
        st.Page(PAIR_PAGE, title="Relative Performance", icon=":material/compare_arrows:"),
        st.Page(WATCHLIST_PAGE, title="Watchlist", icon=":material/star:"),
    ],
    position="sidebar",
    expanded=True,
)

navigation.run()
