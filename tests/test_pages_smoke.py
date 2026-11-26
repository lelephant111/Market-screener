"""
Tests de fumée : chaque page doit s'afficher sans planter, que Yahoo réponde
normalement ("ok") ou qu'il bloque les requêtes comme sur Streamlit Cloud ("blocked").

Aucune requête réseau : yfinance et requests sont remplacés par de fausses données.
Lancement : python -m pytest -q
"""
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from yfinance.exceptions import YFRateLimitError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Niveaux de prix réalistes par symbole (les taux sont en %, comme chez Yahoo)
LEVELS = {"^TNX": 4.4, "^IRX": 4.0, "^FVX": 4.1, "^TYX": 4.7, "^VIX": 18.0, "^VIX3M": 20.0}


def fake_ohlcv(symbol: str, days: int = 260) -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(symbol)) % 2**32)
    base = LEVELS.get(symbol, 100.0)
    close = base * np.exp(np.cumsum(rng.normal(0.0004, 0.01, days)))
    idx = pd.bdate_range(end="2026-11-25", periods=days)
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, days),
        },
        index=idx,
    )


def fake_download(tickers, period="1mo", group_by="column", **kwargs):
    symbols = [tickers] if isinstance(tickers, str) else list(tickers)
    frames = {s: fake_ohlcv(s) for s in symbols}
    if group_by == "ticker":
        return pd.concat(frames, axis=1)  # colonnes (ticker, champ)
    out = pd.concat(frames, axis=1).swaplevel(0, 1, axis=1)  # colonnes (champ, ticker)
    return out.sort_index(axis=1)


class FakeFastInfo:
    def __init__(self, symbol):
        hist = fake_ohlcv(symbol)
        self.last_price = float(hist["Close"].iloc[-1])
        self.previous_close = float(hist["Close"].iloc[-2])
        self.market_cap = 50e9
        self.currency = "EUR" if symbol.endswith(".PA") else "USD"
        self.year_high = float(hist["High"].max())
        self.year_low = float(hist["Low"].min())


def make_ticker_class(mode: str):
    blocked = mode == "blocked"

    def _blocked():
        raise YFRateLimitError()

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            if blocked:
                _blocked()
            return {
                "longName": f"{self.symbol} Corp", "sector": "Industrials", "industry": "Aerospace",
                "currency": "EUR" if self.symbol.endswith(".PA") else "USD",
                "exchange": "PAR", "currentPrice": 233.9, "previousClose": 230.0,
                "trailingPE": 25.0, "forwardPE": 21.0, "enterpriseToEbitda": 14.0,
                "marketCap": 48e9, "totalRevenue": 22e9, "grossMargins": 0.26,
                "profitMargins": 0.076, "returnOnEquity": 0.21, "revenueGrowth": 0.07,
                "earningsGrowth": 0.12, "debtToEquity": 77.0, "currentRatio": 0.9,
                "targetMeanPrice": 260.0, "recommendationKey": "buy",
            }

        @property
        def fast_info(self):
            return FakeFastInfo(self.symbol)

        @property
        def recommendations(self):
            if blocked:
                _blocked()
            return pd.DataFrame([{"period": "0m", "strongBuy": 5, "buy": 8, "hold": 4, "sell": 1, "strongSell": 0}])

        @property
        def earnings_history(self):
            if blocked:
                _blocked()
            idx = pd.to_datetime(["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"])
            return pd.DataFrame(
                {"epsActual": [2.0, 2.1, 2.3, 2.4], "epsEstimate": [1.9, 2.1, 2.2, 2.5],
                 "surprisePercent": [0.05, 0.0, 0.045, -0.04]},
                index=idx,
            )

        @property
        def insider_transactions(self):
            if blocked:
                _blocked()
            today = pd.Timestamp.today().normalize()
            return pd.DataFrame({
                "Shares": [10_000, 2_000],
                "Value": [2_300_000, 460_000],
                "Text": ["Sale at price 230.00 per share.", "Purchase at price 230.00 per share."],
                "Insider": ["DOE JOHN", "SMITH JANE"],
                "Position": ["CEO", "Director"],
                "Transaction": ["", ""],
                "Start Date": [today - pd.Timedelta(days=10), today - pd.Timedelta(days=20)],
                "Ownership": ["D", "D"],
            })

        @property
        def calendar(self):
            if blocked:
                _blocked()
            return {"Earnings Date": [pd.Timestamp("2027-02-25")], "Revenue Average": 6e9}

        @property
        def financials(self):
            cols = pd.to_datetime(["2025-12-31", "2024-12-31"])
            return pd.DataFrame(
                {cols[0]: [22e9, 5.8e9, 2.2e9, 1.7e9, 3.4e9, 8.1],
                 cols[1]: [20.5e9, 5.3e9, 2.0e9, 1.4e9, 3.1e9, 7.0]},
                index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "EBITDA", "Diluted EPS"],
            )

        @property
        def balance_sheet(self):
            cols = pd.to_datetime(["2025-12-31"])
            return pd.DataFrame(
                {cols[0]: [6.1e9, 8e9, 40e9, 4.5e9, 20e9, 23e9]},
                index=["Total Debt", "Stockholders Equity", "Total Assets",
                       "Cash Cash Equivalents And Short Term Investments", "Current Assets", "Current Liabilities"],
            )

        @property
        def cashflow(self):
            cols = pd.to_datetime(["2025-12-31"])
            return pd.DataFrame({cols[0]: [2.5e9]}, index=["Free Cash Flow"])

        def history(self, period="1y", **kwargs):
            return fake_ohlcv(self.symbol)

    return FakeTicker


