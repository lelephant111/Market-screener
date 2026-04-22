# utils.py — Fonctions de formatage
# Ce fichier contient uniquement des fonctions qui transforment des nombres bruts
# en texte lisible. Rien de spécifique à Streamlit ou aux données financières ici.


def fmt(val, suffix="", prefix="", decimals=2):
    """Formate un nombre simple. Retourne 'N/A' si la valeur est absente ou NaN."""
    if val is None or (isinstance(val, float) and val != val):  # val != val détecte NaN
        return "N/A"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def fmt_pct(val, already_pct=False):
    """
    Formate un pourcentage.
    - Si already_pct=False (défaut) : 0.25 → '25.0%'  (yfinance renvoie souvent des décimales)
    - Si already_pct=True           : 25.0 → '25.0%'  (la valeur est déjà en %)
    """
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    if already_pct:
        return f"{val:.1f}%"
    return f"{val * 100:.1f}%"


def fmt_large(val):
    """
    Formate les grands nombres financiers avec suffixe lisible.
    Exemples : 2 500 000 000 → '$2.50B', 1 200 000 → '$1.20M'
    """
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    if val >= 1e12:
        return f"${val / 1e12:.2f}T"
    if val >= 1e9:
        return f"${val / 1e9:.2f}B"
    if val >= 1e6:
        return f"${val / 1e6:.2f}M"
    return f"${val:,.0f}"


def fmt_price(val):
    """Formate un prix avec 2 décimales et signe $."""
    if val is None or (isinstance(val, float) and val != val):
        return "N/A"
    return f"${val:.2f}"


def color_delta(val):
    """Retourne la couleur CSS selon que la valeur est positive ou négative."""
    if val is None:
        return "gray"
    return "#00c853" if val >= 0 else "#ff1744"


# -------------------------------------------------------
# ZACKS-STYLE RATINGS — Value / Growth / Momentum / VGM
# -------------------------------------------------------

def _to_grade(score: float) -> str:
    """
    Convertit un score 0-100 en grade lettre Zacks.
    A = top 20%  (80-100)
    B = next 20% (60-79)
    C = middle   (40-59)
    D = next 20% (20-39)
    F = bottom   (0-19)
    """
    if score >= 80: return 'A'
    if score >= 60: return 'B'
    if score >= 40: return 'C'
    if score >= 20: return 'D'
    return 'F'


