# charts.py — Construction des graphiques Plotly
# Ce fichier ne fait que construire et retourner des figures Plotly.
# Il ne fait aucun appel réseau et n'a pas de logique Streamlit.
# C'est app.py qui appelle st.plotly_chart() avec les figures retournées ici.

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# Palette de couleurs cohérente avec la nouvelle UI
COLORS = {
    "bg":      "#0d1726",
    "panel":   "#111d31",
    "blue":    "#7dd3fc",
    "blue2":   "#4f8cff",
    "green":   "#35d399",
    "red":     "#fb7185",
    "orange":  "#f59e0b",
    "amber":   "#fbbf24",
    "gray":    "#203248",
    "grid":    "rgba(143,166,193,0.18)",
    "white":   "#ffffff",
    "text":    "#e6eef8",
    "muted":   "#8fa6c1",
}

# Layout Plotly commun à tous les graphiques
BASE_LAYOUT = dict(
    plot_bgcolor  = COLORS["bg"],
    paper_bgcolor = COLORS["bg"],
    font          = dict(color=COLORS["text"]),
    margin        = dict(l=0, r=0, t=20, b=0),
    legend        = dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
)


def candlestick_chart(history: pd.DataFrame, ticker: str) -> go.Figure:
    """
    Graphique en chandeliers japonais (OHLC).
    history : DataFrame avec colonnes Open, High, Low, Close
    """
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=history.index,
        open=history['Open'],
        high=history['High'],
        low=history['Low'],
        close=history['Close'],
        name=ticker,
        increasing_line_color=COLORS["green"],
        decreasing_line_color=COLORS["red"],
    ))
    fig.update_layout(
        **BASE_LAYOUT,
        height=420,
        xaxis_rangeslider_visible=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"]),
    )
    return fig


def sector_bar_chart(sector_perf: dict) -> go.Figure:
    """
    Graphique à barres horizontal pour la performance sectorielle.
    sector_perf : { "Tech": 1.2, "Finance": -0.3, ... }
    """
    df = pd.DataFrame(list(sector_perf.items()), columns=["Secteur", "Perf (%)"])
    df = df.sort_values("Perf (%)", ascending=True)
    colors = [COLORS["red"] if x < 0 else COLORS["green"] for x in df["Perf (%)"]]

    fig = go.Figure(go.Bar(
        x=df["Perf (%)"],
        y=df["Secteur"],
        orientation='h',
        marker_color=colors,
        text=[f"{x:+.2f}%" for x in df["Perf (%)"]],
        textposition='outside',
    ))
    fig.update_layout(
        **BASE_LAYOUT,
        height=400,
        xaxis=dict(showgrid=False, zeroline=True, zerolinecolor=COLORS["grid"]),
        yaxis=dict(showgrid=False),
    )
    fig.update_layout(margin=dict(l=0, r=70, t=20, b=0))
    return fig


