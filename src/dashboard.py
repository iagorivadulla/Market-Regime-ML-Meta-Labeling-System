"""
╔══════════════════════════════════════════════════════╗
║   MARKET REGIME TERMINAL  —  HMM + MetaLabeling      ║
║   Bloomberg-style Streamlit dashboard                ║
╚══════════════════════════════════════════════════════╝

Run:  streamlit run dashboard.py
Deps: streamlit plotly pandas sqlalchemy hmmlearn scikit-learn joblib python-dotenv yfinance fredapi ta-lib undetected-chromedriver

Folder structure expected (same as your notebooks):
  models/
    hmm_model.pkl
    scaler.pkl
    pca.pkl
    meta_model.pkl          ← save with joblib.dump(meta_model, 'models/meta_model.pkl')
  data/raw/data.db
  src/
    get_all_data.py  (your existing pipeline)
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
import sqlalchemy as db
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
#from get_all_data import get_all_data

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Market Regime Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Bloomberg-style CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Inter:wght@300;400;600&display=swap');

  html, body, [class*="css"] {
    background-color: ##111827 !important;
    color: ##d4d4d4;
    font-family: 'Inter', sans-serif;
  }
    
  /* Fondo principal de Streamlit (CLAVE) */
    [data-testid="stAppViewContainer"] {
    background-color: #0a0a0f !important;
    }

  /* Hide Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 0.8rem 1.2rem 1rem; max-width: 100%; }

  /* Top header bar */
  .terminal-header {
    background: linear-gradient(90deg, #0d0d1a 0%, #101020 100%);
    border-bottom: 1px solid #1e3a5f;
    padding: 6px 16px;
    display: flex; align-items: center; gap: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: #4a8fc4;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
  }
  .terminal-header .logo {
    font-size: 13px; font-weight: 700;
    color: #f0a500; letter-spacing: 0.15em;
  }
  .terminal-header .sep { color: #1e3a5f; }

  /* KPI cards */
  .kpi-card {
    background: #0d0d1a;
    border: 1px solid #1a2840;
    border-radius: 4px;
    padding: 10px 14px 8px;
    position: relative;
    overflow: hidden;
  }
  .kpi-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
  }
  .kpi-card.green::before  { background: #00d084; }
  .kpi-card.red::before    { background: #e05260; }
  .kpi-card.yellow::before { background: #f0a500; }
  .kpi-card.blue::before   { background: #3a8fd4; }
  .kpi-card.purple::before { background: #9b59b6; }
  .kpi-card.cyan::before   { background: #00b8d9; }
  .kpi-card.grey::before   { background: #888; }

  .kpi-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px; color: #5a7a9a; letter-spacing: 0.12em;
    text-transform: uppercase; margin-bottom: 4px;
  }
  .kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px; font-weight: 700; line-height: 1;
    margin-bottom: 2px;
  }
  .kpi-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: #6a8a9a;
  }

  /* Section titles */
  .section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 600;
    color: #4a8fc4; letter-spacing: 0.18em;
    text-transform: uppercase;
    border-bottom: 1px solid #1a2840;
    padding-bottom: 4px; margin-bottom: 8px;
    margin-top: 4px;
  }

  /* Macro table */
  .macro-row {
    display: grid;
    grid-template-columns: 1fr auto 1fr;  /* nombre | valor | badges */
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .macro-name {
    font-size: 0.75rem;
    color: #ccc;
    white-space: nowrap;
  }
  .macro-val {
    font-size: 0.75rem;
    color: #fff;
    font-weight: 700;
    text-align: center;
  }
  .macro-badges {
    display: flex;
    gap: 4px;
    flex-wrap: nowrap;
    justify-content: flex-end;
  }
  .macro-badge {
    font-size: 0.62rem;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    text-align: center;
    line-height: 1.3;
    min-width: 48px;
    white-space: nowrap;
  }
  .macro-badge.up   { background: rgba(0,200,100,0.15); color: #00c864; }
  .macro-badge.down { background: rgba(220,50,50,0.15);  color: #dc3232; }
  .macro-badge.neu  { background: rgba(150,150,150,0.1); color: #555; }

  /* Events countdown */
  .event-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 4px 6px; margin-bottom: 3px;
    border-radius: 2px; font-family: 'JetBrains Mono', monospace; font-size: 10px;
  }
  .event-name { color: #a0b8c8; flex: 1; }
  .event-days {
    font-size: 11px; font-weight: 700;
    padding: 1px 6px; border-radius: 2px; min-width: 36px; text-align: center;
  }
  .days-today  { background: #1a3a1a; color: #00d084; }
  .days-close  { background: #2a1a0a; color: #f0a500; }
  .days-medium { background: #0a1a2a; color: #3a8fd4; }
  .days-far    { background: #111; color: #556; }

  /* Regime badge */
  .regime-badge {
    display: inline-block;
    padding: 3px 12px; border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
  }

  /* Scrollable table container */
  .scroll-box { max-height: 320px; overflow-y: auto; }
  .scroll-box::-webkit-scrollbar { width: 4px; }
  .scroll-box::-webkit-scrollbar-track { background: #0a0a0f; }
  .scroll-box::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 2px; }

  /* Plotly dark override */
  .js-plotly-plot .plotly .svg-container { background: transparent !important; }

  /* Streamlit divider */
  hr { border-color: #1a2840; margin: 8px 0; }

  /* Metric delta override */
  [data-testid="metric-container"] {
    background: #0d0d1a; border: 1px solid #1a2840;
    border-radius: 4px; padding: 8px 12px;
  }
</style>
""", unsafe_allow_html=True)