def make_screen(mode: str):
    def fake_screen(query, sortField=None, sortAsc=None, size=None, **kwargs):
        assert size is None or size <= 250, "Yahoo refuse les requêtes > 250 résultats"
        if mode == "blocked":
            raise YFRateLimitError()
        return {"quotes": [
            {"symbol": f"T{i}.PA", "shortName": f"Societe {i}", "regularMarketPrice": 10.0 + i,
             "regularMarketChangePercent": 0.5 - i * 0.1, "marketCap": (i + 1) * 1e9,
             "trailingPE": 12.0 + i, "forwardPE": 11.0, "fiftyTwoWeekChangePercent": 0.1,
             "averageDailyVolume3Month": 1e6, "currency": "EUR"}
            for i in range(10)
        ]}
    return fake_screen


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def fake_requests_get(url, params=None, **kwargs):
    if "finance/search" in url:
        q = (params or {}).get("q", "").upper()
        return FakeResponse({"quotes": [{"symbol": q, "shortname": f"{q} Corp", "quoteType": "EQUITY"}]})
    raise ConnectionError("pas de réseau dans les tests")  # Fear & Greed CNN -> proxy interne


@pytest.fixture(params=["ok", "blocked"])
def yahoo(request):
    mode = request.param
    import data  # noqa: F401  (chargé ici pour pouvoir neutraliser ses pauses de retry)
    st.cache_data.clear()
    with mock.patch("yfinance.Ticker", make_ticker_class(mode)), \
         mock.patch("yfinance.download", side_effect=fake_download), \
         mock.patch("yfinance.screen", side_effect=make_screen(mode)), \
         mock.patch("requests.get", side_effect=fake_requests_get), \
         mock.patch("data.time"):
        yield mode
    st.cache_data.clear()


def run_page(name: str, **state) -> AppTest:
    at = AppTest.from_file(str(ROOT / "pages" / name), default_timeout=60)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error]
    return "\n".join(str(p) for p in parts)


def test_home(yahoo):
    run_page("home.py")


def test_stock_analysis(yahoo):
    at = run_page("stock_analysis.py", selected_ticker="HO.PA")
    price = at.metric[0]
    assert price.delta and "+0.00 (+0.00%)" not in price.delta, "la variation du jour doit être calculée"
    has_warning = any("Données partielles" in w.value for w in at.warning)
    assert has_warning == (yahoo == "blocked")
    # Thales cote en euros : le prix ne doit pas s'afficher en dollars
    assert price.value.startswith("€"), price.value
    text = all_text(at)
    if yahoo == "ok":
        assert "Net Seller" in text  # 10 000 titres vendus contre 2 000 achetés sur 3 mois
    else:
        assert "Pas de données" in text  # rating Value sans aucun multiple : N/A, pas "C Neutral"


def test_market_overview(yahoo):
    at = run_page("market_overview.py")
    text = all_text(at)
    # Les taux doivent rester en % : un 10 ans autour de 4 %, pas 0,4 %
    assert "10Y Treasury" in text
    row = text.split("10Y Treasury")[1][:300]
    assert ">4." in row or ">5." in row, row
    indices = at.dataframe[0].value
    assert indices["Index"].iloc[0] == "S&P 500 (SPY)"  # prix d'ETF, clairement étiqueté


def test_screener(yahoo):
    at = AppTest.from_file(str(ROOT / "pages" / "screener.py"), default_timeout=60)
    at.run()
    at.selectbox[3].set_value(200)  # Europe + 200 résultats : dépassait la limite Yahoo
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    if yahoo == "blocked":
        assert any("refuse les requêtes" in e.value for e in at.error)
    else:
        assert not at.error
        assert at.dataframe


def test_relative_performance(yahoo):
    run_page("relative_performance.py")


def test_watchlist(yahoo, tmp_path, monkeypatch):
    import data
    wl = tmp_path / "watchlist.json"
    wl.write_text('["AAPL", "AIR.PA"]')
    monkeypatch.setattr(data, "WATCHLIST_FILE", wl)
    run_page("watchlist.py")