def technical_chart(df: "pd.DataFrame", ticker: str) -> go.Figure:
    """
    Graphique technique multi-panneaux avec :
    - Panneau 1 (60%) : chandeliers + MA20/50/200 + Bandes de Bollinger
    - Panneau 2 (20%) : RSI avec zones surachat/survente
    - Panneau 3 (20%) : MACD avec histogramme

    df : DataFrame retourné par compute_indicators() — doit avoir les colonnes
         MA20, MA50, MA200, BB_upper, BB_lower, RSI, MACD, MACD_signal, MACD_hist
    """
    # make_subplots crée une figure avec plusieurs graphiques empilés
    # shared_xaxes=True : quand tu zoomes sur un panneau, les autres suivent
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20],
        vertical_spacing=0.03,
    )

    # ── Panneau 1 : Chandeliers ──────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name=ticker,
        increasing_line_color=COLORS["green"],
        decreasing_line_color=COLORS["red"],
        showlegend=False,
    ), row=1, col=1)

    # Bandes de Bollinger — zone grisée entre upper et lower
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BB_upper'],
        line=dict(color='rgba(143,166,193,0.35)', width=1, dash='dot'),
        name='BB Upper', showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BB_lower'],
        line=dict(color='rgba(143,166,193,0.35)', width=1, dash='dot'),
        fill='tonexty',  # remplit entre cette courbe et la précédente (BB_upper)
        fillcolor='rgba(125,211,252,0.06)',
        name='BB Lower', showlegend=False,
    ), row=1, col=1)

    # Moyennes Mobiles
    for ma, color, width in [('MA20', COLORS["amber"], 1.2), ('MA50', COLORS["orange"], 1.6), ('MA200', COLORS["red"], 2.1)]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma],
            line=dict(color=color, width=width),
            name=ma,
        ), row=1, col=1)

    # ── Panneau 2 : RSI ──────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI'],
        line=dict(color=COLORS["blue"], width=1.5),
        name='RSI (14)',
    ), row=2, col=1)

    # Lignes horizontales à 70 (surachat) et 30 (survente)
    for level, color in [(70, COLORS["red"]), (30, COLORS["green"]), (50, COLORS["muted"])]:
        fig.add_hline(
            y=level, row=2, col=1,
            line=dict(color=color, width=1, dash='dash'),
        )

    # ── Panneau 3 : MACD ────────────────────────────────────────────────────
    # Histogramme coloré selon qu'il est positif ou négatif
    colors_hist = [COLORS["green"] if v >= 0 else COLORS["red"] for v in df['MACD_hist']]
    fig.add_trace(go.Bar(
        x=df.index, y=df['MACD_hist'],
        marker_color=colors_hist,
        name='MACD Hist',
        showlegend=False,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD'],
        line=dict(color=COLORS["blue"], width=1.5),
        name='MACD',
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD_signal'],
        line=dict(color='#FF9800', width=1.5),
        name='Signal',
    ), row=3, col=1)

    # ── Layout global ────────────────────────────────────────────────────────
    # On applique le layout en deux temps pour éviter le conflit sur la clé 'legend'
    # (BASE_LAYOUT contient déjà 'legend', on ne peut pas le passer deux fois)
    fig.update_layout(**BASE_LAYOUT, height=650, xaxis_rangeslider_visible=False)
    fig.update_layout(legend=dict(
        orientation='h', y=1.02, x=0,
        bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)',
        font=dict(size=11),
    ))
    # Grilles sur chaque panneau
    for row in [1, 2, 3]:
        fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], row=row, col=1)
        fig.update_xaxes(showgrid=False, row=row, col=1)

    # Limiter le RSI entre 0 et 100
    fig.update_yaxes(range=[0, 100], row=2, col=1)

    return fig


def scorecard_chart(scores: dict) -> go.Figure:
    """
    Graphique en barres verticales pour la scorecard (5 dimensions).
    Axe horizontal de référence à 5.0 (score neutre).
    Barres vertes si score > 5, rouges si < 5.
    L'intensité de la couleur augmente avec la distance au centre.
    """
    labels = [d['label'] for d in scores.values()]
    values = [d['score'] if d['score'] is not None else 5.0 for d in scores.values()]

    colors = []
    for v in values:
        intensity = abs(v - 5) / 5      # 0.0 (neutre) → 1.0 (extrême)
        opacity   = 0.35 + 0.65 * intensity
        if v >= 5:
            colors.append(f"rgba(63, 185, 80, {opacity:.2f})")   # vert
        else:
            colors.append(f"rgba(248, 81, 73, {opacity:.2f})")   # rouge

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        marker_line_width=0,
        text=[f"<b>{v:.1f}</b>" for v in values],
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=13),
        hovertemplate="%{x} : %{y}/10<extra></extra>",
    ))

    # Ligne horizontale de référence à 5
    fig.add_hline(y=5, line=dict(color="#555", width=1.5, dash="dot"))

    fig.update_layout(**BASE_LAYOUT, height=220, bargap=0.45)
    fig.update_layout(
        margin=dict(l=0, r=10, t=25, b=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=13)),
        yaxis=dict(showgrid=False, showticklabels=False, range=[0, 12]),
    )
    return fig


