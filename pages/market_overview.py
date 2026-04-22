import pandas as pd
import streamlit as st

from charts import sector_bar_chart, yield_curve_chart
from data import (
    get_fear_greed_index,
    get_market_breadth,
    get_market_snapshot,
    get_sector_performance,
    get_yield_curve,
)
from ui import C, card, page_hero, table
from utils import fmt, fmt_pct


def score_to_rating(score):
    if score is None:
        return "N/A"
    if score >= 75:
        return "Extreme Greed"
    if score >= 55:
        return "Greed"
    if score >= 45:
        return "Neutral"
    if score >= 25:
        return "Fear"
    return "Extreme Fear"


def proxy_fear_greed(snapshot, breadth):
    parts = []

    vix = snapshot.get("VIX", {})
    vix_value = vix.get("value")
    if vix_value is not None:
        parts.append(85 if vix_value < 15 else 70 if vix_value < 18 else 55 if vix_value < 22 else 35 if vix_value < 28 else 15)

    spy = snapshot.get("S&P 500", {})
    if spy.get("above_ma200") is not None:
        parts.append(75 if spy.get("above_ma200") else 25)
    if spy.get("perf_1m") is not None:
        parts.append(80 if spy["perf_1m"] > 5 else 65 if spy["perf_1m"] > 1 else 50 if spy["perf_1m"] > -1 else 30 if spy["perf_1m"] > -5 else 15)

    pct_above_200 = breadth.get("pct_above_200")
    if pct_above_200 is not None:
        parts.append(85 if pct_above_200 >= 75 else 70 if pct_above_200 >= 60 else 50 if pct_above_200 >= 45 else 30 if pct_above_200 >= 30 else 15)

    if not parts:
        return {}

    score = round(sum(parts) / len(parts), 1)
    return {"score": score, "rating": score_to_rating(score), "source": "Proxy"}


def trend_label(row):
    if row.get("above_ma50") and row.get("above_ma200"):
        return "Strong Uptrend"
    if row.get("above_ma200"):
        return "Above 200D"
    if row.get("above_ma50"):
        return "Above 50D"
    return "Weak Trend"


def bbp_label(value):
    if value is None:
        return "N/A"
    if value > 0:
        return "Bullish"
    if value < 0:
        return "Bearish"
    return "Neutral"


page_hero(
    "Macro Tape",
    "Market Overview",
    "Lecture hiérarchisée du marché: régime global, sentiment, volatilité, breadth, leadership et taux."
)

with st.spinner("Chargement du cockpit marché..."):
    snapshot = get_market_snapshot()
    breadth = get_market_breadth()
    sector_perf = get_sector_performance()
    yield_data = get_yield_curve()
    fear_greed = get_fear_greed_index() or proxy_fear_greed(snapshot, breadth)

spy = snapshot.get("S&P 500", {})
qqq = snapshot.get("Nasdaq 100", {})
iwm = snapshot.get("Russell 2000", {})
vix = snapshot.get("VIX", {})
vix3m = snapshot.get("VIX 3M", {})

qqq_lead = None
if qqq.get("perf_1m") is not None and spy.get("perf_1m") is not None:
    qqq_lead = qqq["perf_1m"] - spy["perf_1m"]

iwm_lead = None
if iwm.get("perf_1m") is not None and spy.get("perf_1m") is not None:
    iwm_lead = iwm["perf_1m"] - spy["perf_1m"]

vix_term = None
if vix.get("value") not in (None, 0) and vix3m.get("value") not in (None, 0):
    vix_term = vix["value"] / vix3m["value"]

curve_3m_10y = None
if yield_data.get("3M") is not None and yield_data.get("10Y") is not None:
    curve_3m_10y = yield_data["10Y"] - yield_data["3M"]

curve_5y_30y = None
if yield_data.get("5Y") is not None and yield_data.get("30Y") is not None:
    curve_5y_30y = yield_data["30Y"] - yield_data["5Y"]

st.subheader("1. Indicateurs Critiques")
critical = st.columns(6)
critical[0].metric(
    "Fear & Greed",
    f"{fear_greed.get('score', 'N/A')}",
    delta=fear_greed.get("rating", "N/A"),
    delta_color="off",
)
critical[1].metric(
    "VIX",
    fmt(vix.get("value")),
    delta=fmt(vix.get("change_1d"), "%", decimals=2) if vix.get("change_1d") is not None else None,
    delta_color="inverse",
)
critical[2].metric(
    "S&P 500 1M",
    fmt(spy.get("perf_1m"), "%", decimals=2) if spy.get("perf_1m") is not None else "N/A",
    delta=trend_label(spy) if spy else None,
    delta_color="off",
)
critical[3].metric(
    "% > 200D",
    fmt_pct(breadth.get("pct_above_200"), already_pct=True) if breadth else "N/A",
    delta=f"{breadth.get('advancers', 0)} up / {breadth.get('decliners', 0)} down" if breadth else None,
    delta_color="off",
)
critical[4].metric(
    "QQQ vs SPY (1M)",
    fmt(qqq_lead, "%", decimals=2) if qqq_lead is not None else "N/A",
    delta="Growth leadership" if qqq_lead is not None and qqq_lead > 0 else "Broad market leads" if qqq_lead is not None else None,
    delta_color="off",
)
critical[5].metric(
    "10Y - 3M",
    fmt(curve_3m_10y, "%", decimals=2) if curve_3m_10y is not None else "N/A",
    delta="Steepening" if curve_3m_10y is not None and curve_3m_10y > 0 else "Inversion" if curve_3m_10y is not None else None,
    delta_color="off",
)

