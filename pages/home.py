import streamlit as st

from ui import (
    MARKET_PAGE,
    PAIR_PAGE,
    SCREENER_PAGE,
    STOCK_PAGE,
    WATCHLIST_PAGE,
    open_page,
    open_stock_page,
    C,
)

st.markdown(
    f"""
    <div style="padding: 2rem 0 1.5rem 0;">
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.25em;
                    color:{C['orange']};text-transform:uppercase;margin-bottom:0.5rem;">
            MARKET TERMINAL
        </div>
        <div style="font-size:2rem;font-weight:700;color:{C['text']};
                    letter-spacing:-0.02em;line-height:1.1;">
            Hedge Fund Tool
        </div>
        <div style="font-size:0.82rem;color:{C['muted']};margin-top:0.4rem;
                    letter-spacing:0.02em;">
            Analyse actions · Marchés · Screener · Watchlist
        </div>
    </div>
    <hr style="border-color:{C['border']};margin:0 0 1.5rem 0;" />
    """,
    unsafe_allow_html=True,
)

col_input, col_btn = st.columns([4, 1])
with col_input:
    quick_ticker = st.text_input(
        "Ticker",
        placeholder="Entrer un ticker  —  ex: AAPL, MSFT, ASML",
        key="home_quick_ticker",
        label_visibility="collapsed",
    )
with col_btn:
    if st.button("ANALYSER →", width='stretch', type="primary"):
        open_stock_page(quick_ticker or "AAPL")

st.markdown("<div style='margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)

TOOLS = [
    {
        "icon": "◈",
        "title": "STOCK ANALYSIS",
        "desc": "Valorisation · Fondamentaux · Technique · Analystes",
        "page": STOCK_PAGE,
    },
    {
        "icon": "◉",
        "title": "MARKET OVERVIEW",
        "desc": "Indices · VIX · Breadth · Taux · Rotation sectorielle",
        "page": MARKET_PAGE,
    },
    {
        "icon": "◫",
        "title": "SCREENER",
        "desc": "Filtrage multi-critères · Scatter · Accès rapide",
        "page": SCREENER_PAGE,
    },
    {
        "icon": "⇌",
        "title": "RELATIVE PERFORMANCE",
        "desc": "Comparaison base 100 · Ratio · Z-score",
        "page": PAIR_PAGE,
    },
    {
        "icon": "◷",
        "title": "WATCHLIST",
        "desc": "Suivi personnalisé · Prix · Variation journalière",
        "page": WATCHLIST_PAGE,
    },
]

cols = st.columns(3)
for i, tool in enumerate(TOOLS):
    col = cols[i % 3]
    with col:
        st.markdown(
            f"""
            <div style="background:{C['card']};border:1px solid {C['border']};
                        border-top:2px solid {C['orange']};border-radius:4px;
                        padding:18px 18px 10px 18px;margin-bottom:0.5rem;">
                <div style="font-size:1.4rem;color:{C['orange']};margin-bottom:8px;">
                    {tool['icon']}
                </div>
                <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.18em;
                            color:{C['text']};text-transform:uppercase;margin-bottom:6px;">
                    {tool['title']}
                </div>
                <div style="font-size:0.75rem;color:{C['muted']};line-height:1.45;">
                    {tool['desc']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"OUVRIR", key=f"nav_{i}", width='stretch'):
            open_page(tool["page"])