def profitability_chart(gross, operating, net, roe, roa) -> go.Figure:
    """
    Graphique horizontal des 5 métriques de profitabilité.
    Inclut les marges (Gross, Operating, Net) + les retours (ROE, ROA).
    Toutes les valeurs sont affichées en % sur le même axe.
    """
    labels = ['ROA', 'ROE', 'Net Margin', 'Operating Margin', 'Gross Margin']
    values = [
        (roa or 0) * 100,
        (roe or 0) * 100,
        (net or 0) * 100,
        (operating or 0) * 100,
        (gross or 0) * 100,
    ]
    colors = [COLORS["green"] if v > 0 else COLORS["red"] for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation='h',
        marker_color=colors,
        marker_line_width=0,
        text=[f"{v:.1f}%" for v in values],
        textposition='outside',
        textfont=dict(size=12, color=COLORS["text"]),
    ))
    min_val = min(values) if values else 0
    max_val = max(values) if values else 10
    left_bound = min(0, min_val * 1.25) if min_val < 0 else 0
    right_bound = max(10, max_val * 1.45) if max_val > 0 else max(10, abs(min_val) * 0.45)
    fig.update_layout(**BASE_LAYOUT, height=200,
        xaxis=dict(showgrid=False, showticklabels=False, range=[left_bound, right_bound]),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
    )
    fig.update_layout(margin=dict(l=0, r=65, t=8, b=0))
    return fig


def earnings_chart(df: "pd.DataFrame") -> go.Figure:
    """
    Graphique des earnings sur les 4 derniers trimestres.
    Deux barres par trimestre : Estimate (gris) et Actual (vert si beat, rouge si miss).
    Le % de surprise est affiché au-dessus de chaque barre Actual.

    df : DataFrame avec colonnes epsActual, epsEstimate, surprisePercent (index = dates)
    """
    df = df.tail(4).copy()
    quarters = [str(d)[:7] for d in df.index]   # format "2024-09"

    actual   = df['epsActual'].tolist()
    estimate = df['epsEstimate'].tolist()
    surprise = df['surprisePercent'].tolist() if 'surprisePercent' in df.columns else [None] * len(df)

    # Couleur de la barre Actual selon beat (vert) ou miss (rouge)
    act_colors = []
    for a, e in zip(actual, estimate):
        if a is None or e is None:
            act_colors.append(COLORS["gray"])
        elif a >= e:
            act_colors.append(COLORS["green"])
        else:
            act_colors.append(COLORS["red"])

    fig = go.Figure()

    # Barre Estimate en fond (semi-transparente)
    fig.add_trace(go.Bar(
        x=quarters, y=estimate,
        name='Estimate',
        marker_color='rgba(139,148,158,0.35)',
        marker_line_width=0,
    ))

    # Barre Actual devant, avec surprise % en annotation
    fig.add_trace(go.Bar(
        x=quarters, y=actual,
        name='Actual',
        marker_color=act_colors,
        marker_line_width=0,
        text=[f"{s:+.1f}%" if s is not None else "" for s in surprise],
        textposition='outside',
        textfont=dict(size=11, color=COLORS["text"]),
    ))

    fig.update_layout(**BASE_LAYOUT, height=230, barmode='overlay')
    fig.update_layout(
        margin=dict(l=0, r=10, t=20, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], title="EPS ($)"),
        legend=dict(orientation='h', y=1.12, x=0, bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
    )
    return fig


