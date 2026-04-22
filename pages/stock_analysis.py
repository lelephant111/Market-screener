import pandas as pd
import streamlit as st

from charts import (
    analyst_bar_chart,
    earnings_chart,
    profitability_chart,
    scorecard_chart,
    technical_chart,
)
from data import (
    compute_indicators,
    get_analyst_recommendations,
    get_calendar,
    get_earnings_history,
    get_insider_transactions,
    get_stock_history,
    get_stock_info,
    search_tickers,
)
from ui import C, card, page_hero, table, val_color
from utils import compute_scores, compute_zacks_ratings, fmt, fmt_large, fmt_pct


page_hero(
    "Single Name",
    "Stock Analysis",
    "Recherche une société puis lis ses multiples, sa qualité, ses earnings, le consensus analystes et ses signaux techniques dans une vue unique."
)


def first_timestamp(value):
    if value is None:
        return None
    candidates = value if isinstance(value, (list, tuple)) else [value]
    for candidate in candidates:
        try:
            ts = pd.Timestamp(candidate)
            if pd.notna(ts):
                return ts
        except Exception:
            continue
    return None


def first_scalar(value):
    if isinstance(value, dict):
        for nested in value.values():
            scalar = first_scalar(nested)
            if scalar is not None:
                return scalar
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            scalar = first_scalar(item)
            if scalar is not None:
                return scalar
        return None
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


incoming_ticker = st.session_state.pop("selected_ticker", None)
if incoming_ticker:
    st.session_state["stock_search_query"] = incoming_ticker
    st.session_state.pop("stock_ticker_select", None)

if "stock_search_query" not in st.session_state:
    st.session_state["stock_search_query"] = ""

search_query = st.text_input(
    "Rechercher une entreprise ou un ticker",
    placeholder="ex: Apple, AAPL, Nvidia, BNP Paribas...",
    key="stock_search_query",
)

ticker_input = ""
if search_query and len(search_query.strip()) >= 2:
    results = search_tickers(search_query)
    if results:
        options = [f"{r['symbol']} — {r['name']}" for r in results]
        exact_symbol = search_query.upper().strip()
        default_index = next(
            (i for i, result in enumerate(results) if result["symbol"].upper() == exact_symbol),
            0,
        )
        chosen = st.selectbox(
            "Sélectionner",
            options,
            label_visibility="collapsed",
            index=default_index,
            key="stock_ticker_select",
        )
        ticker_input = chosen.split(" — ")[0].strip()
    else:
        ticker_input = search_query.upper().strip()
        st.caption(f"Aucune suggestion, chargement direct de `{ticker_input}`.")

if not ticker_input:
    st.info("Tapez le nom d'une entreprise ou son symbole boursier pour commencer.")
    st.stop()

with st.spinner(f"Chargement de {ticker_input}..."):
    try:
        info = get_stock_info(ticker_input)
    except Exception:
        info = {}

current_price = info.get("currentPrice") or info.get("regularMarketPrice")
if not current_price:
    if len(info) < 5:
        st.error(
            f"Impossible de récupérer les données pour **{ticker_input}**. "
            "Yahoo Finance est peut-être temporairement indisponible. Réessaie dans quelques secondes."
        )
    else:
        st.error(f"Prix introuvable pour **{ticker_input}**. Vérifie le symbole (ex: `AAPL`, `MC.PA`).")
    st.stop()

prev_close = info.get("previousClose", current_price)
price_change = current_price - prev_close
price_change_pct = (price_change / prev_close) * 100 if prev_close else 0

col_name, col_price = st.columns([3, 1])
with col_name:
    st.subheader(info.get("longName", ticker_input))
    st.caption(
        f"**{info.get('exchange', 'N/A')}** · "
        f"{info.get('sector', 'N/A')} · "
        f"{info.get('industry', 'N/A')}"
    )
with col_price:
    st.metric(
        "Prix actuel",
        f"${current_price:.2f}",
        delta=f"{price_change:+.2f} ({price_change_pct:+.2f}%)",
    )

st.divider()

with st.spinner("Calcul des ratings..."):
    earnings_h_zacks = get_earnings_history(ticker_input)
    hist_z = get_stock_history(ticker_input, "1y")
    df_z = compute_indicators(hist_z) if not hist_z.empty else None
    zacks = compute_zacks_ratings(info, df_z, earnings_h_zacks)


def _to_grade_color(score):
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


