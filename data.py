# data.py — Fetching et cache des données
# Ce fichier est le seul endroit où on appelle yfinance (ou d'autres APIs).
# Chaque fonction est décorée avec @st.cache_data pour éviter les re-fetch inutiles.
# TTL = durée de vie du cache :
#   - 300s (5 min)  pour les données de prix intraday
#   - 3600s (1h)    pour les fondamentaux qui changent rarement

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
from pathlib import Path

TREASURY_SYMBOLS = {"^IRX", "^FVX", "^TNX", "^TYX"}


def _normalize_quote_value(symbol: str, value):
    """
    Yahoo renvoie les taux US en dixièmes de pourcent pour certains symboles
    obligataires (ex: 43.5 pour 4.35%). On les remet en % lisible.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value / 10 if symbol in TREASURY_SYMBOLS else value


def _normalize_calendar_value(value):
    """
    Normalise les différents formats possibles renvoyés par yfinance pour calendar.
    """
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return {}
        if value.shape[1] == 1:
            series = value.iloc[:, 0]
            return {str(idx): _normalize_calendar_value(val) for idx, val in series.items()}
        return {str(col): _normalize_calendar_value(value[col]) for col in value.columns}
    if isinstance(value, pd.Series):
        if value.empty:
            return None
        cleaned = [_normalize_calendar_value(v) for v in value.tolist()]
        cleaned = [v for v in cleaned if v is not None]
        if not cleaned:
            return None
        return cleaned[0] if len(cleaned) == 1 else cleaned
    if isinstance(value, dict):
        normalized = {str(k): _normalize_calendar_value(v) for k, v in value.items()}
        if len(normalized) == 1:
            only_value = next(iter(normalized.values()))
            if isinstance(only_value, dict):
                return only_value
        return normalized
    if isinstance(value, (list, tuple)):
        cleaned = [_normalize_calendar_value(v) for v in value]
        cleaned = [v for v in cleaned if v is not None]
        if not cleaned:
            return None
        return cleaned[0] if len(cleaned) == 1 else cleaned
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _pct_change_from_lookback(series: pd.Series, lookback: int):
    series = series.dropna()
    if len(series) <= lookback:
        return None
    base = series.iloc[-lookback - 1]
    current = series.iloc[-1]
    if base in (None, 0) or pd.isna(base) or pd.isna(current):
        return None
    return ((current - base) / base) * 100


def _latest_valid(series: pd.Series):
    series = series.dropna()
    if series.empty:
        return None
    return series.iloc[-1]


def _compute_bbp_metrics(history: pd.DataFrame) -> dict:
    """
    Bull/Bear Power (Elder Ray) :
    - Bull Power = High - EMA(13)
    - Bear Power = Low - EMA(13)
    - BBP net = Bull Power + Bear Power (proxy synthétique)
    """
    if history is None or history.empty or len(history) < 20:
        return {}

    ema13 = history["Close"].ewm(span=13, adjust=False).mean()
    bull_power = history["High"] - ema13
    bear_power = history["Low"] - ema13

    latest_bull = _latest_valid(bull_power)
    latest_bear = _latest_valid(bear_power)
    if latest_bull is None or latest_bear is None:
        return {}

    return {
        "bull_power": float(latest_bull),
        "bear_power": float(latest_bear),
        "bbp": float(latest_bull + latest_bear),
    }


# -------------------------------------------------------
# SCREENER — UNIVERS DYNAMIQUE via yfinance
# -------------------------------------------------------

_EU_COUNTRIES = ['fr', 'de', 'nl', 'es', 'it', 'be', 'pt', 'fi', 'at', 'ie', 'dk', 'se', 'no', 'ch', 'pl', 'cz', 'hu']
_EU_EX_UK_COUNTRIES = [c for c in _EU_COUNTRIES if c != 'gb']
_SECONDARY_SUFFIXES = ('.F', '.VI', '.MU', '.BE', '.HM', '.DU', '.SG', '.HA', '.TI', '.EI', '.XC')

# region value: either a single country code string, or a list for multi-country
SCREENER_REGIONS = {
    "── Zones ──":          None,
    "Europe":               _EU_COUNTRIES,
    "Europe ex-UK":         _EU_EX_UK_COUNTRIES,
    "── Pays ──":           None,
    "États-Unis":           "us",
    "Royaume-Uni":          "gb",
    "France":               "fr",
    "Allemagne":            "de",
    "Pays-Bas":             "nl",
    "Suède":                "se",
    "Suisse":               "ch",
    "Italie":               "it",
    "Espagne":              "es",
    "Norvège":              "no",
    "Danemark":             "dk",
    "Japon":                "jp",
    "Canada":               "ca",
    "Australie":            "au",
    "Hong Kong":            "hk",
    "Corée du Sud":         "kr",
}

SCREENER_SECTORS = {
    "Tous secteurs": None,
    "Technologie": "Technology",
    "Santé": "Healthcare",
    "Services Financiers": "Financial Services",
    "Énergie": "Energy",
    "Consommation Cyclique": "Consumer Cyclical",
    "Consommation Défensive": "Consumer Defensive",
    "Industrie": "Industrials",
    "Communication": "Communication Services",
    "Matériaux": "Basic Materials",
    "Immobilier": "Real Estate",
    "Services aux collectivités": "Utilities",
}

SCREENER_SORT_OPTIONS = {
    "Market Cap": "intradaymarketcap",
    "Variation 1J (%)": "percentchange",
    "Performance 52S (%)": "fiftytwowkpercentchange",
    "Volume local 3M": "avgdailyvol3m",
}


def _clean_screener_quotes(quotes: list, is_european: bool = False) -> list:
    import re
    seen = {}
    for q in quotes:
        sym = q.get('symbol', '')
        name = q.get('shortName') or q.get('longName') or ''
        if '%' in name:
            continue
        if is_european and any(sym.endswith(s) for s in _SECONDARY_SUFFIXES):
            continue
        if is_european and (q.get('marketCap') or 0) < 500_000_000:
            continue
        canon = re.sub(r'\s+', ' ', name.strip().upper())
        vol = q.get('averageDailyVolume3Month') or 0
        if canon not in seen or vol > (seen[canon].get('averageDailyVolume3Month') or 0):
            seen[canon] = q
    key = 'marketCap' if not is_european else 'marketCap'
    return sorted(seen.values(), key=lambda x: x.get('marketCap') or 0, reverse=True)


@st.cache_data(ttl=300)
def screen_universe(region, sector, sort_field: str, size: int) -> list:
    try:
        from yfinance import EquityQuery, screen as yf_screen

        is_us = region == 'us'
        is_european = isinstance(region, list) or (isinstance(region, str) and region in _EU_COUNTRIES and region != 'us')

        # Build region filter
        if isinstance(region, list):
            region_filter = EquityQuery('is-in', ['region'] + region)
        else:
            region_filter = EquityQuery('eq', ['region', region])

        # For European markets, force volume sort and add min market cap
        if is_european:
            effective_sort = 'avgdailyvol3m'
            # Fetch more to cover all countries before cleanup+re-sort by mktcap
            fetch_size = max(size * 3, 200)
            filters = [
                region_filter,
                EquityQuery('gt', ['intradaymarketcap', 500_000_000]),
            ]
        else:
            effective_sort = sort_field
            fetch_size = size
            filters = [region_filter]

        if sector:
            filters.append(EquityQuery('eq', ['sector', sector]))

        query = EquityQuery('and', filters) if len(filters) > 1 else filters[0]
        result = yf_screen(query, sortField=effective_sort, sortAsc=False, size=fetch_size)
        quotes = result.get('quotes', [])
        cleaned = _clean_screener_quotes(quotes, is_european=is_european)
        return cleaned[:size]
    except Exception:
        return []


# -------------------------------------------------------
# RECHERCHE DE TICKERS
# -------------------------------------------------------

@st.cache_data(ttl=300)
def search_tickers(query: str) -> list:
    """
    Recherche des tickers via l'API de recherche Yahoo Finance.
    Fonctionne avec le nom d'une entreprise ("Apple") ou un symbole ("AAPL").
    Retourne une liste de dicts : [{"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY"}, ...]

    L'API Yahoo est gratuite et ne nécessite pas de clé.
    On filtre sur les types EQUITY (actions), ETF et INDEX.
    """
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q":           query.strip(),
            "quotesCount": 8,      # max 8 résultats
            "newsCount":   0,      # on ne veut pas les news
            "listsCount":  0,
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
        return [
            {
                "symbol": q["symbol"],
                "name":   q.get("shortname") or q.get("longname") or q["symbol"],
                "type":   q.get("quoteType", ""),
            }
            for q in quotes
            if q.get("symbol") and q.get("quoteType") in ("EQUITY", "ETF", "INDEX")
        ]
    except Exception:
        return []


# -------------------------------------------------------
# STOCK — DONNÉES INDIVIDUELLES
# -------------------------------------------------------

@st.cache_data(ttl=60)
def get_stock_info(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = dict(stock.info or {})
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        try:
            last = stock.fast_info.last_price
            if last and not pd.isna(last):
                info["currentPrice"] = float(last)
        except Exception:
            pass
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        try:
            hist = stock.history(period="5d")
            if not hist.empty:
                info["currentPrice"] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return info


@st.cache_data(ttl=300)
def get_stock_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Récupère l'historique OHLCV (Open, High, Low, Close, Volume) d'un stock.
    period : '1mo', '3mo', '6mo', '1y', '2y', '5y'
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period=period)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_analyst_recommendations(ticker: str) -> pd.DataFrame:
    """
    Récupère l'historique des recommandations analystes (Buy/Hold/Sell).
    Cache 1h car ces données changent rarement.
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.recommendations
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_earnings_history(ticker: str) -> pd.DataFrame:
    """
    Récupère l'historique des earnings (EPS réel vs estimé par trimestre).
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.earnings_history
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_insider_transactions(ticker: str) -> pd.DataFrame:
    """
    Récupère les dernières transactions des insiders (dirigeants, actionnaires >10%).
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.insider_transactions
    except Exception:
        return pd.DataFrame()


