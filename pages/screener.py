import pandas as pd
import streamlit as st

from data import SCREENER_REGIONS, SCREENER_SECTORS, SCREENER_SORT_OPTIONS, screen_universe
from ui import C, open_stock_page, page_hero

page_hero(
    "Idea Flow",
    "Screener",
    "Sélectionne une région et un secteur — l'univers se construit automatiquement via Yahoo Finance."
)

# ── Filtres principaux ──────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

# Exclude separator labels from selectable options
selectable_regions = [k for k, v in SCREENER_REGIONS.items() if v is not None]
region_label = c1.selectbox("Région", selectable_regions, index=0)
sector_label = c2.selectbox("Secteur", list(SCREENER_SECTORS.keys()), index=0)
sort_label   = c3.selectbox("Trier par", list(SCREENER_SORT_OPTIONS.keys()), index=0)
size         = c4.selectbox("Résultats", [25, 50, 100, 200], index=1)

region_code  = SCREENER_REGIONS[region_label]
sector_code  = SCREENER_SECTORS[sector_label]
sort_field   = SCREENER_SORT_OPTIONS[sort_label]

# ── Filtres secondaires ─────────────────────────────────────────────
with st.expander("Filtres avancés", expanded=False):
    fa, fb, fc, fd = st.columns(4)
    pe_max         = fa.number_input("P/E Trailing max", min_value=0.0, value=100.0, step=5.0)
    market_cap_min = fb.number_input("Market Cap min ($B)", min_value=0.0, value=0.0, step=1.0)
    week52_min     = fc.number_input("Perf 52S min (%)", value=-100.0, step=5.0)
    change_min     = fd.number_input("Variation 1J min (%)", value=-100.0, step=0.5)

run = st.button("LANCER LE SCREENER", type="primary", width='stretch')

if not run and "screener_results" not in st.session_state:
    st.info("Configure les filtres puis clique sur LANCER LE SCREENER.")
    st.stop()

if run:
    with st.spinner(f"Chargement de l'univers — {region_label} · {sector_label}..."):
        quotes = screen_universe(region_code, sector_code, sort_field, size)
    st.session_state["screener_results"] = quotes
else:
    quotes = st.session_state.get("screener_results", [])

if not quotes:
    st.warning("Aucun résultat. Essaie d'élargir les filtres.")
    st.stop()

# ── Construction du DataFrame ───────────────────────────────────────
def fmt_cap(val):
    if not val:
        return "N/A"
    if val >= 1e12:
        return f"${val/1e12:.1f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    return f"${val/1e6:.0f}M"

rows = []
for q in quotes:
    price     = q.get("regularMarketPrice")
    chg_pct   = q.get("regularMarketChangePercent")
    mktcap    = q.get("marketCap")
    trailing_pe = q.get("trailingPE")
    forward_pe  = q.get("forwardPE")
    wk52_chg  = q.get("fiftyTwoWeekChangePercent")
    rating    = q.get("averageAnalystRating", "N/A")
    currency  = q.get("currency", "")

    rows.append({
        "Ticker":       q.get("symbol", ""),
        "Société":      q.get("shortName") or q.get("longName", ""),
        "Prix":         f"{price:.2f} {currency}" if price else "N/A",
        "1J%":          chg_pct,
        "Market Cap":   fmt_cap(mktcap),
        "P/E TTM":      round(trailing_pe, 1) if trailing_pe else None,
        "P/E Fwd":      round(forward_pe, 1) if forward_pe else None,
        "52S%":         round(wk52_chg * 100, 1) if wk52_chg else None,
        "Rating":       rating,
        # raw pour filtres
        "_mktcap_b":    (mktcap or 0) / 1e9,
        "_trailing_pe": trailing_pe,
        "_52s":         (wk52_chg or 0) * 100,
        "_1d":          chg_pct or 0,
    })

df = pd.DataFrame(rows)

# ── Application des filtres avancés ────────────────────────────────
df = df[
    (df["_mktcap_b"] >= market_cap_min) &
    (df["_trailing_pe"].fillna(10_000) <= pe_max) &
    (df["_52s"] >= week52_min) &
    (df["_1d"] >= change_min)
]

# ── Métriques résumé ────────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
m1.metric("Univers initial", len(quotes))
m2.metric("Après filtres", len(df))
positifs = int((df["_1d"] > 0).sum())
m3.metric("En hausse aujourd'hui", positifs)

st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

if df.empty:
    st.info("Aucun titre ne passe les filtres avancés.")
    st.stop()

# ── Affichage du tableau ────────────────────────────────────────────
display = df[["Ticker", "Société", "Prix", "1J%", "Market Cap", "P/E TTM", "P/E Fwd", "52S%", "Rating"]].copy()

def color_pct(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    color = "#00C896" if val > 0 else "#E8394A" if val < 0 else "#6B7FA0"
    return f"color: {color}; font-weight: 700"

def fmt_pct_col(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    return f"{val:+.1f}%"

display["1J%"]  = display["1J%"].apply(fmt_pct_col)
display["52S%"] = display["52S%"].apply(fmt_pct_col)
display["P/E TTM"] = display["P/E TTM"].apply(lambda v: f"{v:.1f}x" if pd.notna(v) and v else "N/A")
display["P/E Fwd"] = display["P/E Fwd"].apply(lambda v: f"{v:.1f}x" if pd.notna(v) and v else "N/A")

st.dataframe(
    display,
    width='stretch',
    hide_index=True,
    height=min(600, 35 * len(display) + 38),
)

# ── Ouverture dans Stock Analysis ───────────────────────────────────
st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
tickers_list = df["Ticker"].tolist()
selected = st.selectbox("Ouvrir dans Stock Analysis", tickers_list, label_visibility="collapsed")
if st.button(f"OUVRIR {selected}", width='stretch'):
    open_stock_page(selected)