# ── Colour map (fallback / defaults) ──────────────────────────────────────────
REGIME_COLORS = {
    0: ("#00d084", "green",  "BULL TREND"),
    1: ("#f0a500", "yellow", "TRANSITIONAL"),
    2: ("#e05260", "red",    "BEAR / STRESS"),
    3: ("#3a8fd4", "blue",   "LOW VOL RANGE"),
    4: ("#9b59b6", "purple", "HIGH VOL RANGE"),
}

@st.cache_data(show_spinner=False)
def compute_regime_colors(_df, _models):
    df       = _df.copy()
    model    = _models["hmm"]
    scaler   = _models["scaler"]
    pca      = _models["pca"]
    n_states = model.n_components

    # ── 1. Stats per state ────────────────────────────────────────────────────
    df["spy_ret"] = df["spy_close"].pct_change()
    stats = df.groupby("state")["spy_ret"].agg(
        mean_ret="mean", std_ret="std", count="count"
    )
    stats["annual_ret"] = stats["mean_ret"] * 252 * 100
    stats["annual_vol"] = stats["std_ret"]  * np.sqrt(252) * 100
    stats["sharpe"]     = stats["annual_ret"] / (stats["annual_vol"] + 1e-9)

    means_df = pd.DataFrame(
        scaler.inverse_transform(pca.inverse_transform(model.means_)),
        columns=_models["feature_cols"]
    )

    valid_states = [s for s in range(n_states) if s in stats.index]

    # ── 2. Build feature vector per state (normalised 0-1) ────────────────────
    def get(s, col, default):
        return means_df.iloc[s].get(col, default)

    raw = {s: {
        "ret":  stats.loc[s, "annual_ret"],
        "vol":  stats.loc[s, "annual_vol"],
        "vix":  get(s, "^vix_close",   20.0),
        "hy":   get(s, "BAMLH0A0HYM2",  4.0),
        "nfci": get(s, "NFCI",           0.0),
    } for s in valid_states}

    # Normalise each feature to [0, 1] across states so distances are comparable
    for feat in ["ret", "vol", "vix", "hy", "nfci"]:
        vals = np.array([raw[s][feat] for s in valid_states], dtype=float)
        lo, hi = vals.min(), vals.max()
        for s in valid_states:
            raw[s][f"{feat}_n"] = (raw[s][feat] - lo) / (hi - lo + 1e-9)

    # ── 3. Archetypes in normalised feature space ─────────────────────────────
    # Each archetype is defined by (ret_n, vol_n, vix_n, hy_n, nfci_n)
    # 0 = lowest value across states, 1 = highest value across states
    ARCHETYPES = {
        #                           ret   vol   vix   hy    nfci
        "BEAR": np.array([0.0, 1.0, 1.0, 1.0, 1.0]),  # sin cambios, dist=0
        "BULL": np.array([1.0, 0.0, 0.1, 0.1, 0.0]),  # → State 1 (máx ret)
        "LOW VOL": np.array([0.9, 0.0, 0.0, 0.1, 0.0]),  # → State 4 (vol/VIX mínimos)
        "HIGH VOL": np.array([0.9, 0.2, 0.4, 0.0, 0.1]),  # → State 3 (VIX alto, HY bajo)
        "TRANSITIONAL": np.array([0.8, 0.1, 0.2, 0.4, 0.2]),  # → State 0 (HY elevado)
    }

    assert len(ARCHETYPES) == n_states, (
        f"ARCHETYPES has {len(ARCHETYPES)} entries but model has {n_states} states. "
        "Update ARCHETYPES to match n_states."
    )

    PALETTE = {
        "BEAR":         ("#e05260", "red"),
        "HIGH VOL":     ("#f0a500", "yellow"),
        "TRANSITIONAL": ("#9b59b6", "purple"),
        "LOW VOL":      ("#3a8fd4", "blue"),
        "BULL":         ("#00d084", "green"),
    }

    # ── 4. Hungarian assignment: minimise total distance ──────────────────────
    # Builds a cost matrix [states x archetypes] then finds optimal 1-to-1 match
    from scipy.optimize import linear_sum_assignment

    archetype_names = list(ARCHETYPES.keys())
    feat_order      = ["ret_n", "vol_n", "vix_n", "hy_n", "nfci_n"]

    cost = np.zeros((len(valid_states), len(archetype_names)))
    for i, s in enumerate(valid_states):
        state_vec = np.array([raw[s][f] for f in feat_order])
        for j, arch_name in enumerate(archetype_names):
            cost[i, j] = np.linalg.norm(state_vec - ARCHETYPES[arch_name])

    row_ind, col_ind = linear_sum_assignment(cost)

    # ── 5. Build result ───────────────────────────────────────────────────────
    result = {}
    for i, j in zip(row_ind, col_ind):
        state_id   = valid_states[i]
        label      = archetype_names[j]
        color, badge = PALETTE[label]
        result[state_id] = (color, badge, label)

        ret = raw[state_id]["ret"];  vol = raw[state_id]["vol"]
        vix = raw[state_id]["vix"];  hy  = raw[state_id]["hy"]
        pct = stats.loc[state_id, "count"] / len(df) * 100
        dist = cost[i, j]
        print(f"  State {state_id} → {label:15s} | ret={ret:+.1f}% vol={vol:.1f}% "
              f"VIX={vix:.1f} HY={hy:.2f} ({pct:.1f}% of time) dist={dist:.3f}")

    for s in range(n_states):
        if s not in result:
            result[s] = ("#888888", "grey", f"REGIME {s}")

    return result

