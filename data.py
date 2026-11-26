# data.py — Fetching et cache des données
# Ce fichier est le seul endroit où on appelle yfinance (ou d'autres APIs).
# Chaque fonction est décorée avec @st.cache_data pour éviter les re-fetch inutiles.
# TTL = durée de vie du cache :
#   - 300s (5 min)  pour les données de prix intraday
#   - 3600s (1h)    pour les fondamentaux qui changent rarement

#
# Règle importante sur le cache :
#   st.cache_data ne met PAS en cache une fonction qui lève une exception.
#   Les fonctions "_fetch_*" lèvent donc une erreur quand Yahoo échoue
#   (rate limit, réponse vide), pour qu'un échec ne reste pas bloqué en cache
#   pendant 1h. Les fonctions publiques "get_*" attrapent l'erreur et renvoient
#   une valeur vide propre à afficher.

import time

import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import requests
import json
from pathlib import Path

try:
    from yfinance.exceptions import YFRateLimitError
except Exception:  # pragma: no cover - très anciennes versions de yfinance
    class YFRateLimitError(Exception):
        pass

# Taux US : Yahoo les renvoie déjà en % (ex : 4.35 pour 4.35 %).
TREASURY_SYMBOLS = {"^IRX", "^FVX", "^TNX", "^TYX"}


def is_streamlit_cloud() -> bool:
    """Vrai quand l'app tourne sur Streamlit Community Cloud (le code y est monté dans /mount/src)."""
    import os
    return Path(__file__).resolve().as_posix().startswith("/mount/src/") or os.environ.get("HOSTNAME") == "streamlit"


def is_rate_limit_error(exc: Exception) -> bool:
    """Vrai si l'erreur vient du blocage Yahoo (trop de requêtes)."""
    if isinstance(exc, YFRateLimitError):
        return True
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "429" in text


def is_yahoo_blocked_error(exc: Exception) -> bool:
    """Vrai si Yahoo refuse l'accès (rate limit 429 ou session refusée 401/403)."""
    if is_rate_limit_error(exc):
        return True
    text = str(exc).lower()
    return any(code in text for code in ("401", "403", "unauthorized", "forbidden", "invalid crumb"))


_sleep = time.sleep  # remplacé par un no-op dans les tests


def _with_retry(func, *args, attempts: int = 2, wait: float = 1.5):
    """Appelle func(*args). En cas de blocage Yahoo, réessaie une fois après une courte pause."""
    for attempt in range(attempts):
        try:
            return func(*args)
        except Exception as exc:
            if attempt < attempts - 1 and is_rate_limit_error(exc):
                _sleep(wait)
                continue
            raise


def _flatten_download(df: pd.DataFrame) -> pd.DataFrame:
    """yf.download() retourne un MultiIndex ('Close','NVDA') pour un seul ticker.
    Cette fonction le réduit à un Index simple ('Close', 'Open', …)."""
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _as_frame(value) -> pd.DataFrame:
    """yfinance renvoie parfois None ou un dict au lieu d'un DataFrame."""
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


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

_EU_COUNTRIES = ['gb', 'fr', 'de', 'nl', 'es', 'it', 'be', 'pt', 'fi', 'at', 'ie', 'dk', 'se', 'no', 'ch', 'pl', 'cz', 'hu']
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


# Champ de tri Yahoo -> champ correspondant dans chaque résultat
_SORT_FIELD_TO_QUOTE_KEY = {
    "intradaymarketcap": "marketCap",
    "percentchange": "regularMarketChangePercent",
    "fiftytwowkpercentchange": "fiftyTwoWeekChangePercent",
    "avgdailyvol3m": "averageDailyVolume3Month",
}


def _clean_screener_quotes(quotes: list, is_european: bool = False, sort_field: str = "intradaymarketcap") -> list:
    """Supprime obligations, listings secondaires et doublons, puis trie selon le choix de l'utilisateur."""
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
    key = _SORT_FIELD_TO_QUOTE_KEY.get(sort_field, "marketCap")
    return sorted(seen.values(), key=lambda x: x.get(key) or 0, reverse=True)


@st.cache_data(ttl=300)
def screen_universe(region, sector, sort_field: str, size: int) -> list:
    from yfinance import EquityQuery, screen as yf_screen

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

    # Yahoo refuse toute requête au-delà de 250 résultats
    fetch_size = min(fetch_size, 250)

    query = EquityQuery('and', filters) if len(filters) > 1 else filters[0]
    result = _with_retry(
        lambda: yf_screen(query, sortField=effective_sort, sortAsc=False, size=fetch_size)
    )
    quotes = (result or {}).get('quotes', [])
    cleaned = _clean_screener_quotes(quotes, is_european=is_european, sort_field=sort_field)
    return cleaned[:size]


