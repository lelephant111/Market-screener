"""Tests unitaires des calculs et formats corrigés au lot 2."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from charts import earnings_chart, profitability_chart, scorecard_chart  # noqa: E402
from data import compute_indicators  # noqa: E402
from data import _EU_COUNTRIES, _EU_EX_UK_COUNTRIES, _clean_screener_quotes, is_yahoo_blocked_error  # noqa: E402
from utils import compute_scores, compute_zacks_ratings, fmt_large, fmt_price  # noqa: E402


def test_montants_negatifs_et_devises():
    assert fmt_large(-1.5e9, "USD") == "-$1.50B"
    assert fmt_large(48.1e9, "EUR") == "€48.10B"
    assert fmt_large(2e9, "GBp") == "£2.00B"  # cours en pence, montants en livres
    assert fmt_price(233.9, "EUR") == "€233.90"
    assert fmt_price(1234.5, "GBp") == "1,234.50p"
    assert fmt_price(None, "EUR") == "N/A"


def test_ratings_sans_donnees_ne_sont_pas_neutres():
    zacks = compute_zacks_ratings({}, None, None)
    assert zacks["value"]["grade"] == "N/A" and zacks["value"]["score"] is None
    assert zacks["vgm"]["score"] is None
    fig = scorecard_chart(compute_scores({}, None))
    assert all(t == "N/A" for t in fig.data[0].text)


def test_profitabilite_absente_affiche_na():
    fig = profitability_chart(0.26, None, 0.076, None, 0.04)
    assert list(fig.data[0].text) == ["4.0%", "N/A", "7.6%", "N/A", "26.0%"]


def test_surprise_eps_en_pourcentage():
    idx = pd.to_datetime(["2026-03-31", "2026-06-30"])
    df = pd.DataFrame({"epsActual": [2.1, 2.3], "epsEstimate": [2.0, 2.2], "surprisePercent": [0.05, 0.045]}, index=idx)
    actual_bar = earnings_chart(df).data[1]
    assert list(actual_bar.text) == ["+5.0%", "+4.5%"]  # et non +0.1 %


def test_europe_inclut_le_royaume_uni():
    assert "gb" in _EU_COUNTRIES and "gb" not in _EU_EX_UK_COUNTRIES


def test_tri_du_screener_respecte():
    quotes = [
        {"symbol": "A", "shortName": "Alpha", "marketCap": 9e9, "regularMarketChangePercent": -1.0},
        {"symbol": "B", "shortName": "Beta", "marketCap": 1e9, "regularMarketChangePercent": 4.0},
        {"symbol": "C", "shortName": "Gamma", "marketCap": 5e9, "regularMarketChangePercent": 2.0},
    ]
    by_change = _clean_screener_quotes(quotes, sort_field="percentchange")
    assert [q["symbol"] for q in by_change] == ["B", "C", "A"]
    by_cap = _clean_screener_quotes(quotes, sort_field="intradaymarketcap")
    assert [q["symbol"] for q in by_cap] == ["A", "C", "B"]


def test_erreur_401_reconnue_comme_blocage():
    assert is_yahoo_blocked_error(Exception("HTTP Error 401: "))
    assert is_yahoo_blocked_error(Exception("Too Many Requests. Rate limited."))
    assert not is_yahoo_blocked_error(Exception("ticker inconnu"))


def test_rsi_methode_de_wilder():
    import numpy as np
    rng = np.random.default_rng(7)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 120))))
    df = compute_indicators(pd.DataFrame({"Close": close}))

    # Référence : Wilder "à la main" (moyenne simple des 14 premiers écarts, puis lissage 13/14)
    delta = close.diff().dropna().to_numpy()
    gains, losses = np.clip(delta, 0, None), np.clip(-delta, 0, None)
    avg_g, avg_l = gains[:14].mean(), losses[:14].mean()
    for g, l in zip(gains[14:], losses[14:]):
        avg_g = (avg_g * 13 + g) / 14
        avg_l = (avg_l * 13 + l) / 14
    expected = 100 - 100 / (1 + avg_g / avg_l)
    # ewm(adjust=False) démarre différemment, l'écart disparaît après une centaine de séances
    assert abs(df["RSI"].iloc[-1] - expected) < 0.5
    assert df["RSI"].dropna().between(0, 100).all()


def test_rsi_que_des_hausses_vaut_100():
    close = pd.Series(range(1, 40), dtype=float)
    assert compute_indicators(pd.DataFrame({"Close": close}))["RSI"].iloc[-1] == 100
