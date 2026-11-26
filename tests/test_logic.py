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


# ── Lot 4 : pairs et ratings relatifs ───────────────────────────────────

def test_scores_relatifs_aux_pairs():
    from utils import premium_score, relative_spread, relative_value, spread_score, GROWTH_VS_PEERS
    assert premium_score(-0.25) == 75      # P/E 15x vs 20x : décote de 25 %
    assert premium_score(0.0) == 50
    assert premium_score(0.40) == 12
    assert spread_score(6) == 75           # marge 18 % vs 12 % : +6 pts
    assert spread_score(-12) == 12
    info = {"forwardPE": 15.0, "enterpriseToEbitda": 10.0, "revenueGrowth": 0.12}
    medians = {"pe_fwd": 20.0, "ev_ebitda": 10.0, "rev_growth": 0.06}
    assert [s for s, _ in relative_value(info, medians)] == [75, 50]
    assert relative_spread(info, medians, GROWTH_VS_PEERS)[0][0] == 75


def test_ratings_utilisent_les_pairs():
    info = {"forwardPE": 30.0, "trailingPE": 35.0}
    absolu = compute_zacks_ratings(info)["value"]["score"]
    vs_pairs = compute_zacks_ratings(info, peer_medians={"pe_fwd": 45.0, "pe_ttm": 50.0})["value"]["score"]
    assert absolu < 40 < vs_pairs  # 30x paraît cher dans l'absolu, mais c'est une décote de 33 % vs les pairs


def test_noms_canoniques_pour_dedoublonner():
    from data import _canonical_name
    assert _canonical_name("ROLLS-ROYCE HOLDINGS PLC ORD") == _canonical_name("Rolls-Royce Holdings PLC")
    assert _canonical_name("BAE SYSTEMS PLC ORD 2.5P") == "BAE SYSTEMS"
    assert _canonical_name("Thales S.A.") == _canonical_name("THALES")


def test_zone_de_recherche_des_pairs():
    from data import peer_region_codes
    assert "gb" in peer_region_codes("France") and "de" in peer_region_codes("France")
    assert peer_region_codes("United States") == ["us"]
    assert peer_region_codes("Japan") == ["jp"]


def test_suggestion_de_pairs_filtre_et_classe(monkeypatch):
    import data
    quotes = [
        {"symbol": "RHM.DE", "shortName": "Rheinmetall AG", "marketCap": 36e9, "currency": "EUR", "forwardPE": 30},
        {"symbol": "BA.L", "shortName": "BAE SYSTEMS PLC ORD 2.5P", "marketCap": 55e9, "currency": "GBp", "forwardPE": 20},
        {"symbol": "BAL.XC", "shortName": "BAE Systems PLC", "marketCap": 55e9, "currency": "GBp"},   # Cboe : écarté
        {"symbol": "GCP.F", "shortName": "GE Aerospace", "marketCap": 300e9, "currency": "EUR"},       # Francfort : écarté
        {"symbol": "RHM.WA", "shortName": "RHM C.XGLO PLN", "marketCap": 162e9, "currency": "PLN", "forwardPE": 30},
        {"symbol": "SAAB-B.ST", "shortName": "SAAB AB ser. B", "marketCap": 338e9, "currency": "SEK", "forwardPE": 60},
        {"symbol": "SPX.DE", "shortName": "Space Exploration Techs", "marketCap": 1600e9, "currency": "EUR"},  # sans P/E
        {"symbol": "HO.PA", "shortName": "THALES", "marketCap": 48e9, "currency": "EUR", "forwardPE": 21},     # lui-même
        {"symbol": "AIR.PA", "shortName": "AIRBUS", "marketCap": 160e9, "currency": "EUR", "forwardPE": 25},
    ]
    monkeypatch.setattr(data, "_fetch_industry_universe", lambda industry, regions: quotes)
    monkeypatch.setattr(data, "get_fx_to", lambda target, currencies: {"EUR": 1.0, "GBP": 1.19, "SEK": 0.089, "PLN": 0.22})
    countries = {"RHM.DE": "Germany", "BA.L": "United Kingdom", "SAAB-B.ST": "Sweden", "AIR.PA": "France",
                 "HRS.DE": "United States"}
    monkeypatch.setattr(data, "_raw_profile", lambda t: {"country": countries.get(t), "shortName": t})
    quotes.append({"symbol": "HRS.DE", "shortName": "L3Harris Technologies Inc.    R", "marketCap": 47e9,
                   "currency": "EUR", "trailingPE": 25})  # société US cotée à Francfort : écartée par le pays
    info = {"industry": "Aerospace & Defense", "country": "France", "currency": "EUR", "marketCap": 48e9, "shortName": "Thales S.A."}
    peers = data.suggest_peers("HO.PA", info, n=3)
    # BAE 65 Md€ et Rheinmetall 36 Md€ sont les plus proches de 48 Md€, puis Saab (30 Md€)
    assert peers == ["RHM.DE", "BA.L", "SAAB-B.ST"]
    assert not {"BAL.XC", "GCP.F", "RHM.WA", "SPX.DE", "HO.PA", "HRS.DE"} & set(data.suggest_peers("HO.PA", info, n=10))