def compute_zacks_ratings(info: dict, df_ta=None, earnings_h=None) -> dict:
    """
    Calcule les 4 ratings Zacks-style : Value, Growth, Momentum, VGM.

    Paramètres :
      info      : dict yfinance (fondamentaux)
      df_ta     : DataFrame avec indicateurs techniques (optionnel, pour Momentum)
      earnings_h: DataFrame earnings history (optionnel, pour surprise EPS)

    Retourne :
      { 'value':    {'grade': 'B', 'score': 65},
        'growth':   {'grade': 'A', 'score': 82},
        'momentum': {'grade': 'C', 'score': 51},
        'vgm':      {'grade': 'B', 'score': 66} }
    """

    # ── VALUE ────────────────────────────────────────────────────────────
    # Zacks Value : compare P/E, P/S, P/B, EV/EBITDA aux moyennes historiques.
    # Multiples bas = meilleure note.
    v = []

    pe = info.get('trailingPE')
    if pe and 0 < pe < 200:
        v.append(90 if pe < 12 else 75 if pe < 17 else 60 if pe < 22
                 else 45 if pe < 28 else 28 if pe < 35 else 12)

    fpe = info.get('forwardPE')
    if fpe and 0 < fpe < 200:
        v.append(90 if fpe < 12 else 75 if fpe < 17 else 60 if fpe < 22
                 else 45 if fpe < 28 else 28 if fpe < 35 else 12)

    ps = info.get('priceToSalesTrailing12Months')
    if ps and ps > 0:
        v.append(90 if ps < 1 else 75 if ps < 2 else 60 if ps < 4
                 else 40 if ps < 8 else 22 if ps < 15 else 10)

    pb = info.get('priceToBook')
    if pb and pb > 0:
        v.append(88 if pb < 1.5 else 70 if pb < 3 else 55 if pb < 5
                 else 38 if pb < 8 else 18)

    ev_eb = info.get('enterpriseToEbitda')
    if ev_eb and 0 < ev_eb < 100:
        v.append(90 if ev_eb < 8 else 75 if ev_eb < 12 else 58 if ev_eb < 18
                 else 38 if ev_eb < 25 else 15)

    v_score = round(sum(v) / len(v)) if v else 50

    # ── GROWTH ───────────────────────────────────────────────────────────
    # Zacks Growth : croissance passée + forward EPS growth + surprise récente.
    g = []

    rev_g = info.get('revenueGrowth')
    if rev_g is not None:
        rg = rev_g * 100
        g.append(90 if rg > 30 else 80 if rg > 20 else 65 if rg > 10
                 else 55 if rg > 5 else 45 if rg > 0 else 28 if rg > -5 else 12)

    earn_g = info.get('earningsGrowth')
    if earn_g is not None:
        eg = earn_g * 100
        g.append(90 if eg > 30 else 80 if eg > 20 else 65 if eg > 10
                 else 50 if eg > 0 else 28 if eg > -10 else 12)

    # Forward EPS growth vs TTM EPS — indicateur clé chez Zacks
    t_eps = info.get('trailingEps')
    f_eps = info.get('forwardEps')
    if t_eps and f_eps and t_eps > 0:
        fwd_g = (f_eps - t_eps) / abs(t_eps) * 100
        g.append(90 if fwd_g > 20 else 75 if fwd_g > 10 else 60 if fwd_g > 5
                 else 50 if fwd_g > 0 else 30)

    # Surprise EPS du dernier trimestre (surprisePercent est en décimal dans yfinance)
    if earnings_h is not None and not earnings_h.empty:
        try:
            sp = earnings_h['surprisePercent'].dropna().iloc[-1] * 100
            g.append(90 if sp > 10 else 80 if sp > 5 else 68 if sp > 2
                     else 55 if sp > 0 else 32 if sp > -3 else 15)
        except Exception:
            pass

    g_score = round(sum(g) / len(g)) if g else 50

    # ── MOMENTUM ─────────────────────────────────────────────────────────
    # Zacks Momentum : retour prix court terme + révisions d'estimations.
    m = []

    if df_ta is not None and not df_ta.empty:
        close = df_ta['Close']
        last  = close.iloc[-1]

        # Retour 4 semaines (≈20 jours de bourse)
        if len(close) >= 20:
            r4 = (last - close.iloc[-20]) / close.iloc[-20] * 100
            m.append(90 if r4 > 10 else 75 if r4 > 5 else 60 if r4 > 2
                     else 50 if r4 > 0 else 32 if r4 > -5 else 12)

        # Retour 12 semaines (≈60 jours)
        if len(close) >= 60:
            r12 = (last - close.iloc[-60]) / close.iloc[-60] * 100
            m.append(90 if r12 > 20 else 75 if r12 > 10 else 60 if r12 > 5
                     else 50 if r12 > 0 else 32 if r12 > -10 else 12)

        # Position vs MA50 — tendance intermédiaire
        ma50 = df_ta['MA50'].dropna()
        if len(ma50) > 0:
            pct = (last - ma50.iloc[-1]) / ma50.iloc[-1] * 100
            m.append(88 if pct > 10 else 72 if pct > 5 else 58 if pct > 0
                     else 40 if pct > -5 else 20)

    # Momentum des surprises EPS (2 derniers trimestres — en décimal dans yfinance)
    if earnings_h is not None and not earnings_h.empty:
        try:
            sps = earnings_h['surprisePercent'].dropna().tail(2).tolist()
            if sps:
                avg = sum(sps) / len(sps) * 100
                m.append(88 if avg > 5 else 72 if avg > 2 else 55 if avg > 0 else 28)
        except Exception:
            pass

    m_score = round(sum(m) / len(m)) if m else 50

    # ── VGM ──────────────────────────────────────────────────────────────
    # Zacks VGM = moyenne pondérée Value + Growth + Momentum
    vgm_score = round((v_score + g_score + m_score) / 3)

    return {
        'value':    {'grade': _to_grade(v_score),   'score': v_score},
        'growth':   {'grade': _to_grade(g_score),   'score': g_score},
        'momentum': {'grade': _to_grade(m_score),   'score': m_score},
        'vgm':      {'grade': _to_grade(vgm_score), 'score': vgm_score},
    }