st.divider()

left, right = st.columns([1.15, 0.85])

with left:
    st.subheader("2. Indices Directeurs")
    core_names = ["S&P 500", "Nasdaq 100", "Dow Jones", "Russell 2000"]
    core_rows = []
    for name in core_names:
        row = snapshot.get(name)
        if not row:
            continue
        core_rows.append(
            {
                "Index": name,
                "Last": round(row["value"], 2),
                "1D %": round(row["change_1d"], 2) if row.get("change_1d") is not None else None,
                "1M %": round(row["perf_1m"], 2) if row.get("perf_1m") is not None else None,
                "3M %": round(row["perf_3m"], 2) if row.get("perf_3m") is not None else None,
                "Trend": trend_label(row),
                "BBP": round(row["bbp"], 2) if row.get("bbp") is not None else None,
                "BBP Signal": bbp_label(row.get("bbp")),
            }
        )
    if core_rows:
        st.dataframe(pd.DataFrame(core_rows), width='stretch', hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("3. Breadth & Leadership")
    breadth_rows = [
        ("Breadth > 50D", fmt_pct(breadth.get("pct_above_50"), already_pct=True) if breadth else "N/A", C["green"] if breadth and breadth.get("pct_above_50", 0) >= 60 else C["orange"] if breadth and breadth.get("pct_above_50", 0) >= 40 else C["red"]),
        ("Breadth > 200D", fmt_pct(breadth.get("pct_above_200"), already_pct=True) if breadth else "N/A", C["green"] if breadth and breadth.get("pct_above_200", 0) >= 60 else C["orange"] if breadth and breadth.get("pct_above_200", 0) >= 40 else C["red"]),
        ("Advance / Decline", f"{breadth.get('advancers', 0)} / {breadth.get('decliners', 0)}" if breadth else "N/A", C["text"]),
        ("Net A/D", str(breadth.get("advance_decline")) if breadth else "N/A", C["green"] if breadth and breadth.get("advance_decline", 0) > 0 else C["red"]),
        ("QQQ vs SPY (1M)", fmt(qqq_lead, "%", decimals=2) if qqq_lead is not None else "N/A", C["green"] if qqq_lead is not None and qqq_lead > 0 else C["red"] if qqq_lead is not None else C["muted"]),
        ("IWM vs SPY (1M)", fmt(iwm_lead, "%", decimals=2) if iwm_lead is not None else "N/A", C["green"] if iwm_lead is not None and iwm_lead > 0 else C["red"] if iwm_lead is not None else C["muted"]),
    ]
    st.markdown(card("Market Internals", table(breadth_rows)), unsafe_allow_html=True)

    if breadth and breadth.get("trend_table"):
        st.dataframe(pd.DataFrame(breadth["trend_table"]), width='stretch', hide_index=True)

with right:
    st.subheader("Volatilité & Sentiment")
    sentiment_rows = [
        ("Fear & Greed", f"{fear_greed.get('score', 'N/A')} / 100", C["green"] if fear_greed.get("score", 50) >= 55 else C["red"] if fear_greed.get("score", 50) <= 45 else C["orange"]),
        ("Regime", fear_greed.get("rating", "N/A"), C["text"]),
        ("Source", fear_greed.get("source", "N/A"), C["muted"]),
        ("VIX", fmt(vix.get("value")), C["red"] if vix.get("value", 0) >= 22 else C["green"]),
        ("VIX 3M", fmt(vix3m.get("value")), C["muted"]),
        ("VIX / VIX3M", fmt(vix_term), C["red"] if vix_term is not None and vix_term > 1 else C["green"] if vix_term is not None else C["muted"]),
    ]
    st.markdown(card("Priority Signals", table(sentiment_rows)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("4. Taux & Intermarket")
    macro_rows = [
        ("10Y Treasury", fmt(yield_data.get("10Y"), "%", decimals=2) if yield_data else "N/A", C["text"]),
        ("3M Treasury", fmt(yield_data.get("3M"), "%", decimals=2) if yield_data else "N/A", C["text"]),
        ("10Y - 3M", fmt(curve_3m_10y, "%", decimals=2) if curve_3m_10y is not None else "N/A", C["green"] if curve_3m_10y is not None and curve_3m_10y > 0 else C["red"] if curve_3m_10y is not None else C["muted"]),
        ("30Y - 5Y", fmt(curve_5y_30y, "%", decimals=2) if curve_5y_30y is not None else "N/A", C["green"] if curve_5y_30y is not None and curve_5y_30y > 0 else C["muted"]),
        ("Gold 1M", fmt(snapshot.get("Gold", {}).get("perf_1m"), "%", decimals=2) if snapshot.get("Gold") else "N/A", C["orange"]),
        ("US Dollar 1M", fmt(snapshot.get("US Dollar", {}).get("perf_1m"), "%", decimals=2) if snapshot.get("US Dollar") else "N/A", C["blue"]),
    ]
    st.markdown(card("Rates / Dollar / Gold", table(macro_rows)), unsafe_allow_html=True)

st.divider()

st.subheader("5. Rotation Sectorielle")
if sector_perf:
    fig = sector_bar_chart(sector_perf)
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
else:
    st.caption("Données sectorielles non disponibles.")

st.divider()

st.subheader("6. Courbe des Taux US")
if yield_data:
    fig2 = yield_curve_chart(yield_data)
    st.plotly_chart(fig2, width='stretch', config={"displayModeBar": False})
else:
    st.caption("Courbe des taux non disponible.")