# Fallback names in case user has different labelling
def regime_label(state_id):
    return REGIME_COLORS.get(state_id, ("#888888", "grey", f"REGIME {state_id}"))

# ── COLOR UTILS ───────────────────────────────────────────────────────────────
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def hex_to_rgba(hex_color, alpha=1.0):
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"

# ── PLOT STYLE ────────────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0a0a0f",
    plot_bgcolor="#0d0d1a",
    font=dict(family="JetBrains Mono, monospace", size=10, color="#8aa8c4"),
    margin=dict(l=40, r=10, t=26, b=26),
)

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_models():
    """Load HMM, scaler, PCA and meta-model from disk."""
    base = os.path.dirname(__file__)
    paths = {
        "hmm":   os.path.join(base, "..", "models", "hmm_model.pkl"),
        "scaler":os.path.join(base, "..", "models", "scaler.pkl"),
        "pca":   os.path.join(base, "..", "models", "pca.pkl"),
        "meta":  os.path.join(base, "..", "models", "meta_model.pkl"),
        "feature_cols": os.path.join(base, "..", "models", "feature_cols.pkl"),
    }
    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    if missing:
        return None, f"Missing model files: {missing}"
    return {k: joblib.load(p) for k, p in paths.items()}, None


@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    """Load and process all data from the DB."""
    base = os.path.dirname(__file__)
    db_path = os.path.join(base, ".." ,"data", "raw", "data.db")
    if not os.path.exists(db_path):
        return None, f"Database not found at {db_path}"

    engine = db.create_engine(f"sqlite:///{db_path}")

    #get_all_data(engine)

    try:
        stocks = pd.read_sql("SELECT * FROM stocks_processed", engine)
        macro = pd.read_sql("SELECT * FROM macro_processed", engine)
        events = pd.read_sql("SELECT * FROM events_processed", engine)
        countdown = pd.read_sql("SELECT * FROM events_countdown", engine)
        schedule = pd.read_sql("SELECT event, upcoming_date FROM Schedule", engine)
    except Exception as e:
        return None, f"DB read error: {e}"

    # Parse Schedule dates and compute days-to-event relative to today
    schedule["upcoming_date"] = pd.to_datetime(schedule["upcoming_date"])
    today = pd.Timestamp.now().normalize()
    schedule["days_until"] = (schedule["upcoming_date"] - today).dt.days
    # Keep only future (or today) events, sorted soonest first
    schedule = (schedule[schedule["days_until"] >= 0]
                .sort_values("days_until")
                .reset_index(drop=True))

    for df_t in [stocks, macro, events, countdown]:
        df_t["date"] = pd.to_datetime(df_t["date"])
        df_t.set_index("date", inplace=True)

    df = stocks.join([macro, events, countdown], how='left')
    df = df.ffill()
    df = df.dropna(how='any')
    return {"df": df, "raw_stocks": stocks, "macro": macro, "countdown": countdown, "schedule": schedule, "events": events}, None


@st.cache_data(ttl=3600, show_spinner=False)
def run_inference(_models, _data):
    """Run HMM + meta-model inference on the full dataset."""
    df    = _data["df"].copy()
    hmm   = _models["hmm"]
    scaler= _models["scaler"]
    pca   = _models["pca"]
    meta  = _models["meta"]
    feat_cols = _models["feature_cols"]

    # ── Guard: align to training columns, same order ───────────────────────────
    missing_cols = [c for c in feat_cols if c not in df.columns]
    extra_cols = [c for c in df.columns if c not in feat_cols]
    if missing_cols:
        st.warning(f"Dashboard df is missing {len(missing_cols)} training columns: "
                   f"{missing_cols[:5]}{'…' if len(missing_cols) > 5 else ''}. "
                   "Predictions may be inaccurate.")
    if extra_cols:
        # Silently drop columns the scaler never saw
        df = df.drop(columns=extra_cols)

    # Reindex to exact training column order (fills any gap with NaN then drops)
    df = df.reindex(columns=feat_cols).dropna()

    X_scaled = scaler.transform(df)
    X_pca    = pca.transform(X_scaled)

    n_states     = hmm.n_components
    state_probs  = hmm.predict_proba(X_pca)
    state_predict= hmm.predict(X_pca)

    df["state"] = state_predict
    for i in range(n_states):
        df[f"prob_state_{i}"] = state_probs[:, i]

    df["confidence"] = state_probs.max(axis=1)
    df["entropy"]    = -np.sum(state_probs * np.log(state_probs + 1e-8), axis=1)
    df["prev_state"] = df["state"].shift(1)
    df["state_change"] = (df["state"] != df["prev_state"]).astype(int)

    duration, count = [], 1
    for i in range(len(df)):
        if i == 0:
            duration.append(1)
        elif df["state"].iloc[i] == df["state"].iloc[i-1]:
            count += 1; duration.append(count)
        else:
            count = 1; duration.append(count)
    df["state_duration"] = duration

    window = 5
    df["confidence_roll"] = df["confidence"].rolling(window).mean()
    for i in range(n_states):
        df[f"prob_state_{i}_roll"] = df[f"prob_state_{i}"].rolling(window).mean()

    features = (
        ["confidence", "entropy", "state_duration", "confidence_roll"]
        + [f"prob_state_{i}_roll" for i in range(n_states)]
    )

    # Meta-model filtering
    final_states = []
    for i in range(len(df)):
        if i == 0:
            final_states.append(df["state"].iloc[i]); continue
        current = df["state"].iloc[i]
        prev    = final_states[-1]
        if current != prev:
            X_t   = df.iloc[i][features].values.reshape(1, -1)
            proba = meta.predict_proba(X_t)[0][1]
            final_states.append(current if proba > 0.75 else prev)
        else:
            final_states.append(current)

    df["filtered_state"] = final_states
    df.dropna(inplace=True)
    return df, n_states


