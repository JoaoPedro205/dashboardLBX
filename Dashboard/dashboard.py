import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import re

# ── Página ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LBX Construtora — Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cores LBX ─────────────────────────────────────────────────────────────────
NAVY, BLUE, BACC   = "#0e1c35", "#2e74d4", "#4a9fe0"
PURPLE, GREEN, RED = "#534AB7", "#1D9E75", "#e05a3a"
GOLD, TEAL         = "#f0a830", "#0F6E56"
COLORS3 = [BLUE, PURPLE, GREEN]
COLORS5 = [BLUE, PURPLE, GREEN, GOLD, RED]

PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="rgba(255,255,255,0.7)", family="Segoe UI, sans-serif"),
    margin=dict(l=8, r=8, t=36, b=8),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="rgba(255,255,255,0.7)")),
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
.stApp{{background:{NAVY};}}
section[data-testid="stSidebar"]{{background:#142240;}}
section[data-testid="stSidebar"] *{{color:#fff!important;}}
h1,h2,h3,h4{{color:#fff!important;font-family:'Segoe UI',sans-serif;}}
.sec{{font-size:10px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
      color:{BACC};border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:5px;margin:22px 0 12px;}}
.kcard{{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11);
        border-radius:10px;padding:14px 18px;text-align:center;}}
.klabel{{font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;
         letter-spacing:.1em;margin-bottom:5px;}}
.kval{{font-size:28px;font-weight:700;line-height:1;}}
.ksub{{font-size:11px;color:rgba(255,255,255,.38);margin-top:3px;}}
.insight{{background:rgba(255,255,255,.05);border-left:3px solid {BACC};
          border-radius:0 8px 8px 0;padding:10px 14px;font-size:12px;
          color:rgba(255,255,255,.75);margin-bottom:8px;line-height:1.6;}}
div[data-testid="metric-container"]{{background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:10px;}}
div[data-testid="metric-container"] label{{color:rgba(255,255,255,.55)!important;}}
div[data-testid="metric-container"] div{{color:#fff!important;}}
.stTabs [data-baseweb="tab-list"]{{background:rgba(255,255,255,.05);border-radius:8px;}}
.stTabs [data-baseweb="tab"]{{color:rgba(255,255,255,.6)!important;}}
.stTabs [aria-selected="true"]{{color:#fff!important;background:rgba(255,255,255,.12)!important;}}
</style>""", unsafe_allow_html=True)
# ── Carregar e tratar dados ───────────────────────────────────────────────────
def _ler_bytes(source):
    """Converte qualquer fonte (path str, UploadedFile, BytesIO) em bytes puros."""
    if isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as f:
            return f.read()
    # UploadedFile ou BytesIO
    if hasattr(source, "getvalue"):
        return source.getvalue()
    source.seek(0)
    return source.read()

@st.cache_data(show_spinner="Carregando dados...", ttl=3600)
def load(raw_bytes: bytes):
    import io
    data = io.BytesIO(raw_bytes)
    df = pd.read_excel(data)
    df.columns = df.columns.str.strip()

    rename = {
        "Para qual obra deseja regularizar um contrato?": "Obra",
        "A solicitação está aprovada?":                   "Aprovada",
        "Essa regularização faz parte da carteira de qual setor?": "Setor",
        "Qual regularização deseja realizar?":            "Tipo",
        "Especifique o motivo da compra ter sido feita diretamente pela obra": "Motivo",
        "Especifique a Categoria:":                       "Categoria",
        "Qual o tipo de contrato?":                       "TipoContrato",
        "Haverá caução ou retenção nesse contrato?":      "Caucao",
        "Condição de pagamento negociada":                "Pagamento",
        "Nome":                                           "Usuario",
        "Hora de início":                                 "Inicio",
        "Hora de conclusão":                              "Fim",
        "Qual o número da Solicitação?":                  "NumSolicitacao",
    }
    # colunas com \xa0
    for col in df.columns:
        clean = col.replace("\xa0", " ").strip()
        if "Credor" in clean and "descrição" in clean.lower():
            rename[col] = "Credor"
            break

    df = df.rename(columns=rename)
    df["Inicio"] = pd.to_datetime(df["Inicio"], errors="coerce")
    df["Fim"]    = pd.to_datetime(df["Fim"],    errors="coerce")
    df["LeadMin"]    = (df["Fim"] - df["Inicio"]).dt.total_seconds() / 60
    df["Ano"]        = df["Inicio"].dt.year
    df["Mes"]        = df["Inicio"].dt.month
    df["MesAno"]     = df["Inicio"].dt.to_period("M").astype(str)
    df["DiaSemana"]  = df["Inicio"].dt.day_name()
    df["HoraDia"]    = df["Inicio"].dt.hour
    df["Semana"]     = df["Inicio"].dt.to_period("W").astype(str)

    # normalizar pagamento
    def norm_pag(v):
        if pd.isna(v): return None
        v = str(v).upper().strip()
        if "TED" in v:    return "TED"
        if "BOLETO" in v or v.startswith("BOL"): return "Boleto"
        if "PIX" in v:    return "PIX"
        if "FATURA" in v: return "Fatura"
        return "Outros"
    df["PagNorm"] = df["Pagamento"].apply(norm_pag)

    # ── Tratar nulos em colunas de filtro para não perder registros ──────────
    df["Setor"]    = df["Setor"].fillna("Não informado")
    df["Usuario"]  = df["Usuario"].fillna("Não identificado")
    df["Categoria"]= df["Categoria"].fillna("Não informado")
    df["Motivo"]   = df["Motivo"].fillna("Não informado")
    df["TipoContrato"] = df["TipoContrato"].fillna("Não informado")
    df["Caucao"]   = df["Caucao"].fillna("Não informado")
    df["PagNorm"]  = df["PagNorm"].fillna("Não informado")

    df["Aprovada_bool"] = df["Aprovada"] == "Sim"
    return df

# ── Carregar dados: tenta arquivo local, senão pede upload ──────────────────
import glob, os, io

# Procura qualquer .xlsx na pasta do script (funciona com qualquer nome)
_xlsx_locais = glob.glob(os.path.join(os.path.dirname(__file__) if "__file__" in dir() else ".", "*.xlsx"))
_fonte_local = _xlsx_locais[0] if _xlsx_locais else None

if _fonte_local:
    df = load(_ler_bytes(_fonte_local))
else:
    # Arquivo nao encontrado localmente — exibe uploader
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Carregar planilha")
        _upload = st.file_uploader(
            "Selecione o arquivo .xlsx do Forms",
            type=["xlsx"],
            help="Qualquer nome de arquivo é aceito"
        )
    if _upload is None:
        st.markdown(
            "<div style='text-align:center;padding:80px 20px;'>"
            "<p style='color:rgba(255,255,255,.5);font-size:15px;'>"
            "Faça upload da planilha <b>.xlsx</b> no painel lateral.</p>"
            "</div>",
            unsafe_allow_html=True
        )
        st.stop()
    try:
        # Lê os bytes do arquivo enviado pelo usuário
        _bytes = _upload.getvalue()
        if len(_bytes) == 0:
            st.error("O arquivo enviado está vazio. Tente novamente.")
            st.stop()
        df = load(_bytes)
    except Exception as e:
        st.error(
            f"**Erro ao processar o arquivo:** {e}\n\n"
            "Causas comuns:\n"
            "- O arquivo não é um `.xlsx` válido\n"
            "- O arquivo está corrompido ou protegido por senha\n"
            "- As colunas não correspondem ao formato esperado do Microsoft Forms"
        )
        st.stop()


# ── Sidebar — Filtros ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<h2 style='color:{BACC}!important;font-size:16px;letter-spacing:.06em;'>⚙ FILTROS</h2>", unsafe_allow_html=True)

    anos = sorted(df["Ano"].dropna().unique().tolist())
    anos_sel = st.multiselect("Ano", anos, default=anos)

    obras_disp = sorted(df["Obra"].dropna().unique())
    obras_sel  = st.multiselect("Obra", obras_disp, default=obras_disp)

    setores_disp = sorted(df["Setor"].dropna().unique())
    setores_sel  = st.multiselect("Setor", setores_disp, default=setores_disp)

    tipos_disp = sorted(df["Tipo"].dropna().unique())
    tipos_sel  = st.multiselect("Tipo", tipos_disp, default=tipos_disp)

    aprov_sel = st.radio("Aprovação", ["Todos", "Aprovadas", "Não aprovadas"], index=0)

    st.markdown("---")
    st.markdown(f"<span style='font-size:11px;color:rgba(255,255,255,.4);'>Base: {len(df):,} registros</span>", unsafe_allow_html=True)

# ── Filtrar ───────────────────────────────────────────────────────────────────
dff = df[
    df["Ano"].isin(anos_sel) &
    df["Obra"].isin(obras_sel) &
    df["Setor"].isin(setores_sel) &
    df["Tipo"].isin(tipos_sel)
].copy()
if aprov_sel == "Aprovadas":      dff = dff[dff["Aprovada"] == "Sim"]
elif aprov_sel == "Não aprovadas": dff = dff[dff["Aprovada"] == "Não"]

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='text-align:center;letter-spacing:.08em;font-size:24px;margin-bottom:2px;'>LBX CONSTRUTORA</h1>"
    f"<p style='text-align:center;color:{BACC};letter-spacing:.12em;font-size:11px;margin-top:0;margin-bottom:4px;'>"
    f"DASHBOARD DE REGULARIZAÇÃO · CONTRATOS · ADITIVOS · PEDIDOS DE COMPRA</p>",
    unsafe_allow_html=True
)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊  Visão Geral",
    "🏗️  Obras & Setores",
    "📅  Temporal",
    "👤  Operacional",
    "🔍  Dados Brutos",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — VISÃO GERAL
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    total      = len(dff)
    aprovadas  = dff["Aprovada_bool"].sum()
    reprov     = total - aprovadas
    pct_aprov  = aprovadas / total * 100 if total > 0 else 0
    lead_med   = dff["LeadMin"].median()
    n_obras    = dff["Obra"].nunique()
    n_usuarios = dff["Usuario"].nunique()

    st.markdown("<div class='sec'>KPIs principais</div>", unsafe_allow_html=True)
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    cards = [
        (c1, "Total",          f"{total:,}",        "solicitações",        BACC),
        (c2, "Aprovadas",      f"{aprovadas:,}",     f"{pct_aprov:.1f}%",   GREEN),
        (c3, "Não aprovadas",  f"{reprov:,}",        f"{100-pct_aprov:.1f}%", RED),
        (c4, "Lead time med.", f"{lead_med:.1f} min","preenchimento",        GOLD),
        (c5, "Obras",          f"{n_obras}",         "empreendimentos",     PURPLE),
        (c6, "Usuários",       f"{n_usuarios}",      "respondentes",        "#4a9fe0"),
    ]
    for col, lbl, val, sub, color in cards:
        col.markdown(
            f"<div class='kcard'><div class='klabel'>{lbl}</div>"
            f"<div class='kval' style='color:{color};'>{val}</div>"
            f"<div class='ksub'>{sub}</div></div>", unsafe_allow_html=True
        )

    st.markdown("<div class='sec'>Mix de regularização</div>", unsafe_allow_html=True)
    mix = dff["Tipo"].value_counts().reset_index()
    mix.columns = ["Tipo","Qtd"]
    mix["Pct"] = (mix["Qtd"]/mix["Qtd"].sum()*100).round(1)

    mc1,mc2,mc3 = st.columns(3)
    for col,(_, row) in zip([mc1,mc2,mc3], mix.iterrows()):
        c = COLORS3[_ % 3]
        col.markdown(
            f"<div class='kcard'><div class='klabel'>{row['Tipo']}</div>"
            f"<div class='kval' style='color:{c};'>{row['Qtd']:,}</div>"
            f"<div class='ksub'>{row['Pct']}% do total</div></div>",
            unsafe_allow_html=True
        )

    st.markdown("<div class='sec'>Aprovação por tipo</div>", unsafe_allow_html=True)
    aprov_tipo = dff.groupby("Tipo").agg(
        Total=("Aprovada_bool","count"),
        Aprovadas=("Aprovada_bool","sum")
    ).reset_index()
    aprov_tipo["Reprovadas"] = aprov_tipo["Total"] - aprov_tipo["Aprovadas"]
    aprov_tipo["Taxa"] = (aprov_tipo["Aprovadas"]/aprov_tipo["Total"]*100).round(1)

    g1, g2 = st.columns([1.4, 1])
    with g1:
        fig = go.Figure()
        fig.add_bar(name="Aprovadas",    x=aprov_tipo["Tipo"], y=aprov_tipo["Aprovadas"],    marker_color=GREEN)
        fig.add_bar(name="Não aprovadas",x=aprov_tipo["Tipo"], y=aprov_tipo["Reprovadas"], marker_color=RED)
        fig.update_layout(**PLOT, barmode="stack", title="Volume e aprovação por tipo",
                          title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig, use_container_width=True)

    with g2:
        fig2 = px.pie(mix, names="Tipo", values="Qtd", hole=0.58,
                      color_discrete_sequence=COLORS3, title="Distribuição de tipos")
        fig2.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig2.update_traces(textfont_color="white")
        st.plotly_chart(fig2, use_container_width=True)

    # Insights automáticos
    st.markdown("<div class='sec'>Insights automáticos</div>", unsafe_allow_html=True)
    tipo_mais = mix.iloc[0]["Tipo"]
    tipo_pct  = mix.iloc[0]["Pct"]
    obra_top  = dff["Obra"].value_counts().index[0] if total > 0 else "—"
    obra_top_n= dff["Obra"].value_counts().iloc[0] if total > 0 else 0
    worst_obra = dff.groupby("Obra")["Aprovada_bool"].mean().sort_values().index[0] if total > 0 else "—"
    worst_pct  = dff.groupby("Obra")["Aprovada_bool"].mean().sort_values().iloc[0]*100 if total > 0 else 0

    col_i1, col_i2, col_i3 = st.columns(3)
    col_i1.markdown(f"<div class='insight'>O tipo <b>{tipo_mais}</b> representa <b>{tipo_pct}%</b> de todas as solicitações do período selecionado.</div>", unsafe_allow_html=True)
    col_i2.markdown(f"<div class='insight'><b>{obra_top}</b> é a obra mais demandante com <b>{obra_top_n:,}</b> solicitações registradas.</div>", unsafe_allow_html=True)
    col_i3.markdown(f"<div class='insight'><b>{worst_obra}</b> tem a menor taxa de aprovação: apenas <b>{worst_pct:.1f}%</b> das solicitações aprovadas.</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — OBRAS & SETORES
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("<div class='sec'>Volume e taxa de aprovação por obra</div>", unsafe_allow_html=True)

    obra_stats = dff.groupby("Obra").agg(
        Total=("Aprovada_bool","count"),
        Aprovadas=("Aprovada_bool","sum"),
    ).reset_index()
    obra_stats["Taxa%"] = (obra_stats["Aprovadas"]/obra_stats["Total"]*100).round(1)
    obra_stats = obra_stats.sort_values("Total", ascending=True)

    fig_obras = go.Figure()
    fig_obras.add_bar(name="Aprovadas",    y=obra_stats["Obra"], x=obra_stats["Aprovadas"],
                      orientation="h", marker_color=GREEN)
    fig_obras.add_bar(name="Não aprovadas",y=obra_stats["Obra"],
                      x=obra_stats["Total"]-obra_stats["Aprovadas"],
                      orientation="h", marker_color=RED)
    fig_obras.update_layout(**PLOT, barmode="stack", height=520,
                            title="Solicitações por obra (aprovadas vs. reprovadas)",
                            title_font_color="rgba(255,255,255,.8)",
                            xaxis_title="Qtd", yaxis_title="")
    st.plotly_chart(fig_obras, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("<div class='sec'>Taxa de aprovação % por obra</div>", unsafe_allow_html=True)
        obra_taxa = obra_stats.sort_values("Taxa%")
        fig_taxa = px.bar(obra_taxa, y="Obra", x="Taxa%", orientation="h",
                          color="Taxa%", color_continuous_scale=[[0,RED],[0.5,GOLD],[1,GREEN]],
                          labels={"Taxa%":"Taxa aprovação (%)","Obra":""},
                          title="% aprovação por obra")
        fig_taxa.update_layout(**PLOT, coloraxis_showscale=False,
                               title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_taxa, use_container_width=True)

    with col_b:
        st.markdown("<div class='sec'>Distribuição por setor</div>", unsafe_allow_html=True)
        setor_cnt = dff["Setor"].value_counts().reset_index()
        setor_cnt.columns = ["Setor","Qtd"]
        fig_setor = px.pie(setor_cnt, names="Setor", values="Qtd", hole=0.55,
                           color_discrete_sequence=COLORS3, title="Carteira por setor")
        fig_setor.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_setor.update_traces(textfont_color="white")
        st.plotly_chart(fig_setor, use_container_width=True)

    st.markdown("<div class='sec'>Tipo de regularização por obra (top 10)</div>", unsafe_allow_html=True)
    top10_obras = dff["Obra"].value_counts().head(10).index
    obra_tipo = dff[dff["Obra"].isin(top10_obras)].groupby(["Obra","Tipo"]).size().reset_index(name="Qtd")
    fig_ot = px.bar(obra_tipo, x="Qtd", y="Obra", color="Tipo",
                    color_discrete_sequence=COLORS3, orientation="h",
                    title="Mix de tipos por obra (top 10)",
                    labels={"Qtd":"Solicitações","Obra":""})
    fig_ot.update_layout(**PLOT, height=400, barmode="stack",
                         title_font_color="rgba(255,255,255,.8)")
    st.plotly_chart(fig_ot, use_container_width=True)

    # Tipo de contrato e caução
    col_tc, col_cau = st.columns(2)
    with col_tc:
        st.markdown("<div class='sec'>Tipo de contrato</div>", unsafe_allow_html=True)
        tc = dff["TipoContrato"].value_counts().reset_index()
        tc.columns = ["Tipo","Qtd"]
        fig_tc = px.pie(tc, names="Tipo", values="Qtd", hole=0.55,
                        color_discrete_sequence=[BLUE, PURPLE],
                        title="Normal vs. Spot")
        fig_tc.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_tc.update_traces(textfont_color="white")
        st.plotly_chart(fig_tc, use_container_width=True)

    with col_cau:
        st.markdown("<div class='sec'>Caução / Retenção</div>", unsafe_allow_html=True)
        cau = dff["Caucao"].value_counts().reset_index()
        cau.columns = ["Tipo","Qtd"]
        fig_cau = px.pie(cau, names="Tipo", values="Qtd", hole=0.55,
                         color_discrete_sequence=COLORS5,
                         title="Caução e retenção nos contratos")
        fig_cau.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_cau.update_traces(textfont_color="white")
        st.plotly_chart(fig_cau, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — TEMPORAL
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("<div class='sec'>Evolução mensal por tipo</div>", unsafe_allow_html=True)

    mes_tipo = dff.groupby(["MesAno","Tipo"]).size().reset_index(name="Qtd")
    fig_mt = px.bar(mes_tipo, x="MesAno", y="Qtd", color="Tipo",
                    color_discrete_sequence=COLORS3, barmode="group",
                    labels={"MesAno":"","Qtd":"Solicitações","Tipo":""},
                    title="Solicitações mensais por tipo")
    fig_mt.update_layout(**PLOT, xaxis_tickangle=-40,
                         title_font_color="rgba(255,255,255,.8)")
    st.plotly_chart(fig_mt, use_container_width=True)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("<div class='sec'>Aprovadas vs. reprovadas por mês</div>", unsafe_allow_html=True)
        mes_aprov = dff.groupby(["MesAno","Aprovada"]).size().reset_index(name="Qtd")
        fig_ma = px.bar(mes_aprov, x="MesAno", y="Qtd", color="Aprovada",
                        color_discrete_map={"Sim":GREEN,"Não":RED},
                        labels={"MesAno":"","Qtd":"Qtd","Aprovada":""},
                        title="Aprovação mensal")
        fig_ma.update_layout(**PLOT, xaxis_tickangle=-40,
                             title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_ma, use_container_width=True)

    with col_t2:
        st.markdown("<div class='sec'>Tendência — média móvel 4 semanas</div>", unsafe_allow_html=True)
        sem_cnt = dff.groupby("Semana").size().reset_index(name="Qtd")
        sem_cnt["MM4"] = sem_cnt["Qtd"].rolling(4, min_periods=1).mean().round(1)
        fig_mm = go.Figure()
        fig_mm.add_bar(x=sem_cnt["Semana"], y=sem_cnt["Qtd"],
                       name="Semanal", marker_color=f"rgba(46,116,212,0.4)")
        fig_mm.add_scatter(x=sem_cnt["Semana"], y=sem_cnt["MM4"],
                           name="Média 4 sem.", line=dict(color=GOLD, width=2))
        fig_mm.update_layout(**PLOT, xaxis_tickangle=-60, xaxis_nticks=12,
                             title="Volume semanal + média móvel",
                             title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_mm, use_container_width=True)

    col_t3, col_t4 = st.columns(2)
    with col_t3:
        st.markdown("<div class='sec'>Volume por dia da semana</div>", unsafe_allow_html=True)
        ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        nomes = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]
        dia_cnt = dff["DiaSemana"].value_counts().reindex(ordem, fill_value=0).reset_index()
        dia_cnt.columns = ["Dia","Qtd"]
        dia_cnt["DiaLabel"] = nomes
        fig_dia = px.bar(dia_cnt, x="DiaLabel", y="Qtd",
                         color_discrete_sequence=[BLUE],
                         labels={"DiaLabel":"","Qtd":"Solicitações"},
                         title="Distribuição por dia da semana")
        fig_dia.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_dia, use_container_width=True)

    with col_t4:
        st.markdown("<div class='sec'>Volume por hora do dia</div>", unsafe_allow_html=True)
        hora_cnt = dff["HoraDia"].value_counts().sort_index().reset_index()
        hora_cnt.columns = ["Hora","Qtd"]
        fig_hora = px.area(hora_cnt, x="Hora", y="Qtd",
                           color_discrete_sequence=[BACC],
                           labels={"Hora":"Hora","Qtd":"Solicitações"},
                           title="Pico de preenchimento por hora")
        fig_hora.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_hora.update_traces(fill="tozeroy", fillcolor=f"rgba(74,159,224,0.2)")
        st.plotly_chart(fig_hora, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — OPERACIONAL
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        st.markdown("<div class='sec'>Top 15 usuários por volume</div>", unsafe_allow_html=True)
        user_cnt = dff["Usuario"].value_counts().head(15).reset_index()
        user_cnt.columns = ["Usuario","Qtd"]
        fig_user = px.bar(user_cnt.sort_values("Qtd"), x="Qtd", y="Usuario",
                          orientation="h", color_discrete_sequence=[PURPLE],
                          labels={"Qtd":"Solicitações","Usuario":""},
                          title="Ranking de usuários")
        fig_user.update_layout(**PLOT, height=460,
                               title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_user, use_container_width=True)

    with col_u2:
        st.markdown("<div class='sec'>Lead time por usuário (top 10)</div>", unsafe_allow_html=True)
        user_lead = (
            dff.groupby("Usuario")["LeadMin"]
            .agg(["median","count"])
            .reset_index()
        )
        user_lead.columns = ["Usuario","LeadMediano","Total"]
        user_lead = user_lead[user_lead["Total"] >= 5].nlargest(10, "LeadMediano")
        fig_lead = px.bar(user_lead.sort_values("LeadMediano"), x="LeadMediano", y="Usuario",
                          orientation="h", color_discrete_sequence=[GOLD],
                          labels={"LeadMediano":"Lead time mediano (min)","Usuario":""},
                          title="Usuários com maior tempo de preenchimento")
        fig_lead.update_layout(**PLOT, height=460,
                               title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_lead, use_container_width=True)

    st.markdown("<div class='sec'>Motivos de compra direta pela obra</div>", unsafe_allow_html=True)
    col_m1, col_m2 = st.columns([1.2, 1])

    with col_m1:
        motivo_cnt = dff["Motivo"].value_counts().reset_index()
        motivo_cnt.columns = ["Motivo","Qtd"]
        motivo_cnt["Pct"] = (motivo_cnt["Qtd"]/motivo_cnt["Qtd"].sum()*100).round(1)
        fig_mot = px.bar(motivo_cnt.sort_values("Qtd"), x="Qtd", y="Motivo",
                         orientation="h",
                         color="Qtd", color_continuous_scale=[[0,GOLD],[1,RED]],
                         labels={"Qtd":"Ocorrências","Motivo":""},
                         title="Motivos de compra direta")
        fig_mot.update_layout(**PLOT, coloraxis_showscale=False,
                              title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_mot, use_container_width=True)

    with col_m2:
        fig_mot2 = px.pie(motivo_cnt, names="Motivo", values="Qtd", hole=0.52,
                          color_discrete_sequence=COLORS5,
                          title="Proporção dos motivos")
        fig_mot2.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_mot2.update_traces(textfont_color="white", textinfo="percent")
        st.plotly_chart(fig_mot2, use_container_width=True)

    st.markdown("<div class='sec'>Categorias de pedidos de compra</div>", unsafe_allow_html=True)
    col_c1, col_c2 = st.columns([1.5, 1])

    with col_c1:
        cat_cnt = dff["Categoria"].value_counts().head(15).reset_index()
        cat_cnt.columns = ["Categoria","Qtd"]
        fig_cat = px.bar(cat_cnt.sort_values("Qtd"), x="Qtd", y="Categoria",
                         orientation="h", color_discrete_sequence=[TEAL],
                         labels={"Qtd":"Ocorrências","Categoria":""},
                         title="Top 15 categorias de materiais/serviços")
        fig_cat.update_layout(**PLOT, height=440,
                              title_font_color="rgba(255,255,255,.8)")
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_c2:
        st.markdown("<div class='sec'>Condição de pagamento</div>", unsafe_allow_html=True)
        pag_cnt = dff["PagNorm"].value_counts().dropna().reset_index()
        pag_cnt.columns = ["Pagamento","Qtd"]
        fig_pag = px.pie(pag_cnt, names="Pagamento", values="Qtd", hole=0.52,
                         color_discrete_sequence=COLORS5,
                         title="Forma de pagamento negociada")
        fig_pag.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)")
        fig_pag.update_traces(textfont_color="white")
        st.plotly_chart(fig_pag, use_container_width=True)

        st.markdown("<div class='sec'>Lead time — distribuição</div>", unsafe_allow_html=True)
        lead_clip = dff["LeadMin"].clip(upper=60).dropna()
        fig_hist = px.histogram(lead_clip, nbins=30, color_discrete_sequence=[BACC],
                                labels={"value":"Minutos","count":"Registros"},
                                title="Distribuição do lead time (até 60 min)")
        fig_hist.update_layout(**PLOT, title_font_color="rgba(255,255,255,.8)",
                               showlegend=False)
        st.plotly_chart(fig_hist, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — DADOS BRUTOS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown("<div class='sec'>Tabela completa de registros filtrados</div>", unsafe_allow_html=True)

    cols_show = [c for c in ["Inicio","Obra","Setor","Tipo","Aprovada","Usuario",
                              "TipoContrato","Caucao","PagNorm","Categoria","Motivo","LeadMin"]
                 if c in dff.columns]
    df_show = dff[cols_show].copy()
    df_show["LeadMin"] = df_show["LeadMin"].round(1)
    df_show = df_show.rename(columns={"LeadMin":"Lead (min)","PagNorm":"Pagamento"})
    df_show["Inicio"] = df_show["Inicio"].dt.strftime("%d/%m/%Y %H:%M")

    col_s1, col_s2, col_s3 = st.columns(3)
    busca_obra = col_s1.selectbox("Filtrar por obra", ["Todas"] + sorted(dff["Obra"].dropna().unique().tolist()))
    busca_tipo = col_s2.selectbox("Filtrar por tipo", ["Todos"] + sorted(dff["Tipo"].dropna().unique().tolist()))
    busca_aprov = col_s3.selectbox("Filtrar aprovação", ["Todos","Sim","Não"])

    df_view = df_show.copy()
    if busca_obra  != "Todas":  df_view = df_view[df_view["Obra"] == busca_obra]
    if busca_tipo  != "Todos":  df_view = df_view[df_view["Tipo"] == busca_tipo]
    if busca_aprov != "Todos":  df_view = df_view[df_view["Aprovada"] == busca_aprov]

    st.markdown(f"<p style='color:rgba(255,255,255,.5);font-size:12px;'>{len(df_view):,} registros exibidos</p>",
                unsafe_allow_html=True)
    st.dataframe(df_view, use_container_width=True, height=500)

    csv = df_view.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Baixar CSV filtrado", csv, "lbx_filtrado.csv", "text/csv")

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown(
    f"<p style='text-align:center;font-size:10px;color:rgba(255,255,255,.25);margin-top:30px;'>"
    f"LBX CONSTRUTORA · Dashboard de Regularização · Python + Streamlit + Plotly</p>",
    unsafe_allow_html=True
)