def analyst_bar_chart(strong_buy: int, buy: int, hold: int, sell: int, strong_sell: int) -> go.Figure:
    """
    Barre horizontale empilée montrant la répartition des recommandations analystes.
    Les segments sont colorés du vert foncé (Strong Buy) au rouge foncé (Strong Sell).
    """
    categories = ['Strong Buy', 'Buy',         'Hold',    'Sell',        'Strong Sell']
    values     = [strong_buy,   buy,            hold,      sell,           strong_sell]
    colors     = ['#1b6f55',    COLORS["green"], COLORS["orange"], COLORS["red"], '#7f1d37']

    fig = go.Figure()
    for cat, val, color in zip(categories, values, colors):
        if val > 0:
            fig.add_trace(go.Bar(
                x=[val], y=[''],
                orientation='h',
                name=f"{cat} ({val})",
                marker_color=color,
                marker_line_width=0,
                text=[str(val)],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=12, color='white', family='Arial Black'),
            ))

    fig.update_layout(**BASE_LAYOUT, height=70, barmode='stack')
    fig.update_layout(
        margin=dict(l=0, r=0, t=5, b=0),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
        legend=dict(orientation='h', y=-1.2, x=0, bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
        showlegend=True,
    )
    return fig


def yield_curve_chart(yield_data: dict) -> go.Figure:
    """
    Courbe des taux US sous forme de ligne avec remplissage.
    yield_data : { "3M": 5.2, "5Y": 4.8, "10Y": 4.5, "30Y": 4.7 }
    """
    df = pd.DataFrame(list(yield_data.items()), columns=["Maturité", "Taux (%)"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Maturité"],
        y=df["Taux (%)"],
        mode='lines+markers',
        line=dict(color=COLORS["blue"], width=2),
        marker=dict(size=9, color=COLORS["blue"]),
        fill='tozeroy',
        fillcolor='rgba(33, 150, 243, 0.1)',
    ))
    fig.update_layout(
        **BASE_LAYOUT,
        height=300,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], title="Taux (%)"),
    )
    return fig


def relative_performance_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, ticker_a: str, ticker_b: str) -> go.Figure:
    """
    Compare deux actions sur un même graphique :
    - panneau 1 : performance normalisée à 100
    - panneau 2 : ratio de prix ticker_a / ticker_b
    """
    close_a = df_a['Close'].rename(ticker_a)
    close_b = df_b['Close'].rename(ticker_b)
    merged = pd.concat([close_a, close_b], axis=1).dropna()
    if merged.empty:
        fig = go.Figure()
        fig.update_layout(**BASE_LAYOUT, height=340)
        fig.add_annotation(
            text="No overlapping data",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=16, color=COLORS["muted"]),
        )
        return fig

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
    )

    norm_a = merged[ticker_a] / merged[ticker_a].iloc[0] * 100
    norm_b = merged[ticker_b] / merged[ticker_b].iloc[0] * 100
    ratio = merged[ticker_a] / merged[ticker_b]

    fig.add_trace(go.Scatter(
        x=merged.index,
        y=norm_a,
        mode='lines',
        name=ticker_a,
        line=dict(color=COLORS["blue"], width=2),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=merged.index,
        y=norm_b,
        mode='lines',
        name=ticker_b,
        line=dict(color=COLORS["green"], width=2),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=merged.index,
        y=ratio,
        mode='lines',
        name=f"Ratio {ticker_a}/{ticker_b}",
        line=dict(color="#FFD54F", width=2),
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(**BASE_LAYOUT, height=560, xaxis_rangeslider_visible=False)
    fig.update_yaxes(title="Base 100", showgrid=True, gridcolor=COLORS["grid"], row=1, col=1)
    fig.update_yaxes(title="Ratio", showgrid=True, gridcolor=COLORS["grid"], row=2, col=1)
    fig.update_xaxes(showgrid=False, row=1, col=1)
    fig.update_xaxes(showgrid=False, row=2, col=1)
    return fig


def screener_scatter_chart(df: pd.DataFrame) -> go.Figure:
    """
    Scatter simple pour le screener :
    croissance du CA vs P/E forward, taille = market cap.
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["Revenue Growth (%)"],
        y=df["Forward P/E"],
        mode='markers+text',
        text=df["Ticker"],
        textposition='top center',
        marker=dict(
            size=df["Bubble Size"],
            color=df["1D Change (%)"],
            colorscale=[[0, COLORS["red"]], [0.5, "#d29922"], [1, COLORS["green"]]],
            colorbar=dict(
                title=dict(text="Perf 1D", font=dict(color=COLORS["text"])),
                tickfont=dict(color=COLORS["text"]),
            ),
            showscale=True,
            line=dict(color="#111", width=1),
            opacity=0.85,
        ),
        hovertemplate="<b>%{text}</b><br>Growth: %{x:.1f}%<br>Forward P/E: %{y:.1f}x<extra></extra>",
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        height=420,
        xaxis=dict(title="Revenue Growth (%)", showgrid=False),
        yaxis=dict(title="Forward P/E", showgrid=True, gridcolor=COLORS["grid"]),
    )
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0))
    return fig
