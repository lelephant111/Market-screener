from pathlib import Path

import streamlit as st

from data import get_stock_info


C = {
    "green": "#00C896",
    "orange": "#FF6600",
    "red": "#E8394A",
    "blue": "#4A9EFF",
    "text": "#E8EEF7",
    "muted": "#6B7FA0",
    "border": "#1E3050",
    "card": "#0C1220",
    "row": "#101928",
    "bg": "#060B14",
    "panel": "#0F1825",
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
            --bg: #060B14;
            --panel: #0C1220;
            --panel-2: #0F1825;
            --line: #1E3050;
            --line-soft: rgba(30, 48, 80, 0.8);
            --line-strong: rgba(255, 102, 0, 0.5);
            --text: #E8EEF7;
            --muted: #6B7FA0;
            --orange: #FF6600;
            --orange-dim: rgba(255, 102, 0, 0.12);
            --blue: #4A9EFF;
            --green: #00C896;
            --red: #E8394A;
            --shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
        }

        html, body { color-scheme: dark; }

        #MainMenu, footer { visibility: hidden; }
        [data-testid="stDecoration"] { display: none; }

        html, body, [class*="css"] {
            font-family: "SF Mono", "JetBrains Mono", "Fira Mono", "Consolas", monospace;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] { background: transparent !important; }
        [data-testid="stHeader"] {
            background: transparent !important;
            visibility: visible !important;
            height: 0 !important;
        }
        [data-testid="stToolbar"] { right: 1rem; }
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            z-index: 1000 !important;
        }

        [data-testid="stSidebar"] {
            background: #070D18 !important;
            border-right: 1px solid var(--line) !important;
        }
        [data-testid="stSidebar"] > div:first-child { background: transparent !important; }

        [data-testid="stSidebarNav"] { padding-top: 1rem; }

        [data-testid="stSidebarNav"]::before {
            content: "MARKET TERMINAL";
            display: block;
            padding: 0 0.5rem 1rem 0.5rem;
            color: var(--orange);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            border-bottom: 1px solid var(--line);
            margin-bottom: 0.5rem;
        }

        [data-testid="stSidebarNav"] ul { gap: 0.2rem; }
        [data-testid="stSidebarNav"] li { margin: 0.05rem 0; }

        [data-testid="stSidebarNav"] a {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            transition: background 0.12s ease, border-color 0.12s ease;
        }
        [data-testid="stSidebarNav"] a:hover {
            background: rgba(255, 102, 0, 0.08);
            border-color: rgba(255, 102, 0, 0.2);
        }
        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: var(--orange-dim);
            border-color: rgba(255, 102, 0, 0.35);
            border-left: 2px solid var(--orange);
        }
        [data-testid="stSidebarNav"] span {
            color: var(--text) !important;
            font-weight: 500;
            font-size: 0.82rem;
            letter-spacing: 0.04em;
        }

        .block-container {
            max-width: 1460px;
            padding-top: 1.2rem !important;
            padding-bottom: 2rem !important;
        }

        h1 {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: var(--text) !important;
            letter-spacing: -0.02em !important;
            margin: 0 !important;
            padding-bottom: 0 !important;
        }

        h2, h3 {
            font-size: 0.68rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.2em !important;
            color: var(--muted) !important;
        }

        .stApp p, .stApp li, .stApp label, .stApp td, .stApp th { color: var(--text); }

        .stCaption,
        [data-testid="stCaptionContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
            color: var(--muted) !important;
        }

        .page-hero {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 3px solid var(--orange);
            border-radius: 4px;
            padding: 1rem 1.2rem;
            margin: 0 0 1rem 0;
        }

        .page-hero__kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            color: var(--orange);
            margin-bottom: 0.3rem;
        }

        .page-hero p {
            max-width: 760px;
            margin: 0.3rem 0 0 0;
            color: var(--muted) !important;
            font-size: 0.82rem;
            line-height: 1.5;
        }

        [data-testid="metric-container"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-top: 2px solid var(--orange);
            border-radius: 4px;
            padding: 14px 16px !important;
        }

        [data-testid="stMetricLabel"] {
            font-size: 10px !important;
            color: var(--muted) !important;
            text-transform: uppercase;
            letter-spacing: 0.16em;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.2rem !important;
            font-weight: 700 !important;
            color: var(--text) !important;
        }

        hr {
            border-color: var(--line) !important;
            margin: 1rem 0 !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 4px !important;
            color: var(--text) !important;
            min-height: 42px;
            box-shadow: none !important;
        }

        input::placeholder, textarea::placeholder {
            color: var(--muted) !important;
        }

        div[data-baseweb="select"] * { color: var(--text) !important; }

        div[role="listbox"] {
            background: var(--panel-2) !important;
            border: 1px solid var(--line) !important;
            border-radius: 4px !important;
        }

        div[role="option"] { color: var(--text) !important; }
        div[role="option"]:hover { background: var(--orange-dim) !important; }

        .stButton > button,
        [data-testid="stBaseButton-secondary"] {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--line);
            border-radius: 4px;
            min-height: 40px;
            padding: 0.45rem 1rem;
            font-weight: 600;
            font-size: 0.8rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            transition: border-color 0.12s ease, background 0.12s ease;
        }

        .stButton > button:hover,
        [data-testid="stBaseButton-secondary"]:hover {
            border-color: var(--orange);
            background: var(--orange-dim);
            color: white;
        }

        [data-testid="stPageLink"] a {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 0.65rem 0.9rem;
            transition: border-color 0.12s ease, background 0.12s ease;
        }
        [data-testid="stPageLink"] a:hover {
            border-color: var(--orange);
            background: var(--orange-dim);
        }
        [data-testid="stPageLink"] p {
            color: var(--text) !important;
            font-weight: 500;
            font-size: 0.82rem;
        }

        [data-testid="stDataFrame"],
        [data-testid="stPlotlyChart"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 4px;
            overflow: hidden;
            padding: 0.2rem;
        }

        [data-testid="stDataFrame"] * { color: var(--text) !important; }

        [data-testid="stAlert"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 4px;
        }

        [data-testid="stMarkdownContainer"] a {
            color: var(--orange);
            text-decoration: none;
        }
        [data-testid="stMarkdownContainer"] a:hover { color: white; }

        @media (max-width: 900px) {
            .page-hero { padding: 0.85rem 1rem; }
            h1 { font-size: 1.3rem !important; }
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
        f'<p style="font-size:9px;text-transform:uppercase;letter-spacing:2px;'
        f'color:{C["muted"]};margin:0 0 12px 0;font-weight:700;border-bottom:1px solid {C["border"]};'
        f'padding-bottom:8px;">{title}</p>'
        if title else ""
    )
    return (
        f'<div style="background:{C["card"]};border:1px solid {C["border"]};'
        f'border-top:2px solid {C["orange"]};border-radius:4px;padding:16px 18px;">'
        + title_html + body_html + "</div>"
    )


def table(rows: list) -> str:
    rows_html = "".join(
        f'<tr style="border-bottom:1px solid {C["row"]};">'
        f'<td style="color:{C["muted"]};padding:7px 4px;font-size:12px;letter-spacing:0.02em;">{row[0]}</td>'
        f'<td style="text-align:right;color:{row[2] if len(row) > 2 else C["text"]};'
        f'padding:7px 4px;font-size:12px;font-weight:700;font-family:monospace;">{row[1]}</td></tr>'
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