def compute_indicators(history: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les indicateurs techniques sur un DataFrame de prix OHLCV.
    Retourne le même DataFrame avec des colonnes supplémentaires.

    Indicateurs calculés :
    - MA20, MA50, MA200     : moyennes mobiles simples (rolling mean)
    - BB_upper, BB_lower    : bandes de Bollinger (MA20 ± 2 écarts-types)
    - RSI                   : Relative Strength Index sur 14 jours
    - MACD, MACD_signal     : Moving Average Convergence Divergence
    - MACD_hist             : histogramme MACD (différence entre MACD et signal)
    """
    df = history.copy()

    # --- Moyennes Mobiles Simples ---
    # rolling(n).mean() = moyenne des n dernières clôtures
    df['MA20']  = df['Close'].rolling(20).mean()
    df['MA50']  = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()

    # --- Bandes de Bollinger ---
    # Zone de "normalité" statistique autour de la MA20
    # Upper = MA20 + 2 × écart-type  |  Lower = MA20 - 2 × écart-type
    bb_std          = df['Close'].rolling(20).std()
    df['BB_upper']  = df['MA20'] + 2 * bb_std
    df['BB_lower']  = df['MA20'] - 2 * bb_std

    # --- RSI (14 jours) ---
    # Mesure la force des hausses vs baisses récentes. Echelle 0-100.
    # > 70 = suracheté (signal de vente possible)
    # < 30 = survendu  (signal d'achat possible)
    delta   = df['Close'].diff()                          # variation jour par jour
    gain    = delta.clip(lower=0).rolling(14).mean()      # moyenne des jours en hausse
    loss    = (-delta.clip(upper=0)).rolling(14).mean()   # moyenne des jours en baisse
    rs      = gain / loss                                 # ratio gain/perte
    df['RSI'] = 100 - (100 / (1 + rs))

    # --- MACD ---
    # Montre l'élan (momentum) du prix via la différence entre deux EMA.
    # EMA = Exponential Moving Average (donne plus de poids aux données récentes)
    ema12           = df['Close'].ewm(span=12, adjust=False).mean()  # EMA rapide
    ema26           = df['Close'].ewm(span=26, adjust=False).mean()  # EMA lente
    df['MACD']        = ema12 - ema26                                  # ligne MACD
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()   # ligne signal
    df['MACD_hist']   = df['MACD'] - df['MACD_signal']                # histogramme

    return df


@st.cache_data(ttl=3600)
def get_calendar(ticker: str) -> dict:
    """
    Récupère le prochain earnings date et les estimations.
    Retourne un dict avec 'Earnings Date', 'EPS Estimate', 'Revenue Estimate'.
    """
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        normalized = _normalize_calendar_value(cal)
        return normalized if isinstance(normalized, dict) else {}
    except Exception:
        return {}


# -------------------------------------------------------
# MARCHÉ — DONNÉES GLOBALES
# -------------------------------------------------------

@st.cache_data(ttl=300)
def get_market_data() -> dict:
    """
    Récupère les données des principaux indices et taux.
    Retourne un dict : { "S&P 500": {"value": 5200.0, "change": -0.5}, ... }
    """
    indices = {
        "S&P 500":       "^GSPC",
        "NASDAQ":        "^IXIC",
        "Dow Jones":     "^DJI",
        "Russell 2000":  "^RUT",
        "VIX":           "^VIX",
        "10Y Treasury":  "^TNX",
    }
    data = {}
    for name, symbol in indices.items():
        try:
            hist = yf.Ticker(symbol).history(period="2d")
            if len(hist) >= 2:
                prev    = _normalize_quote_value(symbol, hist['Close'].iloc[-2])
                current = _normalize_quote_value(symbol, hist['Close'].iloc[-1])
                if prev is None or current is None:
                    continue
                change  = ((current - prev) / prev) * 100
                data[name] = {"value": current, "change": change}
        except Exception:
            pass
    return data


@st.cache_data(ttl=300)
def get_sector_performance() -> dict:
    """
    Récupère la performance du jour pour chaque secteur S&P via les ETFs XL*.
    Retourne un dict : { "Tech": 1.2, "Finance": -0.3, ... }
    """
    sectors = {
        "Tech":           "XLK",
        "Finance":        "XLF",
        "Santé":          "XLV",
        "Énergie":        "XLE",
        "Industrie":      "XLI",
        "Conso. Disc.":   "XLY",
        "Conso. Staples": "XLP",
        "Matériaux":      "XLB",
        "Immobilier":     "XLRE",
        "Utilities":      "XLU",
        "Télécom":        "XLC",
    }
    perf = {}
    for name, symbol in sectors.items():
        try:
            hist = yf.Ticker(symbol).history(period="2d")
            if len(hist) >= 2:
                change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                perf[name] = round(change, 2)
        except Exception:
            pass
    return perf


@st.cache_data(ttl=300)
def get_yield_curve() -> dict:
    """
    Récupère les taux des obligations US pour construire la courbe des taux.
    Retourne un dict : { "3M": 5.2, "5Y": 4.8, "10Y": 4.5, "30Y": 4.7 }
    """
    treasuries = {
        "3M":  "^IRX",
        "5Y":  "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }
    yields = {}
    for name, symbol in treasuries.items():
        try:
            hist = yf.Ticker(symbol).history(period="1d")
            if len(hist) > 0:
                close = _normalize_quote_value(symbol, hist['Close'].iloc[-1])
                if close is not None:
                    yields[name] = close
        except Exception:
            pass
    return yields


@st.cache_data(ttl=300)
def get_fear_greed_index() -> dict:
    """
    Tente de récupérer l'indice Fear & Greed CNN.
    Si la source ne répond pas, retourne un dict vide.
    """
    endpoints = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=headers, timeout=5)
            response.raise_for_status()
            payload = response.json()

            current = payload.get("fear_and_greed") or payload.get("fear_and_greed_historical", {}).get("current")
            score = None
            rating = None
            timestamp = None

            if isinstance(current, dict):
                score = current.get("score") or current.get("value")
                rating = current.get("rating") or current.get("status")
                timestamp = current.get("timestamp") or current.get("updateTime")
            elif isinstance(current, (int, float)):
                score = current

            if score is not None:
                try:
                    score = float(score)
                except Exception:
                    score = None

            if score is None:
                continue

            if not rating:
                if score >= 75:
                    rating = "Extreme Greed"
                elif score >= 55:
                    rating = "Greed"
                elif score >= 45:
                    rating = "Neutral"
                elif score >= 25:
                    rating = "Fear"
                else:
                    rating = "Extreme Fear"

            return {"score": score, "rating": rating, "timestamp": timestamp, "source": "CNN"}
        except Exception:
            continue

    return {}


@st.cache_data(ttl=300)
def get_market_snapshot() -> dict:
    """
    Vue priorisée du marché avec indices, volatilité et actifs de contexte.
    Les indices cash sont approchés via ETF liquides pour pouvoir calculer
    rendement, tendance et BBP de façon homogène.
    """
    assets = {
        "S&P 500": {"symbol": "SPY", "category": "Core Equity"},
        "Nasdaq 100": {"symbol": "QQQ", "category": "Core Equity"},
        "Dow Jones": {"symbol": "DIA", "category": "Core Equity"},
        "Russell 2000": {"symbol": "IWM", "category": "Core Equity"},
        "VIX": {"symbol": "^VIX", "category": "Volatility"},
        "VIX 3M": {"symbol": "^VIX3M", "category": "Volatility"},
        "10Y Treasury": {"symbol": "^TNX", "category": "Rates"},
        "Gold": {"symbol": "GLD", "category": "Cross-Asset"},
        "US Dollar": {"symbol": "UUP", "category": "Cross-Asset"},
    }

    snapshot = {}
    for name, meta in assets.items():
        symbol = meta["symbol"]
        try:
            hist = yf.Ticker(symbol).history(period="1y")
            if hist.empty:
                continue

            close = hist["Close"].copy()
            if symbol in TREASURY_SYMBOLS:
                close = close.apply(lambda value: _normalize_quote_value(symbol, value))
                hist = hist.copy()
                hist["Close"] = close
                hist["High"] = hist["High"].apply(lambda value: _normalize_quote_value(symbol, value))
                hist["Low"] = hist["Low"].apply(lambda value: _normalize_quote_value(symbol, value))

            current = _latest_valid(close)
            prev_close = close.dropna().iloc[-2] if len(close.dropna()) >= 2 else None
            ma50 = _latest_valid(close.rolling(50).mean())
            ma200 = _latest_valid(close.rolling(200).mean())
            bbp = _compute_bbp_metrics(hist) if symbol not in TREASURY_SYMBOLS else {}

            if current is None:
                continue

            change_1d = ((current - prev_close) / prev_close * 100) if prev_close not in (None, 0) else None
            snapshot[name] = {
                "symbol": symbol,
                "category": meta["category"],
                "value": float(current),
                "change_1d": float(change_1d) if change_1d is not None else None,
                "perf_1m": _pct_change_from_lookback(close, 21),
                "perf_3m": _pct_change_from_lookback(close, 63),
                "ma50_gap_pct": ((current - ma50) / ma50 * 100) if ma50 not in (None, 0) else None,
                "ma200_gap_pct": ((current - ma200) / ma200 * 100) if ma200 not in (None, 0) else None,
                "above_ma50": bool(ma50 is not None and current > ma50),
                "above_ma200": bool(ma200 is not None and current > ma200),
                **bbp,
            }
        except Exception:
            continue

    return snapshot


@st.cache_data(ttl=300)
def get_market_breadth() -> dict:
    """
    Breadth proxy basé sur les grands ETFs indices/secteurs.
    Permet de lire rapidement si la hausse/baisse est large ou étroite.
    """
    universe = {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq 100",
        "DIA": "Dow Jones",
        "IWM": "Russell 2000",
        "XLK": "Tech",
        "XLF": "Finance",
        "XLV": "Santé",
        "XLI": "Industrie",
        "XLE": "Énergie",
        "XLY": "Conso. Disc.",
        "XLP": "Conso. Staples",
        "XLB": "Matériaux",
        "XLU": "Utilities",
        "XLRE": "Immobilier",
        "XLC": "Télécom",
    }

    try:
        history = yf.download(
            tickers=list(universe.keys()),
            period="1y",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
        )
    except Exception:
        return {}

    if history is None or history.empty:
        return {}

    advancers = 0
    decliners = 0
    above_50 = 0
    above_200 = 0
    rows = []

    for symbol, label in universe.items():
        try:
            if isinstance(history.columns, pd.MultiIndex):
                frame = history[symbol].dropna(how="all")
                close = frame["Close"].dropna()
            else:
                close = history["Close"].dropna()

            if close.empty:
                continue

            current = close.iloc[-1]
            previous = close.iloc[-2] if len(close) >= 2 else None
            ma50 = _latest_valid(close.rolling(50).mean())
            ma200 = _latest_valid(close.rolling(200).mean())
            day_change = ((current - previous) / previous * 100) if previous not in (None, 0) else None

            if day_change is not None:
                advancers += int(day_change > 0)
                decliners += int(day_change < 0)
            above_50 += int(ma50 is not None and current > ma50)
            above_200 += int(ma200 is not None and current > ma200)

            rows.append(
                {
                    "Ticker": symbol,
                    "Name": label,
                    "1D %": round(day_change, 2) if day_change is not None else None,
                    "Above 50D": "Yes" if ma50 is not None and current > ma50 else "No",
                    "Above 200D": "Yes" if ma200 is not None and current > ma200 else "No",
                }
            )
        except Exception:
            continue

    total = len(rows)
    if total == 0:
        return {}

    return {
        "universe_size": total,
        "advancers": advancers,
        "decliners": decliners,
        "advance_decline": advancers - decliners,
        "pct_above_50": (above_50 / total) * 100,
        "pct_above_200": (above_200 / total) * 100,
        "trend_table": rows,
    }


# -------------------------------------------------------
# PERSISTANCE LOCALE — WATCHLIST
# -------------------------------------------------------

WATCHLIST_FILE = Path(__file__).with_name("watchlist.json")


def load_watchlist() -> list:
    """
    Charge la watchlist locale depuis un fichier JSON.
    Retourne une liste vide si le fichier n'existe pas encore.
    """
    try:
        if WATCHLIST_FILE.exists():
            data = json.loads(WATCHLIST_FILE.read_text())
            if isinstance(data, list):
                return [str(t).upper().strip() for t in data if str(t).strip()]
    except Exception:
        pass
    return []


def save_watchlist(tickers: list) -> None:
    """
    Sauvegarde la watchlist locale en JSON.
    On nettoie et déduplique les tickers avant l'écriture.
    """
    cleaned = []
    for ticker in tickers:
        value = str(ticker).upper().strip()
        if value and value not in cleaned:
            cleaned.append(value)

    WATCHLIST_FILE.write_text(json.dumps(cleaned, indent=2))
