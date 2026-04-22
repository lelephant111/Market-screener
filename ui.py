from pathlib import Path

import streamlit as st

from data import get_stock_info


C = {
    "green": "#35d399",
    "orange": "#fbbf24",
    "red": "#fb7185",
    "blue": "#7dd3fc",
    "text": "#e6eef8",
    "muted": "#8fa6c1",
    "border": "#21324a",
    "card": "#0d1726",
    "row": "#142238",
    "bg": "#07111f",
    "panel": "#111d31",
}

WATCHLIST_PATH = Path(__file__).with_name("watchlist.json")

HOME_PAGE = "pages/home.py"
STOCK_PAGE = "pages/stock_analysis.py"
MARKET_PAGE = "pages/market_overview.py"
SCREENER_PAGE = "pages/screener.py"
PAIR_PAGE = "pages/relative_performance.py"
WATCHLIST_PAGE = "pages/watchlist.py"


def configure_app() -> None:
    st.set_page_config(
        page_title="Hedge Fund Tool",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #07111f;
            --bg-soft: #0b1422;
            --panel: #0d1726;
            --panel-2: #111d31;
            --line: #21324a;
            --line-soft: rgba(143, 166, 193, 0.14);
            --line-strong: rgba(125, 211, 252, 0.24);
            --text: #e6eef8;
            --muted: #8fa6c1;
            --blue: #7dd3fc;
            --blue-strong: #4f8cff;
            --green: #35d399;
            --red: #fb7185;
            --orange: #fbbf24;
            --shadow: 0 18px 40px rgba(3, 8, 20, 0.28);
        }

        html, body {
            color-scheme: dark;
        }

        #MainMenu, footer {
            visibility: hidden;
        }

        [data-testid="stDecoration"] {
            display: none;
        }

        html, body, [class*="css"] {
            font-family: "Avenir Next", "SF Pro Display", "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 12% 8%, rgba(125, 211, 252, 0.15), transparent 24%),
                radial-gradient(circle at 88% 14%, rgba(53, 211, 153, 0.10), transparent 18%),
                radial-gradient(circle at 50% 100%, rgba(79, 140, 255, 0.10), transparent 28%),
                linear-gradient(180deg, #07111f 0%, #091321 50%, #07101c 100%);
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] {
            background: transparent !important;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
            visibility: visible !important;
            height: 0 !important;
        }

        [data-testid="stToolbar"] {
            right: 1rem;
        }

        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            z-index: 1000 !important;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(7, 17, 31, 0.97) 0%, rgba(10, 21, 38, 0.98) 100%) !important;
            border-right: 1px solid var(--line) !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            background: transparent !important;
        }

        [data-testid="stSidebarNav"] {
            padding-top: 1rem;
        }

        [data-testid="stSidebarNav"]::before {
            content: "Hedge Fund Tool";
            display: block;
            padding: 0 0.35rem 0.9rem 0.35rem;
            color: var(--text);
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: -0.03em;
        }

        [data-testid="stSidebarNav"] ul {
            gap: 0.35rem;
        }

        [data-testid="stSidebarNav"] li {
            margin: 0.05rem 0;
        }

        [data-testid="stSidebarNav"] a {
            background: rgba(17, 29, 49, 0.72);
            border: 1px solid var(--line-soft);
            border-radius: 14px;
            transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease;
        }

        [data-testid="stSidebarNav"] a:hover {
            background: rgba(17, 29, 49, 0.92);
            border-color: var(--line-strong);
            transform: translateX(2px);
        }

        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: linear-gradient(135deg, rgba(125, 211, 252, 0.16) 0%, rgba(79, 140, 255, 0.18) 100%);
            border-color: rgba(125, 211, 252, 0.28);
        }

        [data-testid="stSidebarNav"] span {
            color: var(--text) !important;
            font-weight: 600;
        }

        .block-container {
            max-width: 1460px;
            padding-top: 1.4rem !important;
            padding-bottom: 2.2rem !important;
        }

        h1 {
            font-size: 2.1rem !important;
            font-weight: 700 !important;
            color: var(--text) !important;
            letter-spacing: -0.05em !important;
            margin: 0 !important;
            padding-bottom: 0 !important;
        }

        h2, h3 {
            font-size: 0.77rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.16em !important;
            color: var(--muted) !important;
        }

        .stApp p, .stApp li, .stApp label, .stApp td, .stApp th {
            color: var(--text);
        }

        .stCaption,
        [data-testid="stCaptionContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
            color: var(--muted) !important;
        }

        .page-hero {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(125, 211, 252, 0.14) 0%, rgba(17, 29, 49, 0.94) 32%, rgba(13, 23, 38, 0.98) 100%);
            border: 1px solid rgba(125, 211, 252, 0.18);
            border-radius: 26px;
            padding: 1.2rem 1.35rem 1.1rem 1.35rem;
            margin: 0 0 1.15rem 0;
            box-shadow: var(--shadow);
        }

        .page-hero::after {
            content: "";
            position: absolute;
            inset: auto -40px -60px auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(53, 211, 153, 0.18) 0%, rgba(53, 211, 153, 0) 72%);
            pointer-events: none;
        }

        .page-hero__kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: var(--blue);
            margin-bottom: 0.35rem;
        }

        .page-hero p {
            max-width: 760px;
            margin: 0.35rem 0 0 0;
            color: rgba(230, 238, 248, 0.78) !important;
            font-size: 0.98rem;
            line-height: 1.55;
        }

        [data-testid="metric-container"] {
            background: linear-gradient(180deg, rgba(13, 23, 38, 0.92) 0%, rgba(17, 29, 49, 0.96) 100%);
            border: 1px solid var(--line-soft);
            border-radius: 18px;
            padding: 16px 18px !important;
            box-shadow: var(--shadow);
        }

        [data-testid="stMetricLabel"] {
            font-size: 11px !important;
            color: var(--muted) !important;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
            font-weight: 700 !important;
            color: var(--text) !important;
        }

        hr {
            border-color: rgba(143, 166, 193, 0.12) !important;
            margin: 1.15rem 0 !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: rgba(13, 23, 38, 0.96) !important;
            border: 1px solid var(--line) !important;
            border-radius: 14px !important;
            color: var(--text) !important;
            min-height: 46px;
            box-shadow: none !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: rgba(143, 166, 193, 0.65) !important;
        }

        div[data-baseweb="select"] * {
            color: var(--text) !important;
        }

        div[role="listbox"] {
            background: #0d1726 !important;
            border: 1px solid var(--line) !important;
            border-radius: 14px !important;
            box-shadow: var(--shadow) !important;
        }

        div[role="option"] {
            color: var(--text) !important;
        }

        div[role="option"]:hover {
            background: rgba(125, 211, 252, 0.10) !important;
        }

        .stButton > button,
        [data-testid="stBaseButton-secondary"] {
            background: linear-gradient(135deg, rgba(125, 211, 252, 0.22) 0%, rgba(79, 140, 255, 0.30) 100%);
            color: var(--text);
            border: 1px solid rgba(125, 211, 252, 0.22);
            border-radius: 14px;
            min-height: 44px;
            padding: 0.55rem 1rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            box-shadow: 0 12px 26px rgba(8, 19, 33, 0.28);
            transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
        }

        .stButton > button:hover,
        [data-testid="stBaseButton-secondary"]:hover {
            border-color: rgba(125, 211, 252, 0.44);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 16px 30px rgba(10, 22, 40, 0.34);
        }

        [data-testid="stPageLink"] a {
            background: rgba(17, 29, 49, 0.72);
            border: 1px solid var(--line-soft);
            border-radius: 14px;
            padding: 0.72rem 0.9rem;
        }

        [data-testid="stPageLink"] a:hover {
            border-color: var(--line-strong);
            background: rgba(17, 29, 49, 0.92);
        }

        [data-testid="stPageLink"] p {
            color: var(--text) !important;
            font-weight: 600;
        }

        [data-testid="stDataFrame"],
        [data-testid="stPlotlyChart"] {
            background: linear-gradient(180deg, rgba(13, 23, 38, 0.88) 0%, rgba(17, 29, 49, 0.92) 100%);
            border: 1px solid var(--line-soft);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 16px 34px rgba(3, 8, 20, 0.22);
            padding: 0.25rem;
        }

        [data-testid="stDataFrame"] * {
            color: var(--text) !important;
        }

        [data-testid="stAlert"] {
            background: rgba(17, 29, 49, 0.76);
            border: 1px solid var(--line-soft);
            border-radius: 16px;
        }

        [data-testid="stMarkdownContainer"] a {
            color: var(--blue);
            text-decoration: none;
        }

        [data-testid="stMarkdownContainer"] a:hover {
            color: white;
        }

        @media (max-width: 900px) {
            .page-hero {
                padding: 1rem 1rem 0.95rem 1rem;
                border-radius: 22px;
            }

            h1 {
                font-size: 1.7rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_hero(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <section class="page-hero">
            <div class="page-hero__kicker">{kicker}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body_html: str) -> str:
    title_html = (
        f'<p style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;'
        f'color:{C["muted"]};margin:0 0 12px 0;font-weight:600;">{title}</p>'
        if title else ""
    )
    return (
        f'<div style="background:linear-gradient(180deg, {C["card"]} 0%, {C["panel"]} 100%);'
        f'border:1px solid {C["border"]};border-radius:18px;padding:18px 20px;'
        f'box-shadow:0 18px 40px rgba(3,8,20,0.28);">'
        + title_html + body_html + "</div>"
    )


def table(rows: list) -> str:
    rows_html = "".join(
        f'<tr style="border-bottom:1px solid {C["row"]};">'
        f'<td style="color:{C["muted"]};padding:8px 4px;font-size:13px;">{row[0]}</td>'
        f'<td style="text-align:right;color:{row[2] if len(row) > 2 else C["text"]};'
        f'padding:8px 4px;font-size:13px;font-weight:600;">{row[1]}</td></tr>'
        for row in rows
    )
    return f'<table style="width:100%;border-collapse:collapse;">{rows_html}</table>'


def val_color(val, low_good: bool = True, thresholds=(10, 20, 30)):
    if val is None or (isinstance(val, float) and val != val):
        return C["muted"]
    t1, t2, t3 = thresholds
    if low_good:
        return C["green"] if val < t1 else C["orange"] if val < t2 else C["red"]
    return C["green"] if val > t3 else C["orange"] if val > t2 else C["red"]


def parse_ticker_list(raw: str) -> list:
    seen = []
    for item in raw.split(","):
        ticker = item.upper().strip()
        if ticker and ticker not in seen:
            seen.append(ticker)
    return seen


def build_snapshot_row(ticker: str):
    info = get_stock_info(ticker)
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not current_price:
        return None

    previous_close = info.get("previousClose") or current_price
    change_pct = ((current_price - previous_close) / previous_close * 100) if previous_close else 0

    market_cap = info.get("marketCap")
    bubble_size = max(14, min(40, ((market_cap or 0) / 1e11) + 14))

    return {
        "Ticker": ticker,
        "Name": info.get("longName", ticker),
        "Price": round(current_price, 2),
        "1D Change (%)": round(change_pct, 2),
        "Forward P/E": info.get("forwardPE"),
        "Revenue Growth (%)": (info.get("revenueGrowth") or 0) * 100,
        "Net Margin (%)": (info.get("profitMargins") or 0) * 100,
        "Debt / Equity": info.get("debtToEquity"),
        "Market Cap ($B)": round((market_cap or 0) / 1e9, 2) if market_cap else None,
        "Bubble Size": bubble_size,
    }


def open_page(page_path: str, **state) -> None:
    for key, value in state.items():
        st.session_state[key] = value
    st.switch_page(page_path)


def open_stock_page(ticker: str) -> None:
    value = ticker.upper().strip()
    if not value:
        return
    open_page(STOCK_PAGE, selected_ticker=value)