# ── Chart helpers ──────────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0a0a0f",
    plot_bgcolor="#0d0d1a",
    font=dict(family="JetBrains Mono, monospace", size=10, color="#8aa8c4"),
    margin=dict(l=0, r=0, t=26, b=26),
    xaxis=dict(gridcolor="#0f1a2a", showgrid=True, zeroline=False, color="#5a7a9a"),
    yaxis=dict(gridcolor="#0f1a2a", showgrid=True, zeroline=False, color="#5a7a9a"),
)


def spy_regime_chart(df, n_states, lookback_days=504):
    """Main price chart with clean rectangular regime background fills."""
    # 1. Preparación de datos
    df_plot = df.tail(lookback_days).copy()
    if df_plot.empty:
        return go.Figure()

    df_plot = df_plot.dropna(subset=['filtered_state', 'spy_close'])
    spy = df_plot["spy_close"]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.70, 0.30],
        vertical_spacing=0.05,
    )

    # 2. LÓGICA DE BLOQUES SÓLIDOS (Solo en la gráfica superior)
    # Identificar cambios de estado
    df_plot['change'] = df_plot['filtered_state'].ne(df_plot['filtered_state'].shift())
    df_plot['regime_group'] = df_plot['change'].cumsum()

    # Calculamos el min y max de SPY para que el fondo cubra exactamente el área
    y_min, y_max = spy.min() * 0.95, spy.max() * 1.05

    # Agrupar en bloques
    regime_blocks = df_plot.groupby('regime_group').agg({
        'filtered_state': 'first',
        'spy_close': lambda x: x.index[0],  # start date
    }).rename(columns={'spy_close': 'start'})

    # Añadir fecha de fin a cada bloque
    starts = list(regime_blocks['start'])
    regime_blocks['end'] = starts[1:] + [df_plot.index[-1]]

    for i, (_, row) in enumerate(regime_blocks.iterrows()):
        color, _, _ = regime_label(int(row['filtered_state']))
        x0 =  row['start']

        # Usamos add_shape limitado a la fila 1 (row=1)
        fig.add_shape(
            type="rect",
            x0=x0, x1=row['end'],
            y0=y_min, y1=y_max,
            xref="x", yref="y",
            fillcolor=color,
            opacity=0.15,
            layer="below",
            line_width=0,
            row=1, col=1
        )

    # 3. LEYENDA
    for state_id in range(n_states):
        color, _, label = regime_label(state_id)
        fig.add_trace(go.Scatter(
            x=[df_plot.index[0]], y=[None],
            mode='markers',
            marker=dict(size=12, color=color, symbol='square'),
            name=f"<span style='color:white'>{label}</span>",  # Forzar texto blanco
            showlegend=True,
            hoverinfo='skip'
        ), row=1, col=1)

    # 4. LÍNEAS TÉCNICAS (SPY y EMAs)
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=spy,
        name="<span style='color:white'>SPY Price</span>",
        line=dict(color="#ffffff", width=2),
    ), row=1, col=1)

    # 5. PANEL INFERIOR (VIX)
    if "^vix_close" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot["^vix_close"],
            name="<span style='color:white'>VIX</span>",
            line=dict(color="#e05260", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(224,82,96,0.1)",
        ), row=2, col=1)

    # 6. CONFIGURACIÓN VISUAL
    full_layout = PLOTLY_LAYOUT.copy()
    full_layout.update({
        "height": 600,
        "dragmode": "zoom",
        "font": {"color": "#ffffff"},
        "showlegend": True,
        "legend": dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        ),
        "margin": dict(l=0, r=0, t=50, b=10),  # l=0 para que pegue al borde
        "xaxis": dict(
            range=[df_plot.index.min(), df_plot.index.max()],  # Forzar inicio y fin
            showgrid=True,
            gridcolor="#1a2840",
            tickfont=dict(color="white"),
            fixedrange=False,
            automargin=False,
            constrain="domain",
        ),
    })

    fig.update_layout(full_layout)

    # Configurar ejes Y a la IZQUIERDA
    fig.update_yaxes(
        gridcolor="#1a2840",
        side="left",
        tickfont=dict(color="white"),
        title_font=dict(color="white"),
        autorange=True,
        automargin=True,
        ticks="inside",
        ticklen= 0,
        tickprefix=" ",
    )

    # Ajuste específico para el eje del SPY para que no haya huecos
    fig.update_yaxes(range=[y_min, y_max], row=1, col=1)

    fig.update_xaxes(rangebreaks=[], range=[df_plot.index[0], df_plot.index[-1]])

    return fig