GRADE_COLOR = {"A": "#3fb950", "B": "#7ee787", "C": "#d29922", "D": "#e07046", "F": "#f85149"}
GRADE_LABEL = {"A": "Strong", "B": "Good", "C": "Neutral", "D": "Weak", "F": "Very Weak"}


def grade_cell(data, size="24px"):
    grade = data["grade"]
    return (
        f'<span style="font-size:{size};font-weight:800;color:{GRADE_COLOR[grade]};line-height:1;">{grade}</span>'
        f'<span style="font-size:10px;color:{GRADE_COLOR[grade]};opacity:0.7;margin-left:6px;">'
        f'{GRADE_LABEL[grade]}</span>'
    )


def score_bar(score, width=60):
    fill = GRADE_COLOR[_to_grade_color(score)]
    return (
        f'<div style="display:inline-flex;align-items:center;gap:6px;">'
        f'<div style="width:{width}px;height:4px;background:#21262d;border-radius:2px;">'
        f'<div style="width:{score}%;height:4px;background:{fill};border-radius:2px;"></div>'
        f'</div>'
        f'<span style="font-size:11px;color:#8b949e;">{score}</span>'
        f"</div>"
    )


_, zcol, _ = st.columns([1, 2, 1])
with zcol:
    rows = ""
    for label, key in [("Value", "value"), ("Growth", "growth"), ("Momentum", "momentum")]:
        data = zacks[key]
        rows += (
            f'<tr style="border-bottom:1px solid #21262d;">'
            f'<td style="padding:11px 0;color:#8b949e;font-size:13px;width:40%;">{label}</td>'
            f'<td style="padding:11px 0;width:35%;">{grade_cell(data)}</td>'
            f'<td style="padding:11px 0;text-align:right;">{score_bar(data["score"])}</td>'
            f"</tr>"
        )
    vgm = zacks["vgm"]
    rows += (
        f'<tr style="border-top:1px solid #30363d;">'
        f'<td style="padding:14px 0;color:#e6edf3;font-size:14px;font-weight:600;">VGM Score</td>'
        f'<td style="padding:14px 0;">{grade_cell(vgm, size="28px")}</td>'
        f'<td style="padding:14px 0;text-align:right;">{score_bar(vgm["score"])}</td>'
        f"</tr>"
    )
    st.markdown(
        f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;padding:20px 28px;">'
        f'<p style="font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#555;margin:0 0 4px 0;'
        f'text-align:center;">Zacks-Style Ratings</p>'
        f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

with st.spinner("Calcul des scores..."):
    history_score = get_stock_history(ticker_input, "1y")
    df_score = compute_indicators(history_score) if not history_score.empty else None
    scores = compute_scores(info, df_score)

fig_sc = scorecard_chart(scores)
st.plotly_chart(fig_sc, use_container_width=True, config={"displayModeBar": False})
st.divider()

col_a, col_b = st.columns(2)
pe = info.get("trailingPE")
fpe = info.get("forwardPE")
eveb = info.get("enterpriseToEbitda")
peg = info.get("pegRatio")
ps = info.get("priceToSalesTrailing12Months")
div_yield = info.get("dividendYield")

with col_a:
    st.markdown(card("Valorisation", table([
        ("P/E (TTM)", fmt(pe, "x"), val_color(pe, True, (15, 25, 35))),
        ("Forward P/E", fmt(fpe, "x"), val_color(fpe, True, (15, 22, 30))),
        ("EV/EBITDA", fmt(eveb, "x"), val_color(eveb, True, (10, 18, 25))),
        ("PEG Ratio", fmt(peg), val_color(peg, True, (1, 1.5, 2))),
        ("P/S Ratio", fmt(ps, "x"), val_color(ps, True, (2, 5, 10))),
        ("Dividend Yield", f"{div_yield * 100:.2f}%" if div_yield else "N/A", C["muted"]),
    ])), unsafe_allow_html=True)

with col_b:
    pb = info.get("priceToBook")
    st.markdown(card("Taille & Structure", table([
        ("Market Cap", fmt_large(info.get("marketCap")), C["text"]),
        ("Enterprise Value", fmt_large(info.get("enterpriseValue")), C["text"]),
        ("Revenue (TTM)", fmt_large(info.get("totalRevenue")), C["text"]),
        ("EBITDA", fmt_large(info.get("ebitda")), C["text"]),
        ("Free Cash Flow", fmt_large(info.get("freeCashflow")), C["green"] if (info.get("freeCashflow") or 0) > 0 else C["red"]),
        ("P/B Ratio", fmt(pb, "x"), val_color(pb, True, (1, 3, 5))),
    ])), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col_c, col_d = st.columns(2)
gm = info.get("grossMargins")
om = info.get("operatingMargins")
nm = info.get("profitMargins")
roe = info.get("returnOnEquity")
roa = info.get("returnOnAssets")

with col_c:
    st.markdown(card("Profitabilité", ""), unsafe_allow_html=True)
    fig_m = profitability_chart(gm, om, nm, roe, roa)
    st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

with col_d:
    rev_g = info.get("revenueGrowth")
    earn_g = info.get("earningsGrowth")
    st.markdown(card("Croissance & P&L", table([
        ("Revenue Growth (YoY)", fmt_pct(rev_g), val_color(rev_g or 0, False, (0, 0.1, 0.2))),
        ("Earnings Growth (YoY)", fmt_pct(earn_g), val_color(earn_g or 0, False, (0, 0.1, 0.2))),
        ("Gross Margin", fmt_pct(gm), val_color(gm or 0, False, (0, 0.25, 0.5))),
        ("Operating Margin", fmt_pct(om), val_color(om or 0, False, (0, 0.1, 0.2))),
        ("Net Margin", fmt_pct(nm), val_color(nm or 0, False, (0, 0.05, 0.15))),
    ])), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col_e, col_f = st.columns(2)
with col_e:
    de = info.get("debtToEquity")
    cr = info.get("currentRatio")
    qr = info.get("quickRatio")
    cash = info.get("totalCash")
    debt = info.get("totalDebt")
    st.markdown(card("Santé Financière", table([
        ("Debt / Equity", fmt(de, "%", decimals=0), val_color(de or 0, True, (30, 80, 150))),
        ("Current Ratio", fmt(cr), val_color(cr or 0, False, (0, 1, 1.5))),
        ("Quick Ratio", fmt(qr), val_color(qr or 0, False, (0, 0.8, 1.2))),
        ("Cash & Équivalents", fmt_large(cash), C["green"] if cash else C["muted"]),
        ("Total Debt", fmt_large(debt), C["red"] if debt else C["muted"]),
    ])), unsafe_allow_html=True)

with col_f:
    short_float = info.get("shortPercentOfFloat")
    short_ratio = info.get("shortRatio")
    beta = info.get("beta")
    high_52w = info.get("fiftyTwoWeekHigh")
    low_52w = info.get("fiftyTwoWeekLow")
    pct_52w = None
    if high_52w and low_52w and high_52w != low_52w:
        pct_52w = (current_price - low_52w) / (high_52w - low_52w) * 100

    st.markdown(card("Positionnement", table([
        ("Short % of Float", f"{short_float * 100:.1f}%" if short_float else "N/A", val_color(short_float or 0, True, (0.05, 0.10, 0.20))),
        ("Short Ratio", fmt(short_ratio, " days", decimals=1), C["muted"]),
        ("Beta (1Y)", fmt(beta), C["orange"] if beta and beta > 1.5 else C["text"]),
        ("52w High", f"${high_52w:.2f}" if high_52w else "N/A", C["muted"]),
        ("52w Low", f"${low_52w:.2f}" if low_52w else "N/A", C["muted"]),
        ("Position 52w", f"{pct_52w:.0f}%" if pct_52w else "N/A", val_color(pct_52w or 0, False, (0, 30, 60))),
    ])), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.subheader("Earnings & Estimations")
with st.spinner("Chargement des earnings..."):
    calendar = get_calendar(ticker_input)
    earnings_h = get_earnings_history(ticker_input)

ec1, ec2, ec3, ec4 = st.columns(4)
next_date = None
try:
    next_date = first_timestamp(calendar.get("Earnings Date"))
except Exception:
    pass

days_to = None
if next_date:
    days_to = (next_date.date() - pd.Timestamp.today().date()).days

ec1.metric(
    "Prochain Earnings",
    next_date.strftime("%d %b %Y") if next_date else "N/A",
    delta=(
        f"dans {days_to}j" if days_to is not None and days_to >= 0
        else "passé" if days_to is not None and days_to < 0
        else None
    ),
    delta_color="off",
)

t_eps = info.get("trailingEps")
f_eps = info.get("forwardEps")
ec2.metric("EPS (TTM)", f"${t_eps:.2f}" if t_eps else "N/A")
ec3.metric("EPS Forward", f"${f_eps:.2f}" if f_eps else "N/A")
rev_est = calendar.get("Revenue Average") or calendar.get("Revenue Estimate")
rev_est = first_scalar(rev_est)
ec4.metric("Rev. Estimate", fmt_large(rev_est) if rev_est is not None else "N/A")

if earnings_h is not None and not earnings_h.empty:
    needed = ["epsActual", "epsEstimate"]
    if all(c in earnings_h.columns for c in needed):
        fig_earn = earnings_chart(earnings_h)
        st.plotly_chart(fig_earn, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Données earnings insuffisantes pour afficher le graphique.")
else:
    st.caption("Historique earnings non disponible.")

st.divider()

st.subheader("Consensus Analystes")
with st.spinner("Chargement des recommandations..."):
    reco_df = get_analyst_recommendations(ticker_input)

col_reco, col_targets = st.columns([3, 2])
with col_reco:
    strong_buy = buy_c = hold_c = sell_c = strong_sell = 0
    reco_label = str(info.get("recommendationKey") or "N/A").upper()

    if reco_df is not None and not reco_df.empty:
        if "period" in reco_df.columns:
            row = reco_df[reco_df["period"] == "0m"]
            if row.empty:
                row = reco_df.iloc[[0]]
        else:
            row = reco_df.iloc[[0]]

        r = row.iloc[0]
        strong_buy = int(r.get("strongBuy", 0) or 0)
        buy_c = int(r.get("buy", 0) or 0)
        hold_c = int(r.get("hold", 0) or 0)
        sell_c = int(r.get("sell", 0) or 0)
        strong_sell = int(r.get("strongSell", 0) or 0)
        total = strong_buy + buy_c + hold_c + sell_c + strong_sell

        n_analysts = info.get("numberOfAnalystOpinions", total)
        st.markdown(
            f'<p style="font-size:13px;color:{C["muted"]};margin:0 0 8px 0;">'
            f'Consensus sur <b style="color:{C["text"]}">{n_analysts} analystes</b> — '
            f'<b style="color:{C["blue"]}">{reco_label}</b></p>',
            unsafe_allow_html=True,
        )
        fig_reco = analyst_bar_chart(strong_buy, buy_c, hold_c, sell_c, strong_sell)
        st.plotly_chart(fig_reco, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Données de recommandations non disponibles.")

with col_targets:
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHighPrice")
    target_low = info.get("targetLowPrice")
    upside = ((target_mean - current_price) / current_price * 100) if target_mean else None

    st.markdown(card("Prix Cibles", table([
        ("Prix actuel", f"${current_price:.2f}", C["text"]),
        ("Cible moyenne", f"${target_mean:.2f}" if target_mean else "N/A", C["green"] if upside and upside > 0 else C["red"] if upside else C["muted"]),
        ("Upside / Downside", f"{upside:+.1f}%" if upside is not None else "N/A", C["green"] if upside and upside > 0 else C["red"] if upside else C["muted"]),
        ("Cible haute", f"${target_high:.2f}" if target_high else "N/A", C["muted"]),
        ("Cible basse", f"${target_low:.2f}" if target_low else "N/A", C["muted"]),
    ])), unsafe_allow_html=True)

st.divider()

st.subheader("Transactions Insiders")
with st.spinner("Chargement des transactions insiders..."):
    insiders_df = get_insider_transactions(ticker_input)

if insiders_df is not None and not insiders_df.empty:
    df_ins = insiders_df.copy()
    tx_col = next((c for c in df_ins.columns if "trans" in c.lower()), None)
    shares_col = next((c for c in df_ins.columns if "share" in c.lower()), None)

    net_signal = None
    if tx_col and shares_col:
        try:
            df_ins["_date"] = pd.to_datetime(df_ins.index, errors="coerce")
            three_months_ago = pd.Timestamp.today() - pd.DateOffset(months=3)
            recent = df_ins[df_ins["_date"] >= three_months_ago]
            if not recent.empty:
                buys = recent[recent[tx_col].str.contains("Buy|Purchase", case=False, na=False)][shares_col].sum()
                sales = recent[recent[tx_col].str.contains("Sale|Sell", case=False, na=False)][shares_col].sum()
                net_signal = "Net Buyer" if buys > sales else "Net Seller"
        except Exception:
            pass

    if net_signal:
        signal_color = C["green"] if net_signal == "Net Buyer" else C["red"]
        signal_bg = "#0a2010" if net_signal == "Net Buyer" else "#200508"
        st.markdown(
            f'<div style="display:inline-block;background:{signal_bg};border:1px solid {signal_color};'
            f'border-radius:6px;padding:6px 16px;margin-bottom:12px;">'
            f'<span style="color:{signal_color};font-weight:600;font-size:13px;">'
            f'{"▲" if net_signal == "Net Buyer" else "▼"} {net_signal} (3 mois)</span></div>',
            unsafe_allow_html=True,
        )

    display_cols = {}
    col_map = {
        "Insider": ["Insider", "insider", "Name"],
        "Position": ["Position", "position", "Title"],
        "Transaction": ["Transaction", "transaction", "Type"],
        "Shares": ["Shares", "shares"],
        "Value": ["Value", "value"],
    }
    for friendly, candidates in col_map.items():
        found = next((c for c in candidates if c in df_ins.columns), None)
        if found:
            display_cols[found] = friendly

    if display_cols:
        show = df_ins[list(display_cols.keys())].rename(columns=display_cols).head(8)
        if "Value" in show.columns:
            show["Value"] = show["Value"].apply(lambda v: fmt_large(v) if isinstance(v, (int, float)) else v)
        st.dataframe(show, use_container_width=True, hide_index=False)
    else:
        st.dataframe(df_ins.head(8), use_container_width=True)
else:
    st.caption("Données insiders non disponibles.")

st.subheader("Analyse Technique")
period = st.selectbox("Période", ["3mo", "6mo", "1y", "2y", "5y"], index=2)

with st.spinner("Chargement du graphique..."):
    history = get_stock_history(ticker_input, period)

if not history.empty:
    df_ta = compute_indicators(history)
    last_close = df_ta["Close"].iloc[-1]
    ma200 = df_ta["MA200"].dropna()
    rsi_val = df_ta["RSI"].dropna()
    macd_val = df_ta["MACD"].iloc[-1]
    macd_sig = df_ta["MACD_signal"].iloc[-1]
    bb_upper = df_ta["BB_upper"].iloc[-1]
    bb_lower = df_ta["BB_lower"].iloc[-1]

    def signal_badge(label, value, color):
        bg = "#1a3a1a" if color == "green" else "#3a1a1a" if color == "red" else "#1a1a2e"
        border = "#00c853" if color == "green" else "#ff1744" if color == "red" else "#555"
        return (
            f'<div style="border:1px solid {border}; background:{bg}; border-radius:8px; padding:8px 14px; text-align:center;">'
            f'<div style="font-size:11px; color:#aeb8c5;">{label}</div>'
            f'<div style="font-size:14px; font-weight:bold; color:{border};">{value}</div>'
            f"</div>"
        )

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        if len(ma200) > 0:
            above = last_close > ma200.iloc[-1]
            st.markdown(signal_badge("MA200", "Au-dessus ▲" if above else "En-dessous ▼", "green" if above else "red"), unsafe_allow_html=True)

    with s2:
        if len(rsi_val) > 0:
            rsi = rsi_val.iloc[-1]
            if rsi > 70:
                st.markdown(signal_badge("RSI", f"{rsi:.0f} — Suracheté", "red"), unsafe_allow_html=True)
            elif rsi < 30:
                st.markdown(signal_badge("RSI", f"{rsi:.0f} — Survendu", "green"), unsafe_allow_html=True)
            else:
                st.markdown(signal_badge("RSI", f"{rsi:.0f} — Neutre", "neutral"), unsafe_allow_html=True)

    with s3:
        bullish_macd = macd_val > macd_sig
        st.markdown(signal_badge("MACD", "Haussier ▲" if bullish_macd else "Baissier ▼", "green" if bullish_macd else "red"), unsafe_allow_html=True)

    with s4:
        if last_close > bb_upper:
            st.markdown(signal_badge("Bollinger", "Hors bande haute", "red"), unsafe_allow_html=True)
        elif last_close < bb_lower:
            st.markdown(signal_badge("Bollinger", "Hors bande basse", "green"), unsafe_allow_html=True)
        else:
            st.markdown(signal_badge("Bollinger", "Dans les bandes", "neutral"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    fig = technical_chart(df_ta, ticker_input)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.divider()
