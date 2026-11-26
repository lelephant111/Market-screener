import pandas as pd
import streamlit as st

from charts import sector_bar_chart, yield_curve_chart
from data import MARKET_REGIONS, get_fear_greed_index, get_region_overview
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


def proxy_sentiment(vol_value, main, breadth):
    """Score de sentiment 0-100 maison : volatilité, tendance et momentum de l'indice principal, breadth."""
    parts = []
    if vol_value is not None:
        parts.append(85 if vol_value < 15 else 70 if vol_value < 18 else 55 if vol_value < 22 else 35 if vol_value < 28 else 15)
    if main.get("has_ma200"):
        parts.append(75 if main.get("above_ma200") else 25)
    if main.get("perf_1m") is not None:
        p = main["perf_1m"]
        parts.append(80 if p > 5 else 65 if p > 1 else 50 if p > -1 else 30 if p > -5 else 15)
    if breadth.get("pct_above_200") is not None:
        b = breadth["pct_above_200"]
        parts.append(85 if b >= 75 else 70 if b >= 60 else 50 if b >= 45 else 30 if b >= 30 else 15)
    if not parts:
        return {}
    score = round(sum(parts) / len(parts), 1)
    return {"score": score, "rating": score_to_rating(score), "source": "Proxy maison"}


def text_metric(col, label, value, delta=None):
    """Indicateur dont le sous-titre est un libellé (ex : "Fear") : pas de flèche ↑/↓ trompeuse."""
    try:
        col.metric(label, value, delta=delta, delta_color="off", delta_arrow="off")
    except TypeError:  # anciennes versions de Streamlit sans delta_arrow
        col.metric(label, value, delta=delta, delta_color="off")


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
    return "Bullish" if value > 0 else "Bearish" if value < 0 else "Neutral"


def pct(value):
    return fmt(value, "%", decimals=2) if value is not None else "N/A"


def signed_color(value):
    if value is None:
        return C["muted"]
    return C["green"] if value > 0 else C["red"]


page_hero(
    "Macro Tape",
    "Market Overview",
    "Lecture hiérarchisée du marché : régime, sentiment, volatilité, breadth, leadership, taux et rotation sectorielle."
)

region = st.selectbox("Marché", list(MARKET_REGIONS.keys()), index=0, key="market_region")

with st.spinner(f"Chargement du marché : {region}..."):
    ov = get_region_overview(region)

if not ov:
    st.warning(
        "Yahoo Finance ne répond pas pour le moment (limitation des requêtes depuis le serveur). "
        "Les indicateurs marché sont vides : réessaie dans quelques minutes."
    )
    st.stop()

indices = ov["indices"]
main_name = ov["main"]
main = indices.get(main_name, {})
breadth = ov["breadth"]
rates = ov["rates"]
cross = ov["cross"]

# Volatilité de référence : implicite (VIX) si disponible, sinon réalisée 20 jours de l'indice principal
if "VIX" in ov["implied_vol"]:
    vol_label, vol_value = "VIX", ov["implied_vol"]["VIX"]["value"]
    vol_delta = ov["implied_vol"]["VIX"].get("change_1d")
else:
    vol_label, vol_value, vol_delta = f"Vol. réalisée 20j ({main_name})", ov["realized_vol"], None

sentiment = (get_fear_greed_index() if region == "États-Unis" else {}) or proxy_sentiment(vol_value, main, breadth)

# ── 1. Indicateurs critiques ───────────────────────────────────────────
st.subheader("1. Indicateurs Critiques")
critical = st.columns(6)
text_metric(critical[0], "Sentiment", f"{sentiment.get('score', 'N/A')}", delta=sentiment.get("rating"))
if vol_delta is not None:
    critical[1].metric(vol_label, fmt(vol_value), delta=fmt(vol_delta, "%", decimals=2), delta_color="inverse")
else:
    text_metric(critical[1], vol_label, fmt(vol_value, "%", decimals=1) if vol_value is not None else "N/A")
text_metric(critical[2], f"{main_name} 1M", pct(main.get("perf_1m")), delta=trend_label(main) if main else None)
text_metric(
    critical[3],
    f"% {breadth.get('basis', '')} > 200D",
    fmt_pct(breadth.get("pct_above_200"), already_pct=True) if breadth.get("pct_above_200") is not None else "N/A",
    delta=f"{breadth.get('advancers', 0)} up / {breadth.get('decliners', 0)} down" if breadth else None,
)
lead = ov["leadership"][0] if ov["leadership"] else None
text_metric(
    critical[4],
    lead["label"] if lead else "Leadership",
    pct(lead["spread"]) if lead else "N/A",
    delta=f"{lead['leader']} mène" if lead else None,
)
if rates.get("10Y") is not None and rates.get("3M") is not None:
    curve = rates["10Y"] - rates["3M"]
    text_metric(critical[5], "10Y - 3M", pct(curve), delta="Pente positive" if curve > 0 else "Inversion")
elif ov["headline_cross"] and ov["headline_cross"] in cross:
    hc = cross[ov["headline_cross"]]
    text_metric(critical[5], f"{ov['headline_cross']} 1M", pct(hc.get("perf_1m")), delta=fmt(hc["value"], decimals=4))

st.divider()

left, right = st.columns([1.15, 0.85])