def state_prob_chart(latest_row, n_states):
    """Horizontal bar chart showing state probabilities."""
    labels = [regime_label(i)[2] for i in range(n_states)]
    values = [latest_row.get(f"prob_state_{i}", 0) for i in range(n_states)]
    colors = [regime_label(i)[0] for i in range(n_states)]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        text=[f"{v:.1%}" for v in values],
        textposition="outside",
        textfont=dict(size=10, color="#d4d4d4"),
        hovertemplate="%{y}: %{x:.2%}<extra></extra>",
    ))
    fig.update_layout(
        **{**PLOTLY_LAYOUT,
           "height": 180,
           "xaxis": dict(range=[0,1], tickformat=".0%", gridcolor="#0f1a2a"),
           "yaxis": dict(gridcolor="rgba(0,0,0,0)"),
           "margin": dict(l=10, r=50, t=10, b=24),
           "showlegend": False,
        }
    )
    return fig


def transition_heatmap(model):
    """Transition probability matrix heatmap."""
    mat = model.transmat_
    n = mat.shape[0]
    labels = [regime_label(i)[2] for i in range(n)]

    fig = go.Figure(go.Heatmap(
        z=mat, x=labels, y=labels,
        colorscale=[[0,"#0a0a0f"],[0.5,"#1a3a5f"],[1,"#3a8fd4"]],
        text=np.round(mat*100,1),
        texttemplate="%{text:.0f}%",
        textfont=dict(size=9),
        hovertemplate="From %{y} → %{x}: %{z:.2%}<extra></extra>",
        showscale=False,
    ))
    fig.update_layout(
        **{**PLOTLY_LAYOUT,
           "height": 200,
           "margin": dict(l=10, r=10, t=10, b=10),
           "xaxis": dict(side="top", tickfont=dict(size=8)),
           "yaxis": dict(tickfont=dict(size=8), autorange="reversed"),
        }
    )
    return fig


def macro_sparkline(series, color):
    s = series.dropna().tail(60)

    fig = go.Figure(go.Scatter(
        x=s.index,
        y=s.values,
        line=dict(color=color, width=1.2),
        fill="tozeroy",
        fillcolor=hex_to_rgba(color, 0.08),  # ✅ FIXED
        hoverinfo="x+y",
    ))

    fig.update_layout(
        **{**PLOTLY_LAYOUT,
           "height": 50,
           "margin": dict(l=0, r=0, t=0, b=0),
           "showlegend": False,
           "xaxis": dict(visible=False),
           "yaxis": dict(visible=False),
        }
    )
    return fig


def regime_duration_chart(df):
    """Bar chart showing average days spent in each regime."""
    grp = (df.groupby("filtered_state")["state_duration"]
             .apply(lambda x: x[x==x.max()].count())
             .reset_index())
    grp.columns = ["state", "episodes"]
    avg = df.groupby("filtered_state")["state_duration"].max().reset_index()
    avg.columns = ["state", "max_duration"]

    data = (df.assign(episode=(df["filtered_state"] != df["filtered_state"].shift()).cumsum())
              .groupby(["episode","filtered_state"])["state_duration"]
              .max().reset_index())
    avg_dur = data.groupby("filtered_state")["state_duration"].mean()

    labels = [regime_label(i)[2] for i in avg_dur.index]
    colors = [regime_label(i)[0] for i in avg_dur.index]

    fig = go.Figure(go.Bar(
        x=labels, y=avg_dur.values,
        marker_color=colors,
        text=[f"{v:.0f}d" for v in avg_dur.values],
        textposition="outside", textfont=dict(size=9, color="#d4d4d4"),
        hovertemplate="%{x}: %{y:.0f} days avg<extra></extra>",
    ))
    fig.update_layout(
        **{**PLOTLY_LAYOUT,
           "height": 170,
           "margin": dict(l=10, r=10, t=10, b=40),
           "showlegend": False,
           "xaxis": dict(tickfont=dict(size=8), gridcolor="rgba(0,0,0,0)"),
           "yaxis": dict(title="avg days", gridcolor="#0f1a2a"),
        }
    )
    return fig