# -------------------------------------------------------
# SCORECARD — Calcul des 5 scores sur 10
# -------------------------------------------------------

def _weighted_avg(scores_weights):
    """
    Calcule la moyenne pondérée d'une liste de (score, poids).
    Ignore les entrées None. Retourne None si aucune donnée.
    """
    valid = [(s, w) for s, w in scores_weights if s is not None]
    if not valid:
        return None
    total = sum(s * w for s, w in valid)
    weight = sum(w for _, w in valid)
    return round(total / weight, 1)


def compute_scores(info: dict, df_ta=None) -> dict:
    """
    Calcule 5 scores sur 10 pour un stock.

    Paramètres :
      info  : dict retourné par yfinance (fondamentaux)
      df_ta : DataFrame avec les indicateurs techniques (optionnel, pour Momentum)

    Retourne un dict avec 5 clés :
      valuation, quality, growth, momentum, financial_health
    Chaque valeur : { 'score': float|None, 'label': str, 'icon': str, 'details': list[str] }
    """

    # ── 1. VALORISATION ─────────────────────────────────────────────────────
    # Plus les multiples sont bas, mieux c'est (action pas chère)
    v, dv = [], []

    pe = info.get('trailingPE')
    if pe and 0 < pe < 200:  # on ignore les P/E aberrants (pertes, distorsions)
        s = 10 if pe < 15 else 8 if pe < 20 else 6 if pe < 25 else 3 if pe < 35 else 1
        v.append((s, 2)); dv.append(f"P/E {pe:.1f}x")

    fpe = info.get('forwardPE')
    if fpe and 0 < fpe < 200:
        s = 10 if fpe < 15 else 8 if fpe < 20 else 6 if fpe < 25 else 3 if fpe < 35 else 1
        v.append((s, 2)); dv.append(f"Fwd P/E {fpe:.1f}x")

    ev_ebitda = info.get('enterpriseToEbitda')
    if ev_ebitda and 0 < ev_ebitda < 100:
        s = 10 if ev_ebitda < 10 else 7 if ev_ebitda < 15 else 5 if ev_ebitda < 20 else 2
        v.append((s, 2)); dv.append(f"EV/EBITDA {ev_ebitda:.1f}x")

    peg = info.get('pegRatio')
    if peg and 0 < peg < 10:
        s = 10 if peg < 1 else 7 if peg < 1.5 else 5 if peg < 2 else 2
        v.append((s, 1)); dv.append(f"PEG {peg:.2f}")

    ps = info.get('priceToSalesTrailing12Months')
    if ps and ps > 0:
        s = 10 if ps < 2 else 7 if ps < 5 else 4 if ps < 10 else 1
        v.append((s, 1)); dv.append(f"P/S {ps:.1f}x")

    scores_out = {}
    scores_out['valuation'] = {'score': _weighted_avg(v), 'label': 'Valorisation', 'details': dv}

    # ── 2. QUALITÉ ───────────────────────────────────────────────────────────
    # Mesure la capacité de l'entreprise à générer du profit durablement
    q, dq = [], []

    gm = info.get('grossMargins')
    if gm is not None:
        g = gm * 100
        s = 10 if g > 60 else 8 if g > 40 else 6 if g > 25 else 4 if g > 10 else 2
        q.append((s, 1)); dq.append(f"Gross margin {g:.0f}%")

    nm = info.get('profitMargins')
    if nm is not None:
        n = nm * 100
        s = 10 if n > 20 else 8 if n > 10 else 6 if n > 5 else 4 if n > 0 else 1
        q.append((s, 2)); dq.append(f"Net margin {n:.0f}%")

    roe = info.get('returnOnEquity')
    if roe is not None:
        r = roe * 100
        s = 10 if r > 25 else 8 if r > 15 else 6 if r > 10 else 4 if r > 5 else 2
        q.append((s, 2)); dq.append(f"ROE {r:.0f}%")

    roa = info.get('returnOnAssets')
    if roa is not None:
        r = roa * 100
        s = 10 if r > 12 else 8 if r > 7 else 6 if r > 4 else 3
        q.append((s, 1)); dq.append(f"ROA {r:.0f}%")

    scores_out['quality'] = {'score': _weighted_avg(q), 'label': 'Qualité', 'details': dq}

    # ── 3. CROISSANCE ────────────────────────────────────────────────────────
    # Est-ce que l'entreprise grandit ? À quelle vitesse ?
    g, dg = [], []

    rev_g = info.get('revenueGrowth')
    if rev_g is not None:
        rg = rev_g * 100
        s = 10 if rg > 30 else 8 if rg > 20 else 6 if rg > 10 else 4 if rg > 5 else 2 if rg > 0 else 1
        g.append((s, 2)); dg.append(f"Rev. growth {rg:+.0f}%")

    earn_g = info.get('earningsGrowth')
    if earn_g is not None:
        eg = earn_g * 100
        s = 10 if eg > 30 else 8 if eg > 20 else 6 if eg > 10 else 4 if eg > 0 else 1
        g.append((s, 2)); dg.append(f"EPS growth {eg:+.0f}%")

    scores_out['growth'] = {'score': _weighted_avg(g), 'label': 'Croissance', 'details': dg}

    # ── 4. MOMENTUM ──────────────────────────────────────────────────────────
    # La tendance du prix : est-ce que le marché est avec nous ou contre nous ?
    m, dm = [], []

    if df_ta is not None and not df_ta.empty:
        last_close = df_ta['Close'].iloc[-1]

        # Position par rapport à la MA200
        ma200 = df_ta['MA200'].dropna()
        if len(ma200) > 0:
            pct = ((last_close - ma200.iloc[-1]) / ma200.iloc[-1]) * 100
            s = 10 if pct > 10 else 8 if pct > 5 else 6 if pct > 0 else 4 if pct > -5 else 2
            m.append((s, 3))
            dm.append(f"{'▲' if pct > 0 else '▼'} MA200 ({pct:+.1f}%)")

        # RSI : idéal entre 50 et 65 (tendance haussière sans surachat)
        rsi_s = df_ta['RSI'].dropna()
        if len(rsi_s) > 0:
            r = rsi_s.iloc[-1]
            s = 10 if 50 <= r <= 65 else 7 if (40 <= r < 50 or 65 < r <= 70) else 5 if 30 <= r < 40 else 3 if r > 70 else 2
            m.append((s, 2))
            dm.append(f"RSI {r:.0f}")

        # Position dans le range 52 semaines
        roll_max = df_ta['Close'].rolling(252, min_periods=50).max().iloc[-1]
        roll_min = df_ta['Close'].rolling(252, min_periods=50).min().iloc[-1]
        if roll_max and roll_min and roll_max != roll_min:
            pos = (last_close - roll_min) / (roll_max - roll_min) * 100
            s = 10 if pos > 80 else 8 if pos > 60 else 6 if pos > 40 else 3
            m.append((s, 1))
            dm.append(f"Range 52w: {pos:.0f}%")

    scores_out['momentum'] = {'score': _weighted_avg(m), 'label': 'Momentum', 'details': dm}

    # ── 5. SANTÉ FINANCIÈRE ──────────────────────────────────────────────────
    # Est-ce que l'entreprise peut survivre à un choc ? Trop de dette = risque
    h, dh = [], []

    de = info.get('debtToEquity')
    if de is not None:
        # D/E en % chez yfinance (ex: 150 = 150%)
        s = 10 if de < 30 else 8 if de < 60 else 6 if de < 100 else 4 if de < 150 else 2
        h.append((s, 3)); dh.append(f"D/E {de:.0f}%")

    cr = info.get('currentRatio')
    if cr is not None:
        s = 10 if cr > 2 else 8 if cr > 1.5 else 6 if cr > 1 else 3
        h.append((s, 2)); dh.append(f"Current ratio {cr:.1f}")

    fcf = info.get('freeCashflow')
    if fcf is not None:
        s = 8 if fcf > 0 else 2
        h.append((s, 1)); dh.append(f"FCF {'✓' if fcf > 0 else '✗'}")

    scores_out['financial_health'] = {'score': _weighted_avg(h), 'label': 'Santé Fin.', 'details': dh}

    return scores_out