with left:
    # ── 2. Indices ─────────────────────────────────────────────────────
    st.subheader("2. Indices")
    rows = [
        {
            "Indice": name,
            "Niveau": round(row["value"], 2),
            "1D %": round(row["change_1d"], 2) if row.get("change_1d") is not None else None,
            "1M %": round(row["perf_1m"], 2) if row.get("perf_1m") is not None else None,
            "3M %": round(row["perf_3m"], 2) if row.get("perf_3m") is not None else None,
            "Tendance": trend_label(row),
            "BBP": bbp_label(row.get("bbp")),
        }
        for name, row in indices.items()
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # ── 3. Breadth & leadership ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("3. Breadth & Leadership")
    basis = breadth.get("basis", "")
    breadth_rows = [
        (f"% {basis} > 50D", fmt_pct(breadth.get("pct_above_50"), already_pct=True) if breadth else "N/A",
         C["green"] if breadth.get("pct_above_50", 0) >= 60 else C["orange"] if breadth.get("pct_above_50", 0) >= 40 else C["red"]),
        (f"% {basis} > 200D", fmt_pct(breadth.get("pct_above_200"), already_pct=True) if breadth.get("pct_above_200") is not None else "N/A",
         C["green"] if (breadth.get("pct_above_200") or 0) >= 60 else C["orange"] if (breadth.get("pct_above_200") or 0) >= 40 else C["red"]),
        ("Hausse / Baisse (1J)", f"{breadth.get('advancers', 0)} / {breadth.get('decliners', 0)}" if breadth else "N/A", C["text"]),
    ]
    for item in ov["leadership"]:
        breadth_rows.append((item["label"], pct(item["spread"]), signed_color(item["spread"])))
    st.markdown(card("Market Internals", table(breadth_rows)), unsafe_allow_html=True)

with right:
    # ── Volatilité & sentiment ─────────────────────────────────────────
    st.subheader("Volatilité & Sentiment")
    sentiment_rows = [
        ("Sentiment", f"{sentiment.get('score', 'N/A')} / 100",
         C["green"] if (sentiment.get("score") or 50) >= 55 else C["red"] if (sentiment.get("score") or 50) <= 45 else C["orange"]),
        ("Régime", sentiment.get("rating", "N/A"), C["text"]),
        ("Source", sentiment.get("source", "N/A"), C["muted"]),
    ]
    for name, stats in ov["implied_vol"].items():
        sentiment_rows.append((name, fmt(stats["value"]), C["red"] if stats["value"] >= 22 else C["green"]))
    if "VIX" in ov["implied_vol"] and "VIX 3M" in ov["implied_vol"]:
        term = ov["implied_vol"]["VIX"]["value"] / ov["implied_vol"]["VIX 3M"]["value"]
        sentiment_rows.append(("VIX / VIX3M", fmt(term), C["red"] if term > 1 else C["green"]))
    sentiment_rows.append((f"Vol. réalisée 20j ({main_name})", fmt(ov["realized_vol"], "%", decimals=1) if ov["realized_vol"] is not None else "N/A", C["muted"]))
    st.markdown(card("Priority Signals", table(sentiment_rows)), unsafe_allow_html=True)

    # ── 4. Taux & intermarket ──────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("4. Taux & Intermarket")
    macro_rows = []
    if rates:
        for name in ("10Y", "3M"):
            if name in rates:
                macro_rows.append((f"Taux {name}", pct(rates[name]), C["text"]))
        if "10Y" in rates and "3M" in rates:
            macro_rows.append(("10Y - 3M", pct(rates["10Y"] - rates["3M"]), signed_color(rates["10Y"] - rates["3M"])))
        if "30Y" in rates and "5Y" in rates:
            macro_rows.append(("30Y - 5Y", pct(rates["30Y"] - rates["5Y"]), signed_color(rates["30Y"] - rates["5Y"])))
    for name, stats in cross.items():
        macro_rows.append((f"{name} ({fmt(stats['value'], decimals=4 if '/' in name else 2)}) 1M", pct(stats.get("perf_1m")), signed_color(stats.get("perf_1m"))))
    st.markdown(card("Taux / Changes / Matières premières", table(macro_rows)), unsafe_allow_html=True)
    if not rates:
        st.caption("Taux souverains non disponibles sur Yahoo pour cette zone.")

# ── 5. Rotation sectorielle ────────────────────────────────────────────
if ov["sectors"]:
    st.divider()
    st.subheader("5. Rotation Sectorielle")
    horizon = st.radio("Horizon", ["1J", "1M", "3M"], index=1, horizontal=True, key="sector_horizon")
    field = {"1J": "change_1d", "1M": "perf_1m", "3M": "perf_3m"}[horizon]
    perf = {name: round(stats[field], 2) for name, stats in ov["sectors"].items() if stats.get(field) is not None}
    if perf:
        st.plotly_chart(sector_bar_chart(perf), width="stretch", config={"displayModeBar": False})
        st.caption(ov["sectors_label"])
    else:
        st.caption("Données sectorielles non disponibles.")

# ── 6. Courbe des taux ─────────────────────────────────────────────────
if len(rates) >= 2:
    st.divider()
    st.subheader("6. Courbe des Taux US")
    st.plotly_chart(yield_curve_chart(rates), width="stretch", config={"displayModeBar": False})