# ── App ────────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # ── Terminal header bar ────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="terminal-header">
      <span class="logo">▎REGIME TERMINAL</span>
      <span class="sep">│</span>
      <span>S&P 500 · MACRO · HMM · METALABELING</span>
      <span class="sep">│</span>
      <span style="margin-left:auto; color:#2a5a8a">{now}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Load data ──────────────────────────────────────────────────────────────
    with st.spinner("Loading models & data…"):
        models, model_err = load_models()
        data,   data_err  = load_data()

    if model_err or data_err:
        st.error(model_err or data_err)
        st.markdown("""
        **Setup checklist:**
        1. Run your full pipeline (`get_all_data.py`) to populate `data/raw/data.db`
        2. Run `process_db.py` and `final_db.py`
        3. Train and save models:
           ```python
           import joblib
           joblib.dump(scaler,     'models/scaler.pkl')
           joblib.dump(pca,        'models/pca.pkl')
           joblib.dump(model,      'models/hmm_model.pkl')
           joblib.dump(meta_model, 'models/meta_model.pkl')
           ```
        """)
        st.stop()

    df, n_states = run_inference(models, data)

    # ── Override REGIME_COLORS with labels computed from the data ─────────────────
    global REGIME_COLORS
    REGIME_COLORS = compute_regime_colors(df, models)

    # Latest snapshot
    latest      = df.iloc[-1]
    curr_state  = int(latest["filtered_state"])
    hmm_state   = int(latest["state"])
    confidence  = latest["confidence"]
    entropy     = latest["entropy"]
    duration    = int(latest["state_duration"])
    color, badge_class, regime_name = regime_label(curr_state)

    # Recent regime changes
    changes = df[df["filtered_state"] != df["filtered_state"].shift(1)].tail(10)

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 1 — KPI cards
    # ═══════════════════════════════════════════════════════════════════════
    c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.4, 1.4, 1.4, 1.4, 1.4])

    with c1:
        r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
        conf_pct = f"{confidence:.1%}"
        spy_price = f"${latest.get('spy_close', 0):.2f}"
        st.markdown(f"""
        <div class="kpi-card {badge_class}">
          <div class="kpi-label">CURRENT REGIME</div>
          <div class="kpi-value" style="color:{color}; font-size:18px;">{regime_name}</div>
          <div class="kpi-sub">HMM raw: {regime_label(hmm_state)[2]} &nbsp;·&nbsp; SPY {spy_price}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        conf_clr = "#00d084" if confidence > 0.7 else "#f0a500" if confidence > 0.5 else "#e05260"
        st.markdown(f"""
        <div class="kpi-card {badge_class}">
          <div class="kpi-label">CONFIDENCE</div>
          <div class="kpi-value" style="color:{conf_clr}">{confidence:.1%}</div>
          <div class="kpi-sub">meta threshold 75%</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        ent_clr = "#00d084" if entropy < 0.8 else "#f0a500" if entropy < 1.3 else "#e05260"
        st.markdown(f"""
        <div class="kpi-card blue">
          <div class="kpi-label">ENTROPY</div>
          <div class="kpi-value" style="color:{ent_clr}">{entropy:.3f}</div>
          <div class="kpi-sub">lower = clearer regime</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card {badge_class}">
          <div class="kpi-label">REGIME DURATION</div>
          <div class="kpi-value" style="color:{color}">{duration}d</div>
          <div class="kpi-sub">consecutive sessions</div>
        </div>
        """, unsafe_allow_html=True)

    vix_val = latest.get("^vix_close", None)
    with c5:
        vix_str = f"{vix_val:.1f}" if vix_val else "N/A"
        vix_clr = "#e05260" if (vix_val or 0) > 25 else "#f0a500" if (vix_val or 0) > 18 else "#00d084"
        st.markdown(f"""
        <div class="kpi-card red">
          <div class="kpi-label">VIX</div>
          <div class="kpi-value" style="color:{vix_clr}">{vix_str}</div>
          <div class="kpi-sub">fear gauge</div>
        </div>
        """, unsafe_allow_html=True)

    yc = latest.get("T10Y2Y", None)
    with c6:
        yc_str = f"{yc:.2f}%" if yc is not None else "N/A"
        yc_clr = "#e05260" if (yc or 0) < 0 else "#00d084"
        st.markdown(f"""
        <div class="kpi-card {'green' if (yc or 0) >= 0 else 'red'}">
          <div class="kpi-label">YIELD CURVE 10Y-2Y</div>
          <div class="kpi-value" style="color:{yc_clr}">{yc_str}</div>
          <div class="kpi-sub">{'normal' if (yc or 0) >= 0 else 'inverted'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 2 — Main chart | Right panel
    # ═══════════════════════════════════════════════════════════════════════
    col_chart, col_right = st.columns([3.0, 1.0])

    with col_chart:
        # Lookback selector
        lb_opts = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260, "ALL": len(df)}
        lb_sel  = st.radio("Lookback", list(lb_opts.keys()), index=3,
                           horizontal=True, label_visibility="collapsed")
        lookback = lb_opts[lb_sel]

        st.markdown('<div class="section-title">SPY PRICE  ·  REGIME OVERLAY  ·  VIX</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(spy_regime_chart(df, n_states, lookback),
                        width= "stretch", config={"displayModeBar": False})

    with col_right:
        st.markdown('<div class="section-title">MARKET OVERVIEW</div>', unsafe_allow_html=True)

        assets = [
            ("spy_close",     "SPY  S&P500",     "#00d084"),
            ("qqq_close",     "QQQ  NASDAQ",     "#3a8fd4"),
            ("^vix_close",    "VIX  VOLATILITY", "#e05260"),
            ("dx-y.nyb_close","DXY  DOLLAR",     "#f0a500"),
            ("gc=f_close",    "GC   GOLD",        "#f5c518"),
        ]

        for field, label, clr in assets:
            if field in df.columns:
                series = df[field].dropna().tail(252)
                if len(series) < 5:
                    continue
                last_v  = series.iloc[-1]
                chg_1d  = (last_v / series.iloc[-2]  - 1) if len(series) > 1  else 0
                chg_1m  = (last_v / series.iloc[-21] - 1) if len(series) > 21 else 0
                chg_clr = "#00d084" if chg_1d >= 0 else "#e05260"
                arrow   = "▲" if chg_1d >= 0 else "▼"

                fig_sp = macro_sparkline(series, clr)
                st.markdown(f"""
                <div style="background:#0d0d1a; border:1px solid #1a2840; border-radius:4px;
                            padding:6px 10px 4px; margin-bottom:2px;">
                  <div style="font-family:'JetBrains Mono',monospace; font-size:9px;
                              color:#4a6a8a; letter-spacing:0.1em;">{label}</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:15px;
                              font-weight:700; color:#d4d4d4;">{last_v:.2f}</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:10px;
                              color:{chg_clr};">{arrow} {chg_1d:+.2%} 1d &nbsp; {chg_1m:+.2%} 1m</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(fig_sp, width="stretch",
                                config={"displayModeBar": False})

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 3 — Macro | Events | Regime log
    # ═══════════════════════════════════════════════════════════════════════
    col_macro, col_events, col_log = st.columns([1.2, 1.2, 1.0])

    # ── Macro indicators ──────────────────────────────────────────────────────
    macro_indicators = [
        ("FEDFUNDS",       "Fed Funds Rate",      "%",  False),
        ("T10Y2Y",         "Yield Curve 10Y-2Y",  "%",  True),
        ("GS10",           "10Y Treasury",        "%",  False),
        ("BAMLH0A0HYM2",   "High Yield OAS Spread",       "%",  True),
        ("BAMLC0A0CM",     "Investment Grade OAS Spread",        "%",  True),
        ("UNRATE",         "Unemployment",        "%",  True),
        ("CPIAUCSL",       "CPI",                 "",   True),
        ("T5YIE",          "5Y Breakeven Infl.",  "%",  False),
        ("WALCL",          "Fed Balance Sheet",   "T$", False),
        ("M2SL",           "M2 Money Supply",     "B$", False),
        ("NFCI",           "NFCI",                "",   True),
        ("US Existing Home Sales", "Existing Home Sales", "M$", False),
        ("US New Home Sales", "New Home Sales", "K$", False ),
    ]

    with col_macro:
        st.markdown('<div class="section-title">MACRO INDICATORS</div>', unsafe_allow_html=True)
        macro_df = pd.concat([data["macro"], data["events"]], axis=1)

        periods = {
            "3M": 63,
            "6M": 126,
            "1Y": 252,
            "2Y": 504,
            "5Y": 1260,
        }

        macro_row_count = sum(
            1 for serie, _, _, _ in macro_indicators
            if serie in macro_df.columns and len(macro_df[serie].dropna()) >= 2
        )
        # 38.5px per row (padding 4px top+bottom + ~25px content)
        macro_panel_px = macro_row_count * 38.5

        rows_html = ""
        for serie, label, unit, higher_bad in macro_indicators:
            if serie not in macro_df.columns:
                continue
            vals = macro_df[serie].dropna()
            if len(vals) < 2:
                continue
            val = vals.iloc[-1]

            if unit == "T$":
                disp = f"{val / 1e6:.2f}T"
            elif unit == "B$":
                disp = f"{val / 1e3:.2f}B"
            elif unit == "M$":
                disp = f"{val / 1e6:.2f}M"
            elif unit == "K$":
                disp = f"{val / 1e3:.2f}K"
            elif unit == "%":
                disp = f"{val:.2f}%"
            else:
                disp = f"{val:.2f}"

            badges_html = ""
            for period_label, lookback in periods.items():
                if len(vals) < lookback + 1:
                    badges_html += f'<span class="macro-badge neu">–</span>'
                    continue
                ref = vals.iloc[-(lookback + 1)]
                if ref == 0:
                    badges_html += f'<span class="macro-badge neu">–</span>'
                    continue
                chg_pct = (val - ref) / abs(ref) * 100

                if abs(chg_pct) < 0.01:
                    cls = "neu"
                elif (chg_pct > 0 and not higher_bad) or (chg_pct < 0 and higher_bad):
                    cls = "up"
                else:
                    cls = "down"

                sign = "+" if chg_pct > 0 else ""
                badges_html += f'<span class="macro-badge {cls}">{period_label}<br>{sign}{chg_pct:.1f}%</span>'

            rows_html += f"""
            <div class="macro-row">
              <span class="macro-name">{label}</span>
              <span class="macro-val">{disp}</span>
              <div class="macro-badges">{badges_html}</div>
            </div>"""

        st.markdown(rows_html, unsafe_allow_html=True)

    # ── Events countdown ──────────────────────────────────────────────────────
    with col_events:
        st.markdown('<div class="section-title">UPCOMING ECONOMIC EVENTS</div>', unsafe_allow_html=True)
        schedule = data.get("schedule", pd.DataFrame())
        if not schedule.empty:
            rows_html = ""
            for _, row in schedule.iterrows():
                ev = row["event"]
                d = int(row["days_until"])
                date_str = row["upcoming_date"].strftime("%b %d")

                # Short display name: strip "US " prefix and frequency suffixes
                short = (ev.replace("US ", "")
                         .replace(" m/m", "").replace(" y/y", "")
                         .replace(" q/q", "").replace(" Change", ""))

                if d == 0:
                    cls, lbl = "days-today", "TODAY"
                elif d <= 5:
                    cls, lbl = "days-close", f"{d}d"
                elif d <= 20:
                    cls, lbl = "days-medium", f"{d}d"
                else:
                    cls, lbl = "days-far", f"{d}d"

                rows_html += f"""
                <div class="event-row">
                  <span class="event-name">{short}</span>
                  <span class="event-days {cls}" title="{date_str}">{lbl}</span>
                </div>"""

            st.markdown(f'<div style="height:{macro_panel_px}px; overflow-y:auto;">{rows_html}</div>', unsafe_allow_html=True)
        else:
            st.info("No schedule data — run search_event() to populate the Schedule table")

    # ── Regime intel panel ────────────────────────────────────────────────────
    with col_log:
        # ── 1. Current regime historical stats ───────────────────────────────
        st.markdown('<div class="section-title">CURRENT REGIME STATS</div>', unsafe_allow_html=True)

        df["_spy_ret"] = df["spy_close"].pct_change()
        regime_stats = df.groupby("filtered_state")["_spy_ret"].agg(
            mean_ret="mean", std_ret="std", count="count"
        )
        regime_stats["annual_ret"] = regime_stats["mean_ret"] * 252 * 100
        regime_stats["annual_vol"] = regime_stats["std_ret"]  * np.sqrt(252) * 100
        regime_stats["sharpe"]     = regime_stats["annual_ret"] / (regime_stats["annual_vol"] + 1e-9)
        regime_stats["pct_time"]   = regime_stats["count"] / len(df) * 100

        if curr_state in regime_stats.index:
            rs   = regime_stats.loc[curr_state]
            rret = rs["annual_ret"]
            rvol = rs["annual_vol"]
            rsh  = rs["sharpe"]
            rpct = rs["pct_time"]
            ret_clr = "#00d084" if rret >= 0 else "#e05260"
            sh_clr  = "#00d084" if rsh  >= 1 else "#f0a500" if rsh >= 0 else "#e05260"

            stats_html = f"""
            <div style="background:#0d0d1a; border:1px solid #1a2840; border-radius:4px;
                        padding:10px 12px; margin-bottom:8px; border-left:3px solid {color};">
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px;">
                <div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:8px;
                              color:#4a6a8a; letter-spacing:0.1em;">ANN. RETURN</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:16px;
                              font-weight:700; color:{ret_clr};">{rret:+.1f}%</div>
                </div>
                <div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:8px;
                              color:#4a6a8a; letter-spacing:0.1em;">ANN. VOL</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:16px;
                              font-weight:700; color:#d4d4d4;">{rvol:.1f}%</div>
                </div>
                <div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:8px;
                              color:#4a6a8a; letter-spacing:0.1em;">SHARPE</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:16px;
                              font-weight:700; color:{sh_clr};">{rsh:.2f}</div>
                </div>
                <div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:8px;
                              color:#4a6a8a; letter-spacing:0.1em;">% OF TIME</div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:16px;
                              font-weight:700; color:#d4d4d4;">{rpct:.1f}%</div>
                </div>
              </div>
            </div>"""
            st.markdown(stats_html, unsafe_allow_html=True)

        # ── 2. Next-state transition probabilities ────────────────────────────
        st.markdown('<div class="section-title">NEXT REGIME PROBABILITIES</div>', unsafe_allow_html=True)

        transmat   = models["hmm"].transmat_
        trans_row  = transmat[curr_state]           # probabilities from current state
        sorted_idx = np.argsort(trans_row)[::-1]    # descending

        trans_html = ""
        for s_id in sorted_idx:
            prob        = trans_row[s_id]
            s_clr, _, s_name = regime_label(s_id)
            bar_w       = int(prob * 100)
            is_self     = s_id == curr_state
            opacity     = "1.0" if not is_self else "0.55"
            self_label  = " ← current" if is_self else ""
            trans_html += f"""
            <div style="margin-bottom:7px; opacity:{opacity};">
              <div style="display:flex; justify-content:space-between; align-items:center;
                          font-family:'JetBrains Mono',monospace; font-size:9px;
                          margin-bottom:2px;">
                <span style="color:{s_clr}; font-weight:700;">{s_name}{self_label}</span>
                <span style="color:#8aa8c4;">{prob:.1%}</span>
              </div>
              <div style="background:#0f1a2a; border-radius:2px; height:5px; width:100%;">
                <div style="background:{s_clr}; width:{bar_w}%; height:5px;
                            border-radius:2px; transition:width 0.3s;"></div>
              </div>
            </div>"""

        st.markdown(f'<div style="padding:2px 0">{trans_html}</div>', unsafe_allow_html=True)

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding:12px; margin-top:12px;
            font-family:'JetBrains Mono', monospace; font-size:10px;
            color:#1e3a5f; border-top:1px solid #0f1a2a;">
      Model: HMM (5-state Gaussian) + RF Meta-labeling (threshold = 0.75)<br>
      Data sources: FRED · ForexFactory · Yahoo Finance (open prices)<br>
      This content is for informational purposes only and does not constitute financial advice.
    </div>
    """, unsafe_allow_html=True)

    # ── Auto-refresh ───────────────────────────────────────────────────────────
    st.markdown("""
    <script>
    setTimeout(function(){ window.location.reload(); }, 3600000);  // refresh every hour
    </script>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()