# -------------------------------------------------------
# RECHERCHE DE TICKERS
# -------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_search(query: str) -> list:
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {
        "q":           query,
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
        return _fetch_search(query.strip())
    except Exception:
        return []


# -------------------------------------------------------
# STOCK — DONNÉES INDIVIDUELLES
# -------------------------------------------------------

def _supplement_fundamentals(stock, info: dict) -> None:
    """
    Complète les métriques fondamentales manquantes via les états financiers yfinance.
    Appelé quand stock.info est incomplet (rate-limit Streamlit Cloud typiquement).
    """
    has_fundamentals = any(info.get(k) for k in ("grossMargins", "trailingPE", "totalRevenue"))
    if has_fundamentals:
        return

    def _safe_val(df, key):
        try:
            if key in df.index:
                vals = df.loc[key].dropna()
                return float(vals.iloc[0]) if len(vals) > 0 else None
        except Exception:
            pass
        return None

    # ── Income statement ────────────────────────────────────────────────────
    try:
        fin = stock.financials
        if fin is not None and not fin.empty:
            rev = _safe_val(fin, "Total Revenue")
            gp = _safe_val(fin, "Gross Profit")
            op_inc = _safe_val(fin, "Operating Income")
            net_inc = _safe_val(fin, "Net Income")
            ebitda = _safe_val(fin, "EBITDA")
            eps_d = _safe_val(fin, "Diluted EPS")

            if rev and rev > 0:
                info.setdefault("totalRevenue", rev)
                if gp is not None:
                    info.setdefault("grossMargins", gp / rev)
                if op_inc is not None:
                    info.setdefault("operatingMargins", op_inc / rev)
                if net_inc is not None:
                    info.setdefault("profitMargins", net_inc / rev)
            if ebitda is not None:
                info.setdefault("ebitda", ebitda)
            if eps_d is not None:
                info.setdefault("trailingEps", eps_d)

            # Revenue growth YoY
            if "Total Revenue" in fin.index:
                revs = fin.loc["Total Revenue"].dropna()
                if len(revs) >= 2:
                    r0, r1 = float(revs.iloc[0]), float(revs.iloc[1])
                    if r1 != 0:
                        info.setdefault("revenueGrowth", (r0 - r1) / abs(r1))

            # Earnings growth YoY
            if "Net Income" in fin.index:
                nics = fin.loc["Net Income"].dropna()
                if len(nics) >= 2:
                    n0, n1 = float(nics.iloc[0]), float(nics.iloc[1])
                    if n1 != 0:
                        info.setdefault("earningsGrowth", (n0 - n1) / abs(n1))

    except Exception:
        pass

    # ── Balance sheet ────────────────────────────────────────────────────────
    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            total_debt = _safe_val(bs, "Total Debt")
            equity = _safe_val(bs, "Stockholders Equity") or _safe_val(bs, "Common Stock Equity")
            total_assets = _safe_val(bs, "Total Assets")
            cash = _safe_val(bs, "Cash Cash Equivalents And Short Term Investments")
            curr_assets = _safe_val(bs, "Current Assets")
            curr_liab = _safe_val(bs, "Current Liabilities")

            if total_debt is not None:
                info.setdefault("totalDebt", total_debt)
            if cash is not None:
                info.setdefault("totalCash", cash)
            if equity and equity != 0 and total_debt is not None:
                info.setdefault("debtToEquity", total_debt / equity * 100)
            if curr_assets is not None and curr_liab and curr_liab > 0:
                info.setdefault("currentRatio", curr_assets / curr_liab)

            # ROE et ROA nécessitent le résultat net de l'income statement
            try:
                fin = stock.financials
                if fin is not None and not fin.empty and "Net Income" in fin.index:
                    nics = fin.loc["Net Income"].dropna()
                    if len(nics) > 0:
                        net_inc = float(nics.iloc[0])
                        if equity and equity > 0:
                            info.setdefault("returnOnEquity", net_inc / equity)
                        if total_assets and total_assets > 0:
                            info.setdefault("returnOnAssets", net_inc / total_assets)
            except Exception:
                pass

    except Exception:
        pass

    # ── Cash flow ────────────────────────────────────────────────────────────
    try:
        cf = stock.cashflow
        if cf is not None and not cf.empty:
            fcf = _safe_val(cf, "Free Cash Flow")
            if fcf is not None:
                info.setdefault("freeCashflow", fcf)
    except Exception:
        pass


# Clés qui prouvent que Yahoo a bien renvoyé le profil complet de la société
_PROFILE_KEYS = ("longName", "shortName", "quoteType", "sector")


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_full_info(ticker: str) -> dict:
    """Profil complet Yahoo (fondamentaux, multiples, consensus). Lève une erreur si Yahoo bloque."""
    fetched = yf.Ticker(ticker).info
    if not isinstance(fetched, dict) or not any(fetched.get(k) for k in _PROFILE_KEYS):
        raise RuntimeError(f"Profil Yahoo incomplet pour {ticker}")
    return dict(fetched)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_price_snapshot(ticker: str) -> dict:
    """
    Prix, clôture de la veille, devise, market cap via les endpoints légers
    (fast_info puis historique de prix), qui sont rarement bloqués.
    """
    snap = {}
    stock = yf.Ticker(ticker)

    try:
        fi = stock.fast_info
        for attr, key in [
            ("last_price", "currentPrice"),
            ("previous_close", "previousClose"),
            ("market_cap", "marketCap"),
            ("currency", "currency"),
            ("year_high", "fiftyTwoWeekHigh"),
            ("year_low", "fiftyTwoWeekLow"),
        ]:
            try:
                val = getattr(fi, attr, None)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    snap[key] = float(val) if key != "currency" else val
            except Exception:
                continue
    except Exception:
        pass

    if not snap.get("currentPrice") or not snap.get("previousClose"):
        hist = _flatten_download(
            yf.download(ticker, period="5d", progress=False, auto_adjust=False)
        )
        closes = hist["Close"].dropna() if not hist.empty and "Close" in hist else pd.Series(dtype=float)
        if len(closes) >= 1:
            snap.setdefault("currentPrice", float(closes.iloc[-1]))
        if len(closes) >= 2:
            snap.setdefault("previousClose", float(closes.iloc[-2]))

    if not snap.get("currentPrice"):
        raise RuntimeError(f"Aucune donnée de prix disponible pour {ticker}")
    return snap


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_statement_fundamentals(ticker: str) -> dict:
    """Marges, croissance, dette, FCF recalculés depuis les états financiers publiés."""
    computed = {}
    _supplement_fundamentals(yf.Ticker(ticker), computed)
    return computed


def get_stock_info(ticker: str) -> dict:
    """
    Assemble les données d'une société à partir de 3 sources, de la plus riche à la plus robuste :
      1. profil complet Yahoo (peut être bloqué sur Streamlit Cloud)
      2. prix + clôture de la veille (endpoints légers)
      3. états financiers (pour recalculer marges, croissance, dette)
    La clé "_partial" vaut True quand le profil complet n'a pas pu être chargé.
    La clé "_rate_limited" vaut True quand c'est à cause du blocage Yahoo.
    """
    info = {}
    partial = False
    rate_limited = False

    try:
        info = dict(_with_retry(_fetch_full_info, ticker))
    except Exception as exc:
        partial = True
        rate_limited = is_yahoo_blocked_error(exc)

    if not info.get("currentPrice"):
        info["currentPrice"] = info.get("regularMarketPrice")
    if not info.get("previousClose"):
        info["previousClose"] = info.get("regularMarketPreviousClose")

    if not info.get("currentPrice") or not info.get("previousClose"):
        try:
            snap = _fetch_price_snapshot(ticker)
            for key, value in snap.items():
                if not info.get(key):
                    info[key] = value
        except Exception:
            pass

    if not info.get("currentPrice"):
        raise RuntimeError(f"Aucune donnée de prix disponible pour {ticker}")

    has_fundamentals = any(info.get(k) for k in ("grossMargins", "trailingPE", "totalRevenue"))
    if not has_fundamentals:
        try:
            for key, value in _fetch_statement_fundamentals(ticker).items():
                info.setdefault(key, value)
        except Exception:
            pass

    info["_partial"] = partial
    info["_rate_limited"] = rate_limited
    return info


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_history(ticker: str, period: str) -> pd.DataFrame:
    df = _flatten_download(yf.download(ticker, period=period, progress=False, auto_adjust=True))
    if df.empty:
        df = yf.Ticker(ticker).history(period=period)
    if df is None or df.empty:
        raise RuntimeError(f"Historique vide pour {ticker}")
    # Index sans fuseau horaire : permet de comparer des titres de places différentes
    if getattr(df.index, "tz", None) is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df


def get_stock_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Récupère l'historique OHLCV (Open, High, Low, Close, Volume) d'un stock.
    period : '1mo', '3mo', '6mo', '1y', '2y', '5y'
    """
    try:
        return _with_retry(_fetch_history, ticker, period)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_recommendations(ticker: str) -> pd.DataFrame:
    return _as_frame(yf.Ticker(ticker).recommendations)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_earnings_history(ticker: str) -> pd.DataFrame:
    return _as_frame(yf.Ticker(ticker).earnings_history)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_insider_transactions(ticker: str) -> pd.DataFrame:
    return _as_frame(yf.Ticker(ticker).insider_transactions)


def _safe_frame(fetcher, ticker: str) -> pd.DataFrame:
    try:
        return _with_retry(fetcher, ticker)
    except Exception:
        return pd.DataFrame()


def get_analyst_recommendations(ticker: str) -> pd.DataFrame:
    """Historique des recommandations analystes (Buy/Hold/Sell). Vide si indisponible."""
    return _safe_frame(_fetch_recommendations, ticker)


def get_earnings_history(ticker: str) -> pd.DataFrame:
    """Historique des earnings (EPS réel vs estimé par trimestre). Vide si indisponible."""
    return _safe_frame(_fetch_earnings_history, ticker)


def get_insider_transactions(ticker: str) -> pd.DataFrame:
    """Dernières transactions des insiders. Vide si indisponible."""
    return _safe_frame(_fetch_insider_transactions, ticker)


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
    # Méthode de Wilder (standard Bloomberg / TradingView) : moyenne lissée
    # exponentielle avec alpha = 1/14, et non une moyenne simple sur 14 jours.
    delta   = df['Close'].diff()                                              # variation jour par jour
    gain    = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss    = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs      = gain / loss                                                     # ratio gain/perte
    df['RSI'] = 100 - (100 / (1 + rs))
    df.loc[(loss == 0) & (gain > 0), 'RSI'] = 100.0                           # que des hausses

    # --- MACD ---
    # Montre l'élan (momentum) du prix via la différence entre deux EMA.
    # EMA = Exponential Moving Average (donne plus de poids aux données récentes)
    ema12           = df['Close'].ewm(span=12, adjust=False).mean()  # EMA rapide
    ema26           = df['Close'].ewm(span=26, adjust=False).mean()  # EMA lente
    df['MACD']        = ema12 - ema26                                  # ligne MACD
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()   # ligne signal
    df['MACD_hist']   = df['MACD'] - df['MACD_signal']                # histogramme

    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_calendar(ticker: str) -> dict:
    normalized = _normalize_calendar_value(yf.Ticker(ticker).calendar)
    return normalized if isinstance(normalized, dict) else {}


def get_calendar(ticker: str) -> dict:
    """
    Récupère le prochain earnings date et les estimations.
    Retourne un dict avec 'Earnings Date', 'EPS Estimate', 'Revenue Estimate'.
    """
    try:
        return _with_retry(_fetch_calendar, ticker)
    except Exception:
        return {}


# -------------------------------------------------------
# MARCHÉ — DONNÉES GLOBALES
# -------------------------------------------------------

# Une configuration par zone. Chaque bloc est optionnel : la page masque ce qui n'existe pas.
# Symboles vérifiés sur Yahoo le 2026-11-26. Yahoo ne fournit ni VSTOXX ni taux du Bund :
# pour l'Europe et l'Asie, la volatilité affichée est la volatilité réalisée de l'indice principal.
US_SECTOR_ETFS = {
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

EU_SECTOR_ETFS = {  # iShares STOXX Europe 600 sectoriels (Xetra, EUR)
    "Banques":            "EXV1.DE",
    "Assurance":          "EXH5.DE",
    "Services financiers": "EXH2.DE",
    "Pétrole & gaz":      "EXH1.DE",
    "Utilities":          "EXH9.DE",
    "Technologie":        "EXV3.DE",
    "Télécoms":           "EXV2.DE",
    "Santé":              "EXV4.DE",
    "Biens industriels":  "EXH4.DE",
    "Construction":       "EXV8.DE",
    "Chimie":             "EXV7.DE",
    "Matières premières": "EXV6.DE",
    "Automobile":         "EXV5.DE",
    "Agroalimentaire":    "EXH3.DE",
    "Biens de conso.":    "EXH7.DE",
    "Distribution":       "EXH8.DE",
    "Voyages & loisirs":  "EXV9.DE",
    "Médias":             "EXH6.DE",
    "Immobilier":         "EXI5.DE",
}

MARKET_REGIONS = {
    "États-Unis": {
        "indices": {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Dow Jones": "^DJI", "Russell 2000": "^RUT"},
        "main": "S&P 500",
        "leadership": [("Nasdaq 100", "S&P 500", "Nasdaq vs S&P (1M)"), ("Russell 2000", "S&P 500", "Small vs large caps (1M)")],
        "implied_vol": {"VIX": "^VIX", "VIX 3M": "^VIX3M"},
        "rates": {"3M": "^IRX", "5Y": "^FVX", "10Y": "^TNX", "30Y": "^TYX"},
        "sectors": US_SECTOR_ETFS,
        "sectors_label": "ETFs sectoriels S&P 500 (XL*)",
        "cross": {"Dollar (DXY)": "DX-Y.NYB", "Or": "GC=F", "Brent": "BZ=F"},
        "headline_cross": None,
    },
    "Europe": {
        "indices": {
            "Stoxx 600": "^STOXX", "Euro Stoxx 50": "^STOXX50E", "DAX": "^GDAXI", "CAC 40": "^FCHI",
            "FTSE 100": "^FTSE", "FTSE MIB": "FTSEMIB.MI", "IBEX 35": "^IBEX", "SMI": "^SSMI", "AEX": "^AEX",
        },
        "main": "Stoxx 600",
        "leadership": [("Euro Stoxx 50", "Stoxx 600", "Euro Stoxx 50 vs Stoxx 600 (1M)"), ("DAX", "CAC 40", "DAX vs CAC 40 (1M)")],
        "implied_vol": {},
        "rates": {},
        "sectors": EU_SECTOR_ETFS,
        "sectors_label": "ETFs sectoriels Stoxx Europe 600",
        "cross": {"EUR/USD": "EURUSD=X", "EUR/GBP": "EURGBP=X", "Or": "GC=F", "Brent": "BZ=F"},
        "headline_cross": "EUR/USD",
    },
    "Asie": {
        "indices": {
            "Nikkei 225": "^N225", "Hang Seng": "^HSI", "Shanghai Composite": "000001.SS", "KOSPI": "^KS11",
            "Taiwan (TAIEX)": "^TWII", "Nifty 50": "^NSEI", "ASX 200": "^AXJO",
        },
        "main": "Nikkei 225",
        "leadership": [("Hang Seng", "Nikkei 225", "Hang Seng vs Nikkei (1M)"), ("Nifty 50", "Nikkei 225", "Inde vs Japon (1M)")],
        "implied_vol": {},
        "rates": {},
        "sectors": {},
        "sectors_label": "",
        "cross": {"USD/JPY": "USDJPY=X", "USD/CNY": "USDCNY=X", "Or": "GC=F", "Brent": "BZ=F"},
        "headline_cross": "USD/JPY",
    },
}


def _region_symbols(region: str) -> list:
    cfg = MARKET_REGIONS[region]
    symbols = set(cfg["indices"].values()) | set(cfg["implied_vol"].values()) | set(cfg["rates"].values())
    symbols |= set(cfg["sectors"].values()) | set(cfg["cross"].values())
    return sorted(symbols)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_region_history(region: str) -> dict:
    """Historique 1 an de tous les symboles d'une zone, en un seul téléchargement groupé."""
    symbols = _region_symbols(region)
    raw = yf.download(
        tickers=symbols,
        period="1y",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if raw is None or raw.empty:
        raise RuntimeError("Téléchargement marché vide")

    frames = {}
    for symbol in symbols:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if symbol not in raw.columns.get_level_values(0):
                    continue
                frame = raw[symbol]
            else:
                frame = raw
            frame = frame.dropna(how="all")
            if not frame.empty and "Close" in frame and frame["Close"].notna().any():
                frames[symbol] = frame
        except Exception:
            continue

    if not frames:
        raise RuntimeError("Aucun symbole marché exploitable")
    return frames


def get_market_history(region: str = "États-Unis") -> dict:
    """{symbole: DataFrame OHLCV} pour une zone. Dict vide si Yahoo ne répond pas."""
    try:
        return _with_retry(_fetch_region_history, region)
    except Exception:
        return {}


def _close(frames: dict, symbol: str) -> pd.Series:
    frame = frames.get(symbol)
    if frame is None or "Close" not in frame:
        return pd.Series(dtype=float)
    return frame["Close"].dropna()


def _day_change_pct(close: pd.Series):
    if len(close) < 2:
        return None
    prev, last = close.iloc[-2], close.iloc[-1]
    if prev == 0 or pd.isna(prev) or pd.isna(last):
        return None
    return float((last - prev) / prev * 100)


def realized_vol(close: pd.Series, window: int = 20):
    """Volatilité réalisée annualisée en % (écart-type des rendements journaliers x racine de 252)."""
    returns = np.log(close / close.shift(1)).dropna()
    if len(returns) < window:
        return None
    return float(returns.tail(window).std() * np.sqrt(252) * 100)


def _asset_stats(frames: dict, symbol: str) -> dict:
    close = _close(frames, symbol)
    current = _latest_valid(close)
    if current is None:
        return {}
    ma50 = _latest_valid(close.rolling(50).mean())
    ma200 = _latest_valid(close.rolling(200).mean())
    hist = frames.get(symbol)
    bbp = _compute_bbp_metrics(hist) if symbol not in TREASURY_SYMBOLS else {}
    return {
        "symbol": symbol,
        "value": float(current),
        "change_1d": _day_change_pct(close),
        "perf_1m": _pct_change_from_lookback(close, 21),
        "perf_3m": _pct_change_from_lookback(close, 63),
        "above_ma50": bool(ma50 is not None and current > ma50),
        "above_ma200": bool(ma200 is not None and current > ma200),
        "has_ma200": ma200 is not None,
        **bbp,
    }


def get_region_overview(region: str = "États-Unis") -> dict:
    """
    Tout ce qu'affiche Market Overview pour une zone :
    indices, volatilité, breadth, leadership, taux, intermarket, rotation sectorielle.
    """
    cfg = MARKET_REGIONS[region]
    frames = get_market_history(region)
    if not frames:
        return {}

    indices = {name: _asset_stats(frames, s) for name, s in cfg["indices"].items()}
    indices = {k: v for k, v in indices.items() if v}

    implied = {name: _asset_stats(frames, s) for name, s in cfg["implied_vol"].items()}
    implied = {k: v for k, v in implied.items() if v}

    main_close = _close(frames, cfg["indices"][cfg["main"]])
    realized = realized_vol(main_close)

    sectors = {}
    for name, s in cfg["sectors"].items():
        stats = _asset_stats(frames, s)
        if stats:
            sectors[name] = stats

    # Breadth : sur les secteurs quand la zone en a, sinon sur les indices
    universe = sectors or indices
    breadth = {}
    if universe:
        changes = [v["change_1d"] for v in universe.values() if v.get("change_1d") is not None]
        with_ma200 = [v for v in universe.values() if v.get("has_ma200")]
        breadth = {
            "basis": "secteurs" if sectors else "indices",
            "universe_size": len(universe),
            "advancers": sum(c > 0 for c in changes),
            "decliners": sum(c < 0 for c in changes),
            "pct_above_50": sum(v["above_ma50"] for v in universe.values()) / len(universe) * 100,
            "pct_above_200": (sum(v["above_ma200"] for v in with_ma200) / len(with_ma200) * 100) if with_ma200 else None,
        }
        breadth["advance_decline"] = breadth["advancers"] - breadth["decliners"]

    leadership = []
    for a, b, label in cfg["leadership"]:
        pa, pb = indices.get(a, {}).get("perf_1m"), indices.get(b, {}).get("perf_1m")
        if pa is not None and pb is not None:
            leadership.append({"label": label, "spread": pa - pb, "leader": a if pa > pb else b})

    rates = {}
    for name, s in cfg["rates"].items():
        last = _latest_valid(_close(frames, s))
        if last is not None:
            rates[name] = float(last)

    cross = {name: _asset_stats(frames, s) for name, s in cfg["cross"].items()}
    cross = {k: v for k, v in cross.items() if v}

    return {
        "region": region,
        "main": cfg["main"],
        "indices": indices,
        "implied_vol": implied,
        "realized_vol": realized,
        "sectors": sectors,
        "sectors_label": cfg["sectors_label"],
        "breadth": breadth,
        "leadership": leadership,
        "rates": rates,
        "cross": cross,
        "headline_cross": cfg["headline_cross"],
    }


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


# -------------------------------------------------------
# PAIRS — COMPARABLES D'UNE SOCIÉTÉ
# -------------------------------------------------------

_COUNTRY_CODES = {
    "United Kingdom": "gb", "France": "fr", "Germany": "de", "Netherlands": "nl", "Spain": "es",
    "Italy": "it", "Belgium": "be", "Portugal": "pt", "Finland": "fi", "Austria": "at",
    "Ireland": "ie", "Denmark": "dk", "Sweden": "se", "Norway": "no", "Switzerland": "ch",
    "Poland": "pl", "Czech Republic": "cz", "Hungary": "hu", "Luxembourg": "lu", "Jersey": "gb",
    "United States": "us", "Canada": "ca", "Japan": "jp", "Australia": "au", "Hong Kong": "hk",
    "South Korea": "kr", "Taiwan": "tw", "India": "in", "China": "cn", "Singapore": "sg",
}

# Cotations secondaires ou multilatérales à écarter (Francfort, Vienne, Cboe Europe, LSE IOB...)
_PEER_EXCLUDED_SUFFIXES = _SECONDARY_SUFFIXES + (".IL",)
_NAME_NOISE = {
    "PLC", "ORD", "SA", "SE", "AG", "NV", "AB", "ASA", "SER", "B", "A", "INC", "CORP", "CORPORATION",
    "HOLDINGS", "HOLDING", "GROUP", "CO", "LTD", "OYJ", "AS", "SPA", "THE", "CLASS", "SHS", "REG", "CXGLO",
}


def _canonical_name(name: str) -> str:
    """'ROLLS-ROYCE HOLDINGS PLC ORD', 'Rolls-Royce Holdings PLC' -> 'ROLLS-ROYCE' (pour dédoublonner)."""
    import re
    words = []
    for raw in str(name).upper().replace(",", " ").split():
        key = raw.replace(".", "").replace("/", "")
        if key in _NAME_NOISE or re.fullmatch(r"[\d.]+P", raw):  # formes juridiques, "2.5P" (nominal UK)
            continue
        words.append(raw.strip("."))
    return " ".join(words[:2]) if words else str(name).upper()


def peer_region_codes(country) -> list:
    """Zone dans laquelle chercher les pairs : toute l'Europe pour une société européenne, sinon son pays."""
    code = _COUNTRY_CODES.get(country or "")
    if code in _EU_COUNTRIES or code == "lu":
        return list(_EU_COUNTRIES)
    return [code or "us"]


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_industry_universe(industry: str, regions: tuple) -> list:
    """Sociétés de la même industrie et de la même zone (cache 24 h). Lève une erreur si Yahoo bloque."""
    from yfinance import EquityQuery, screen as yf_screen

    region_filter = (
        EquityQuery("is-in", ["region"] + list(regions)) if len(regions) > 1 else EquityQuery("eq", ["region", regions[0]])
    )
    query = EquityQuery("and", [
        region_filter,
        EquityQuery("eq", ["industry", industry]),
        EquityQuery("gt", ["intradaymarketcap", 1_000_000_000]),
    ])
    result = yf_screen(query, sortField="intradaymarketcap", sortAsc=False, size=250)
    return (result or {}).get("quotes", [])


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_fx_to(target: str, currencies: tuple) -> dict:
    """Taux de change vers la devise cible : {"SEK": 0.089, ...} pour convertir en EUR, par exemple."""
    rates = {target: 1.0}
    pairs = {c: f"{c}{target}=X" for c in currencies if c and c != target}
    if not pairs:
        return rates
    raw = yf.download(list(pairs.values()), period="5d", progress=False, group_by="ticker", threads=True)
    for cur, symbol in pairs.items():
        try:
            frame = raw[symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
            last = _latest_valid(frame["Close"])
            if last:
                rates[cur] = float(last)
        except Exception:
            continue
    return rates


def get_fx_to(target: str, currencies) -> dict:
    """Taux de change vers `target`. Les cotations en pence (GBp) sont ramenées en livres en amont."""
    try:
        return _with_retry(_fetch_fx_to, target, tuple(sorted(set(currencies))))
    except Exception:
        return {target: 1.0}


def _amount_ccy(currency) -> str:
    return "GBP" if currency in ("GBp", "GBX") else (currency or "USD")


def suggest_peers(ticker: str, info: dict, n: int = 6) -> list:
    """
    Pairs suggérés : même industrie Yahoo, même zone, cotation principale, multiples disponibles,
    puis les n sociétés à la capitalisation la plus proche (en devise commune).
    Liste vide si l'industrie est inconnue ou si Yahoo bloque (version en ligne).
    """
    industry = info.get("industry")
    if not industry:
        return []
    try:
        quotes = _fetch_industry_universe(industry, tuple(peer_region_codes(info.get("country"))))
    except Exception:
        return []

    own_name = _canonical_name(info.get("shortName") or info.get("longName") or ticker)
    seen = {}
    for q in quotes:
        sym = q.get("symbol", "")
        name = q.get("shortName") or q.get("longName") or sym
        if sym.upper() == ticker.upper() or any(sym.endswith(s) for s in _PEER_EXCLUDED_SUFFIXES):
            continue
        if "XGLO" in name.upper() or "%" in name:
            continue
        if not (q.get("forwardPE") or q.get("trailingPE")):
            continue  # cotation secondaire ou société sans multiples : inutile comme pair
        canon = _canonical_name(name)
        if canon == own_name:
            continue
        vol = q.get("averageDailyVolume3Month") or 0
        if canon not in seen or vol > (seen[canon].get("averageDailyVolume3Month") or 0):
            seen[canon] = q
    candidates = list(seen.values())
    if not candidates:
        return []

    target = _amount_ccy(info.get("currency"))
    fx = get_fx_to(target, [_amount_ccy(q.get("currency")) for q in candidates])
    own_cap = info.get("marketCap")

    def cap_in_target(q):
        rate = fx.get(_amount_ccy(q.get("currency")))
        return (q.get("marketCap") or 0) * rate if rate else None

    scored = []
    for q in candidates:
        cap = cap_in_target(q)
        if not cap:
            continue
        distance = abs(np.log(cap / own_cap)) if own_cap else -cap  # sans cap propre : les plus gros
        scored.append((distance, q["symbol"]))
    scored.sort()
    shortlist = [sym for _, sym in scored[: n * 3]]

    # Les cotations secondaires de sociétés étrangères (ex : L3Harris cotée à Francfort en .DE)
    # passent les filtres ci-dessus : on vérifie le pays de chaque société dans son profil.
    zone = set(peer_region_codes(info.get("country")))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        profiles = list(pool.map(_raw_profile, shortlist))
    # Une seule ligne par société : les actions ordinaires et préférentielles (VOW.DE / VOW3.DE)
    # ont des noms courts différents mais le même nom officiel.
    seen_companies = {_canonical_name(info.get("longName") or info.get("shortName") or ticker)}
    kept = []
    for sym, prof in zip(shortlist, profiles):
        if not prof:
            continue
        country_code = _COUNTRY_CODES.get(prof.get("country") or "")
        if country_code is None or not (country_code in zone or (country_code == "lu" and "fr" in zone)):
            continue
        company = _canonical_name(prof.get("longName") or prof.get("shortName") or sym)
        if company in seen_companies:
            continue
        seen_companies.add(company)
        kept.append(sym)
        if len(kept) == n:
            break
    return kept


PEER_METRICS = {
    # clé interne : (champ Yahoo, libellé, type)
    "pe_fwd":     ("forwardPE", "P/E fwd", "multiple"),
    "pe_ttm":     ("trailingPE", "P/E TTM", "multiple"),
    "ev_ebitda":  ("enterpriseToEbitda", "EV/EBITDA", "multiple"),
    "ev_sales":   ("enterpriseToRevenue", "EV/Sales", "multiple"),
    "rev_growth": ("revenueGrowth", "Croiss. CA", "pct"),
    "eps_growth": ("earningsGrowth", "Croiss. BPA", "pct"),
    "ebitda_m":   ("ebitdaMargins", "Marge EBITDA", "pct"),
    "op_m":       ("operatingMargins", "Marge op.", "pct"),
    "roe":        ("returnOnEquity", "ROE", "pct"),
    "perf_1y":    ("52WeekChange", "Perf 1 an", "pct"),
}


_PROFILE_CACHE = {}       # {ticker: (horodatage, profil)} : évite de tout recharger quand on retire un pair
_PROFILE_TTL = 900        # secondes


def _raw_profile(ticker: str) -> dict:
    """Profil Yahoo brut avec petit cache maison (st.cache_data n'est pas fait pour les threads)."""
    cached = _PROFILE_CACHE.get(ticker)
    if cached and time.time() - cached[0] < _PROFILE_TTL:
        return cached[1]
    try:
        data = yf.Ticker(ticker).info
        profile = dict(data) if isinstance(data, dict) and any(data.get(k) for k in _PROFILE_KEYS) else {}
    except Exception:
        profile = {}
    if profile:  # on ne garde jamais un échec en cache
        _PROFILE_CACHE[ticker] = (time.time(), profile)
    return profile


def _clean_multiple(value):
    """Un multiple négatif (pertes) ou absurde n'a pas de sens en comparaison : None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value) if 0 < value < 200 else None


@st.cache_data(ttl=900, show_spinner=False)
def get_peer_table(tickers: tuple, base_currency: str) -> pd.DataFrame:
    """
    Une ligne par société (la première est la société analysée) avec capitalisation
    convertie en `base_currency`, multiples, croissance, marges et levier.
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        profiles = list(pool.map(_raw_profile, tickers))

    target = _amount_ccy(base_currency)
    fx = get_fx_to(target, [_amount_ccy(p.get("currency")) for p in profiles if p])

    rows = []
    for ticker, p in zip(tickers, profiles):
        if not p:
            rows.append({"ticker": ticker, "name": ticker, "available": False})
            continue
        rate = fx.get(_amount_ccy(p.get("currency")))
        cap = p.get("marketCap")
        row = {
            "ticker": ticker,
            "name": p.get("shortName") or p.get("longName") or ticker,
            "country": p.get("country"),
            "available": True,
            "market_cap": cap * rate if cap and rate else None,
        }
        for key, (field, _, kind) in PEER_METRICS.items():
            value = p.get(field)
            row[key] = _clean_multiple(value) if kind == "multiple" else (
                float(value) if value is not None and not (isinstance(value, float) and pd.isna(value)) else None
            )
        debt, cash, ebitda = p.get("totalDebt"), p.get("totalCash"), p.get("ebitda")
        row["net_debt_ebitda"] = ((debt or 0) - (cash or 0)) / ebitda if ebitda and ebitda > 0 and debt is not None else None
        rows.append(row)
    return pd.DataFrame(rows)


def peer_medians(table: pd.DataFrame) -> dict:
    """Médiane de chaque indicateur sur les pairs (hors société analysée, première ligne)."""
    peers = table.iloc[1:]
    if "available" in peers:
        peers = peers[peers["available"]]
    medians = {}
    for key in list(PEER_METRICS.keys()) + ["net_debt_ebitda", "market_cap"]:
        if key in peers:
            series = pd.to_numeric(peers[key], errors="coerce").dropna()
            if len(series) >= 2:
                medians[key] = float(series.median())
    medians["_count"] = int(len(peers))
    return medians


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
