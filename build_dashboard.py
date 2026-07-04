#!/usr/bin/env python3
"""Gera dashboard-visitantes.html com dados embutidos."""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "datatable-sem-trilha.csv"
OUT_HTML = ROOT / "dashboard-visitantes.html"

CULTOS = {
    1: {"id": "fe-milagres", "nome": "Fé e Milagres", "dia": "Terça"},
    3: {"id": "quinta-profetica", "nome": "Quinta Profética", "dia": "Quinta"},
    5: {"id": "arena", "nome": "Arena", "dia": "Sábado"},
    6: {"id": "culto-familia", "nome": "Culto da Família", "dia": "Domingo", "nota": "Manhã + Noite"},
}
WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def parse_date(value: str):
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def norm_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def moving_avg(values, window=3):
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1) : i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def build_records(rows):
    records = []
    for row in rows:
        dt = parse_date(row["Data de Cadastro"])
        if not dt or dt.year < 2020:
            continue
        culto = CULTOS.get(dt.weekday())
        if not culto:
            continue
        records.append(
            {
                "nome": (row.get("Nome") or "").strip(),
                "email": (row.get("Email") or "").strip(),
                "telefone": (row.get("Celular") or "").strip(),
                "telefone_norm": norm_phone(row.get("Celular")),
                "contato": (row.get("Contato") or "").strip(),
                "data": dt.strftime("%d/%m/%Y"),
                "data_iso": iso_date(dt),
                "weekday": WEEKDAYS[dt.weekday()],
                "culto_id": culto["id"],
                "culto": culto["nome"],
                "genero": None,
                "origem": None,
            }
        )
    return records


def aggregate(records):
    by_date = defaultdict(list)
    by_phone = defaultdict(list)
    for rec in records:
        by_date[rec["data"]].append(rec)
        if rec["telefone_norm"]:
            by_phone[rec["telefone_norm"]].append(rec)

    ranking = []
    for date, items in sorted(by_date.items(), key=lambda x: parse_date(x[0])):
        dt = parse_date(date)
        ranking.append(
            {
                "date": date,
                "date_iso": iso_date(dt),
                "count": len(items),
                "weekday": WEEKDAYS[dt.weekday()],
                "culto_id": CULTOS[dt.weekday()]["id"],
                "culto": CULTOS[dt.weekday()]["nome"],
            }
        )

    counts = [r["count"] for r in ranking]
    evolucao = [
        {"date": r["date"], "date_iso": r["date_iso"], "count": r["count"], "ma3": ma}
        for r, ma in zip(ranking, moving_avg(counts))
    ]

    dist_culto = Counter(r["culto_id"] for r in records)
    dist_weekday = Counter(r["weekday"] for r in records)

    by_month = Counter(month_key(parse_date(r["data"])) for r in records)
    months = sorted(by_month)
    crescimento = []
    for month in months:
        count = by_month[month]
        prev = crescimento[-1]["count"] if crescimento else None
        pct = round((count - prev) / prev * 100, 1) if prev else None
        crescimento.append({"month": month, "count": count, "pct": pct})

    first_seen = {}
    novos = Counter()
    for rec in sorted(records, key=lambda r: r["data_iso"]):
        phone = rec["telefone_norm"] or rec["nome"].lower()
        if phone not in first_seen:
            first_seen[phone] = rec["data_iso"]
            novos[month_key(parse_date(rec["data"]))] += 1

    pessoas = []
    for phone, visits in by_phone.items():
        visits_sorted = sorted(visits, key=lambda r: r["data_iso"])
        cultos = sorted({v["culto"] for v in visits_sorted})
        historico = [{"data": v["data"], "culto": v["culto"]} for v in visits_sorted]
        pessoas.append(
            {
                "nome": visits_sorted[-1]["nome"] or "Sem nome",
                "telefone": visits_sorted[-1]["telefone"],
                "email": visits_sorted[-1]["email"] or "",
                "visitas": len(visits_sorted),
                "primeira": historico[0]["data"],
                "ultima": historico[-1]["data"],
                "cultos": cultos,
                "historico": historico,
                "genero": None,
                "origem": None,
            }
        )
    pessoas.sort(key=lambda p: (-p["visitas"], p["nome"].lower()))

    retornaram = sum(1 for p in pessoas if p["visitas"] > 1)
    freq = Counter(p["visitas"] for p in pessoas)
    domingos = [r["count"] for r in ranking if r["weekday"] == "Domingo"]
    half = len(counts) // 2
    first_half = sum(counts[:half]) or 1
    second_half = sum(counts[half:]) or 0
    tendencia = round((second_half - first_half) / first_half * 100, 1)

    return {
        "meta": {
            "igreja": "Sara Nossa Terra — Morumbi Sul",
            "fonte": "datatable-sem-trilha.csv",
            "periodo_inicio": ranking[0]["date"] if ranking else None,
            "periodo_fim": ranking[-1]["date"] if ranking else None,
            "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        "cultos": [
            {"id": c["id"], "nome": c["nome"], "dia": c["dia"], "nota": c.get("nota")}
            for c in CULTOS.values()
        ],
        "total_visitantes": len(records),
        "n_cultos": len(ranking),
        "visitantes_unicos": len(pessoas),
        "retornaram": retornaram,
        "media_por_culto": round(len(records) / len(ranking), 2) if ranking else 0,
        "maior_culto": max(ranking, key=lambda r: r["count"]) if ranking else None,
        "menor_culto": min(ranking, key=lambda r: r["count"]) if ranking else None,
        "ranking_cultos": sorted(ranking, key=lambda r: (-r["count"], r["date_iso"])),
        "evolucao": evolucao,
        "dist_culto": [
            {
                "id": cid,
                "nome": next(c["nome"] for c in CULTOS.values() if c["id"] == cid),
                "count": dist_culto[cid],
            }
            for cid in ["fe-milagres", "quinta-profetica", "arena", "culto-familia"]
        ],
        "dist_weekday": [
            {"day": day, "count": dist_weekday.get(day, 0)}
            for day in ["Terça", "Quinta", "Sábado", "Domingo"]
        ],
        "media_domingo": round(sum(domingos) / len(domingos), 2) if domingos else None,
        "crescimento_mensal": crescimento,
        "novos_por_mes": [{"month": m, "count": novos[m]} for m in months],
        "mes_mais_visitantes": max(
            ({"month": m, "count": by_month[m]} for m in months), key=lambda x: x["count"]
        )
        if months
        else None,
        "freq_dist": [{"visits": v, "people": freq[v]} for v in sorted(freq)],
        "top_recorrentes": [
            {"name": p["nome"], "visits": p["visitas"]}
            for p in pessoas[:15]
            if p["visitas"] > 1
        ],
        "tendencia_pct": tendencia,
        "genero": {"masculino": 0, "feminino": 0, "nao_informado": len(records)},
        "origem": [],
        "registros": records,
        "pessoas": pessoas,
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sara Morumbi Sul — Painel de Visitantes</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#000;--bg2:#0a0a0a;--card:#111;--card2:#161616;--line:#222;--line2:#2a2a2a;
  --text:#fff;--muted:#8a8a8a;--dim:#555;--glow:rgba(255,255,255,.04);
  --radius:14px;--radius-sm:10px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
button,input,select{font:inherit}

/* flame watermark */
body::before{
  content:'';position:fixed;top:0;right:-80px;width:420px;height:420px;opacity:.03;pointer-events:none;z-index:0;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 100'%3E%3Cpath fill='%23fff' d='M40 5c-8 18-22 28-18 48 2 10 10 18 18 22 8-4 16-12 18-22 4-20-10-30-18-48z'/%3E%3C/svg%3E") center/contain no-repeat;
}

/* header */
.topbar{
  position:sticky;top:0;z-index:100;background:rgba(0,0,0,.92);backdrop-filter:blur(16px);
  border-bottom:1px solid var(--line);
}
.topbar-inner{max-width:1320px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:14px;min-width:0}
.brand img{height:42px;width:auto;object-fit:contain}
.brand-text{display:flex;flex-direction:column;line-height:1.1}
.brand-text .sub{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);font-weight:600}
.brand-text .main{font-size:15px;font-weight:700;letter-spacing:-.02em}

.tabs{display:flex;gap:4px;margin-left:auto;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px}
.tab{
  border:0;background:transparent;color:var(--muted);padding:8px 16px;border-radius:999px;
  font-size:13px;font-weight:600;cursor:pointer;transition:.2s;
}
.tab:hover{color:var(--text)}
.tab.active{background:#fff;color:#000}

/* filters */
.filters{
  max-width:1320px;margin:0 auto;padding:16px 24px 0;
  display:grid;grid-template-columns:1fr 1fr auto auto;gap:12px;align-items:end;
}
.filter-group label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700;margin-bottom:6px}
.filter-group input,.filter-group select{
  width:100%;background:var(--card);border:1px solid var(--line2);color:var(--text);
  border-radius:var(--radius-sm);padding:10px 12px;outline:none;
}
.filter-group input:focus,.filter-group select:focus{border-color:#555}
.culto-chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{
  border:1px solid var(--line2);background:var(--card);color:var(--muted);
  padding:7px 12px;border-radius:999px;font-size:12px;font-weight:600;cursor:pointer;transition:.2s;
}
.chip.on{background:#fff;color:#000;border-color:#fff}
.chip .dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;background:currentColor;opacity:.5}
.btn{
  border:1px solid var(--line2);background:var(--card);color:var(--text);
  padding:10px 16px;border-radius:var(--radius-sm);font-size:13px;font-weight:600;cursor:pointer;
}
.btn.primary{background:#fff;color:#000;border-color:#fff}
.btn:hover{opacity:.9}

/* layout */
main{max-width:1320px;margin:0 auto;padding:24px;position:relative;z-index:1}
.page{display:none}
.page.active{display:block}
.hero{
  display:grid;grid-template-columns:1.2fr .8fr;gap:20px;margin-bottom:24px;
}
.hero-card{
  background:linear-gradient(135deg,var(--card) 0%,var(--card2) 100%);
  border:1px solid var(--line);border-radius:var(--radius);padding:28px 32px;position:relative;overflow:hidden;
}
.hero-card::after{
  content:'';position:absolute;right:-20px;bottom:-20px;width:180px;height:180px;opacity:.06;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 100'%3E%3Cpath fill='%23fff' d='M40 5c-8 18-22 28-18 48 2 10 10 18 18 22 8-4 16-12 18-22 4-20-10-30-18-48z'/%3E%3C/svg%3E") center/contain no-repeat;
}
.hero-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:10px}
.hero-num{font-size:clamp(48px,8vw,72px);font-weight:700;letter-spacing:-.04em;line-height:1}
.hero-desc{color:var(--muted);font-size:15px;line-height:1.6;margin-top:10px;max-width:480px}
.hero-side{display:grid;grid-template-rows:1fr 1fr;gap:12px}
.mini-stat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px}
.mini-stat .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700}
.mini-stat .val{font-size:28px;font-weight:700;margin-top:6px}
.mini-stat .sub{font-size:12px;color:var(--muted);margin-top:4px}

.kpi-row{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:24px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px;text-align:center}
.kpi .v{font-size:24px;font-weight:700}
.kpi .l{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-top:4px;font-weight:600}

.section{margin-bottom:28px}
.section-head{display:flex;align-items:baseline;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.section-head h2{font-size:20px;font-weight:700;letter-spacing:-.02em}
.section-head p{font-size:13px;color:var(--muted)}

.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.grid23{display:grid;grid-template-columns:1.4fr 1fr;gap:16px}

.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px}
.card h3{font-size:14px;font-weight:700;margin-bottom:4px}
.card .hint{font-size:12px;color:var(--muted);margin-bottom:14px}
.chart-box{position:relative;width:100%}
.chart-box.h220{height:220px}.chart-box.h260{height:260px}.chart-box.h300{height:300px}

.insight-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.insight{background:var(--card2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:14px 16px}
.insight .tag{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700}
.insight .txt{font-size:13px;margin-top:6px;line-height:1.45}
.insight strong{color:#fff}

.pill{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:999px;font-size:11px;font-weight:700}
.pill.up{background:rgba(255,255,255,.12);color:#fff}
.pill.down{background:rgba(255,255,255,.06);color:var(--muted)}
.pill.gold{background:rgba(255,255,255,.15);color:#fff}

.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.bar-row .bl{width:110px;font-size:12px;color:var(--muted);flex-shrink:0}
.bar-row .bt{flex:1;background:var(--line);border-radius:6px;overflow:hidden;height:8px}
.bar-row .bf{height:100%;border-radius:6px;background:#fff}
.bar-row .bn{width:36px;text-align:right;font-size:12px;font-weight:700;flex-shrink:0}

table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:10px 8px;border-bottom:1px solid var(--line);font-weight:700}
td{padding:10px 8px;border-bottom:1px solid var(--line)}
tr:hover td{background:var(--glow)}
.num{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.rank{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;background:var(--line2);font-size:11px;font-weight:700;margin-right:8px}
.rank.top{background:#fff;color:#000}

.placeholder-box{
  border:1px dashed var(--line2);border-radius:var(--radius-sm);padding:24px;text-align:center;
  background:repeating-linear-gradient(-45deg,transparent,transparent 8px,rgba(255,255,255,.015) 8px,rgba(255,255,255,.015) 16px);
}
.placeholder-box .icon{font-size:28px;opacity:.3;margin-bottom:8px}
.placeholder-box p{font-size:13px;color:var(--muted);line-height:1.5}
.placeholder-box strong{color:var(--text)}

/* pessoal */
.search-bar{
  display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;
}
.search-bar input{
  flex:1;min-width:200px;background:var(--card);border:1px solid var(--line2);color:var(--text);
  border-radius:var(--radius-sm);padding:12px 16px;outline:none;
}
.search-bar input:focus{border-color:#555}
.table-wrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:var(--radius)}
.table-wrap table thead{position:sticky;top:0;background:var(--card);z-index:2}
.badge{display:inline-block;padding:3px 8px;border-radius:6px;font-size:11px;font-weight:600;background:var(--line2);color:var(--muted);margin:2px 2px 2px 0}
.badge.retorno{background:rgba(255,255,255,.12);color:#fff}
.person-detail{
  display:none;margin-top:16px;padding:20px;background:var(--card2);border:1px solid var(--line);border-radius:var(--radius);
}
.person-detail.open{display:block}
.person-detail h4{font-size:16px;margin-bottom:12px}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px}
.detail-item .k{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700}
.detail-item .v{font-size:14px;margin-top:4px}
.visit-timeline{display:flex;flex-wrap:wrap;gap:6px}
.visit-tag{font-size:12px;padding:6px 10px;border-radius:8px;background:var(--line);border:1px solid var(--line2)}

.pagination{display:flex;align-items:center;justify-content:space-between;margin-top:12px;font-size:13px;color:var(--muted)}
.pagination button{padding:8px 14px}

footer{
  max-width:1320px;margin:0 auto;padding:24px;color:var(--dim);font-size:12px;border-top:1px solid var(--line);
}

@media(max-width:1024px){
  .hero,.grid23{grid-template-columns:1fr}
  .kpi-row{grid-template-columns:repeat(3,1fr)}
  .grid2,.grid3{grid-template-columns:1fr}
  .filters{grid-template-columns:1fr 1fr}
}
@media(max-width:640px){
  .tabs{width:100%;margin-left:0;overflow-x:auto}
  .kpi-row{grid-template-columns:repeat(2,1fr)}
  .filters{grid-template-columns:1fr}
  .topbar-inner{padding:12px 16px}
  main{padding:16px}
}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <img src="logo.jpg" alt="Sara Morumbi Sul">
      <div class="brand-text">
        <span class="sub">Sara Nossa Terra</span>
        <span class="main">Morumbi Sul</span>
      </div>
    </div>
    <nav class="tabs" id="navTabs">
      <button class="tab active" data-page="visao">Visão Geral</button>
      <button class="tab" data-page="cultos">Cultos</button>
      <button class="tab" data-page="pessoal">Pessoal</button>
    </nav>
  </div>
</header>

<div class="filters" id="filterBar">
  <div class="filter-group">
    <label>Data inicial</label>
    <input type="date" id="dateFrom">
  </div>
  <div class="filter-group">
    <label>Data final</label>
    <input type="date" id="dateTo">
  </div>
  <div class="filter-group" style="grid-column:span 2">
    <label>Cultos</label>
    <div class="culto-chips" id="cultoChips"></div>
  </div>
  <button class="btn" id="btnReset">Limpar</button>
  <button class="btn primary" id="btnApply">Aplicar</button>
</div>

<main>
  <!-- VISÃO GERAL -->
  <div class="page active" id="page-visao">
    <div class="hero">
      <div class="hero-card">
        <div class="hero-eyebrow">Painel Pastoral · Visitantes</div>
        <div class="hero-num" id="heroTotal">—</div>
        <p class="hero-desc" id="heroDesc">Carregando dados dos cultos oficiais — Terça (Fé e Milagres), Quinta (Quinta Profética), Sábado (Arena) e Domingo (Culto da Família, manhã e noite).</p>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <div class="lbl">Maior culto</div>
          <div class="val" id="heroMaior">—</div>
          <div class="sub" id="heroMaiorMeta"></div>
        </div>
        <div class="mini-stat">
          <div class="lbl">Tendência do período</div>
          <div class="val" id="heroTend">—</div>
          <div class="sub" id="heroTendMeta"></div>
        </div>
      </div>
    </div>

    <div class="kpi-row" id="kpiRow"></div>

    <section class="section">
      <div class="section-head"><h2>Radar pastoral</h2><p>Insights automáticos do filtro atual</p></div>
      <div class="insight-grid" id="insights"></div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Evolução mensal</h2><p>Crescimento e novos rostos por mês</p></div>
      <div class="grid2">
        <div class="card"><h3>Visitantes por mês</h3><div class="hint">Total de registros no período filtrado</div><div class="chart-box h260"><canvas id="chartMes"></canvas></div></div>
        <div class="card"><h3>Novos visitantes</h3><div class="hint">Primeira visita registrada no mês</div><div class="chart-box h260"><canvas id="chartNovos"></canvas></div></div>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Perfil & origem</h2><p>Áreas reservadas para a base atualizada</p></div>
      <div class="grid2">
        <div class="card">
          <h3>Masculino × Feminino</h3>
          <div class="hint">Distribuição por gênero dos visitantes</div>
          <div class="chart-box h220"><canvas id="chartGenero"></canvas></div>
          <div class="placeholder-box" style="margin-top:12px" id="generoPlaceholder">
            <div class="icon">◐</div>
            <p><strong>Aguardando base atualizada</strong><br>Os dados de gênero serão exibidos assim que a planilha for enviada com essa informação.</p>
          </div>
        </div>
        <div class="card">
          <h3>Origem da visita</h3>
          <div class="hint">Como as pessoas chegaram à igreja</div>
          <div class="chart-box h220"><canvas id="chartOrigem"></canvas></div>
          <div class="placeholder-box" style="margin-top:12px" id="origemPlaceholder">
            <div class="icon">◎</div>
            <p><strong>Aguardando base atualizada</strong><br>Barra de origem será preenchida com Instagram, indicação, panfleto, etc.</p>
          </div>
        </div>
      </div>
    </section>
  </div>

  <!-- CULTOS -->
  <div class="page" id="page-cultos">
    <section class="section">
      <div class="section-head"><h2>Distribuição por culto</h2><p>Apenas dias oficiais de culto</p></div>
      <div class="grid23">
        <div class="card"><h3>Visitantes por culto</h3><div class="hint">Fé e Milagres · Quinta Profética · Arena · Culto da Família</div><div class="chart-box h300"><canvas id="chartCultos"></canvas></div></div>
        <div class="card"><h3>Por dia da semana</h3><div class="hint">Volume acumulado no filtro</div><div id="weekdayBars"></div></div>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Linha do tempo</h2><p>Evolução culto a culto com média móvel</p></div>
      <div class="card"><div class="chart-box h300"><canvas id="chartEvolucao"></canvas></div></div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Ranking de cultos</h2><p>Datas com mais visitantes</p></div>
      <div class="card"><div class="table-wrap"><table id="rankingTable"></table></div></div>
    </section>
  </div>

  <!-- PESSOAL -->
  <div class="page" id="page-pessoal">
    <section class="section">
      <div class="section-head"><h2>Consulta de pessoal</h2><p>Busque por nome, telefone ou culto</p></div>
      <div class="grid3" id="pessoasStats" style="margin-bottom:16px"></div>
      <div class="search-bar">
        <input type="search" id="searchPessoa" placeholder="Buscar nome, telefone, e-mail ou culto…">
        <select id="filterRetorno">
          <option value="all">Todos</option>
          <option value="novos">Só 1ª visita</option>
          <option value="retorno">Voltaram +1x</option>
        </select>
      </div>
      <div class="card" style="padding:0">
        <div class="table-wrap">
          <table id="pessoasTable">
            <thead><tr><th>Pessoa</th><th>Contato</th><th>Cultos</th><th>Visitas</th><th>Última visita</th></tr></thead>
            <tbody id="pessoasBody"></tbody>
          </table>
        </div>
        <div class="pagination">
          <span id="pageInfo">—</span>
          <div>
            <button class="btn" id="prevPage">← Anterior</button>
            <button class="btn" id="nextPage">Próxima →</button>
          </div>
        </div>
      </div>
      <div class="person-detail" id="personDetail"></div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Frequência de retorno</h2><p>Quantas vezes cada pessoa visitou</p></div>
      <div class="grid2">
        <div class="card"><div class="chart-box h260"><canvas id="chartFreq"></canvas></div></div>
        <div class="card"><h3>Mais fiéis</h3><div class="hint">Top visitantes recorrentes</div><table id="recorrentesTable"></table></div>
      </div>
    </section>
  </div>
</main>

<footer id="footer"></footer>

<script id="dashboard-data" type="application/json">__DATA_JSON__</script>
<script>
const RAW = JSON.parse(document.getElementById('dashboard-data').textContent);
const CULTOS = RAW.cultos;
const CULT_MAP = Object.fromEntries(CULTOS.map(c => [c.id, c]));

const COLORS = {
  text:'#8a8a8a', grid:'#222', white:'#ffffff',
  cultos:['#ffffff','#cccccc','#999999','#666666'],
  muted:'#444444'
};

Chart.defaults.color = COLORS.text;
Chart.defaults.font.family = "'DM Sans', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.borderColor = COLORS.grid;

let charts = {};
let state = {
  dateFrom: RAW.meta.periodo_inicio ? isoFromBr(RAW.meta.periodo_inicio) : '',
  dateTo: RAW.meta.periodo_fim ? isoFromBr(RAW.meta.periodo_fim) : '',
  cultos: new Set(CULTOS.map(c => c.id)),
  search: '',
  retorno: 'all',
  page: 1,
  pageSize: 25,
  selectedPerson: null
};

function isoFromBr(d){ const [dd,mm,yy]=d.split('/'); return `${yy}-${mm}-${dd}`; }
function brFromIso(iso){ if(!iso) return ''; const [y,m,d]=iso.split('-'); return `${d}/${m}/${y}`; }
function fmtMonth(m){ const [y,mo]=m.split('-'); const n=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']; return n[+mo-1]+'/'+y.slice(2); }

function inRange(iso){
  if(state.dateFrom && iso < state.dateFrom) return false;
  if(state.dateTo && iso > state.dateTo) return false;
  return true;
}

function filterRegistros(){
  return RAW.registros.filter(r => state.cultos.has(r.culto_id) && inRange(r.data_iso));
}

function computeStats(regs){
  const byDate = {}, byPhone = {}, byMonth = {}, novosMonth = {};
  const firstSeen = {};
  const sorted = [...regs].sort((a,b)=>a.data_iso.localeCompare(b.data_iso));

  for(const r of sorted){
    byDate[r.data] = (byDate[r.data]||0) + 1;
    const key = r.telefone_norm || r.nome.toLowerCase();
    if(!byPhone[key]) byPhone[key] = {nome:r.nome, telefone:r.telefone, email:r.email, visitas:0, cultos:new Set(), historico:[]};
    byPhone[key].visitas++;
    byPhone[key].cultos.add(r.culto);
    byPhone[key].historico.push({data:r.data, culto:r.culto});
    byPhone[key].nome = r.nome || byPhone[key].nome;
    const mk = r.data_iso.slice(0,7);
    byMonth[mk] = (byMonth[mk]||0) + 1;
    if(!firstSeen[key]){ firstSeen[key]=r.data_iso; novosMonth[mk]=(novosMonth[mk]||0)+1; }
  }

  const ranking = Object.entries(byDate).map(([date,count])=>{
    const rec = sorted.find(x=>x.data===date);
    return {date, date_iso:rec.data_iso, count, weekday:rec.weekday, culto_id:rec.culto_id, culto:rec.culto};
  }).sort((a,b)=>a.date_iso.localeCompare(b.date_iso));

  const counts = ranking.map(r=>r.count);
  const evolucao = ranking.map((r,i)=>{
    const chunk = counts.slice(Math.max(0,i-2), i+1);
    return {...r, ma3: Math.round(chunk.reduce((a,b)=>a+b,0)/chunk.length*100)/100};
  });

  const distCulto = CULTOS.map(c=>({...c, count: regs.filter(r=>r.culto_id===c.id).length}));
  const distWd = ['Terça','Quinta','Sábado','Domingo'].map(day=>({day, count: regs.filter(r=>r.weekday===day).length}));

  const months = [...new Set(Object.keys(byMonth))].sort();
  const crescimento = months.map((m,i)=>{
    const count = byMonth[m];
    const prev = i? byMonth[months[i-1]] : null;
    const pct = prev? Math.round((count-prev)/prev*1000)/10 : null;
    return {month:m, count, pct};
  });

  const pessoas = Object.values(byPhone).map(p=>{
    const hist = p.historico;
    return {
      nome: p.nome||'Sem nome', telefone:p.telefone, email:p.email||'',
      visitas:p.visitas, cultos:[...p.cultos], historico:hist,
      primeira:hist[0].data, ultima:hist[hist.length-1].data
    };
  }).sort((a,b)=>b.visitas-a.visitas || a.nome.localeCompare(b.nome));

  const retornaram = pessoas.filter(p=>p.visitas>1).length;
  const freq = {};
  pessoas.forEach(p=>{ freq[p.visitas]=(freq[p.visitas]||0)+1; });

  const maior = ranking.length? ranking.reduce((a,b)=>b.count>a.count?b:a) : null;
  const menor = ranking.length? ranking.reduce((a,b)=>b.count<a.count?b:a) : null;
  const media = ranking.length? Math.round(regs.length/ranking.length*100)/100 : 0;

  const half = Math.floor(counts.length/2);
  const t1 = counts.slice(0,half).reduce((a,b)=>a+b,0);
  const t2 = counts.slice(half).reduce((a,b)=>a+b,0);
  const tendencia = t1? Math.round((t2-t1)/t1*1000)/10 : 0;

  return {
    total: regs.length, n_cultos: ranking.length, unicos: pessoas.length, retornaram, media,
    maior, menor, ranking: [...ranking].sort((a,b)=>b.count-a.count),
    evolucao, distCulto, distWd, crescimento,
    novos_por_mes: months.map(m=>({month:m, count:novosMonth[m]||0})),
    pessoas, freq, tendencia
  };
}

function destroyChart(id){ if(charts[id]){ charts[id].destroy(); delete charts[id]; } }

function renderKPIs(s){
  const items = [
    {v:s.total, l:'Registros'},
    {v:s.unicos, l:'Únicos'},
    {v:s.n_cultos, l:'Cultos'},
    {v:s.media, l:'Média/culto'},
    {v:s.maior?s.maior.count:'—', l:'Maior culto'},
    {v:s.retornaram, l:'Retornaram'},
  ];
  document.getElementById('kpiRow').innerHTML = items.map(i=>`<div class="kpi"><div class="v">${i.v}</div><div class="l">${i.l}</div></div>`).join('');
}

function renderHero(s){
  document.getElementById('heroTotal').textContent = s.total;
  const cultoLabel = [...state.cultos].map(id=>CULT_MAP[id]?.nome).filter(Boolean).join(' · ') || 'todos os cultos';
  document.getElementById('heroDesc').textContent =
    `${s.total} visitantes em ${s.n_cultos} cultos (${cultoLabel}). Período: ${brFromIso(state.dateFrom)||'…'} a ${brFromIso(state.dateTo)||'…'}.`;
  if(s.maior){
    document.getElementById('heroMaior').textContent = s.maior.count;
    document.getElementById('heroMaiorMeta').textContent = `${s.maior.date} · ${s.maior.culto}`;
  }
  const sign = s.tendencia>=0?'+':'';
  document.getElementById('heroTend').textContent = `${sign}${s.tendencia}%`;
  document.getElementById('heroTendMeta').textContent = s.tendencia>=0? '2ª metade vs 1ª metade — em alta' : '2ª metade vs 1ª metade — em queda';
}

function renderInsights(s){
  const insights = [];
  if(s.maior) insights.push({tag:'Pico', txt:`O maior fluxo foi <strong>${s.maior.count} visitantes</strong> em ${s.maior.date} (${s.maior.culto}).`});
  if(s.distCulto.length){
    const top = [...s.distCulto].sort((a,b)=>b.count-a.count)[0];
    insights.push({tag:'Culto líder', txt:`<strong>${top.nome}</strong> concentra ${top.count} registros (${Math.round(top.count/s.total*100)||0}% do total).`});
  }
  const pctRet = s.unicos? Math.round(s.retornaram/s.unicos*1000)/10 : 0;
  insights.push({tag:'Retorno', txt:`<strong>${s.retornaram}</strong> pessoas voltaram mais de uma vez (${pctRet}% dos únicos).`});
  if(s.crescimento.length>1){
    const last = s.crescimento[s.crescimento.length-1];
    if(last.pct!==null) insights.push({tag:'Mês recente', txt:`Último mês: <strong>${last.count}</strong> visitantes (${last.pct>=0?'+':''}${last.pct}% vs anterior).`});
  }
  const abaixo = s.ranking.filter(r=>r.count < s.media * 0.6);
  if(abaixo.length) insights.push({tag:'Atenção', txt:`<strong>${abaixo.length}</strong> culto(s) abaixo de 60% da média — oportunidade de acompanhamento.`});
  document.getElementById('insights').innerHTML = insights.map(i=>`<div class="insight"><div class="tag">${i.tag}</div><div class="txt">${i.txt}</div></div>`).join('');
}

function chartOpts(extra={}){
  return {
    responsive:true, maintainAspectRatio:false,
    plugins:{legend:{labels:{color:COLORS.text, boxWidth:12, usePointStyle:true}}},
    scales:{
      x:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text}},
      y:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text}, beginAtZero:true}
    },
    ...extra
  };
}

function renderCharts(s){
  destroyChart('mes');
  charts.mes = new Chart(document.getElementById('chartMes'),{
    type:'bar',
    data:{labels:s.crescimento.map(d=>fmtMonth(d.month)), datasets:[{data:s.crescimento.map(d=>d.count), backgroundColor:COLORS.white, borderRadius:6, maxBarThickness:48}]},
    options:chartOpts({plugins:{legend:{display:false}, tooltip:{callbacks:{afterLabel:ctx=>{const p=s.crescimento[ctx.dataIndex].pct; return p===null?'':`${p>=0?'+':''}${p}% vs mês ant.`;}}}}})
  });

  destroyChart('novos');
  charts.novos = new Chart(document.getElementById('chartNovos'),{
    type:'bar',
    data:{labels:s.novos_por_mes.map(d=>fmtMonth(d.month)), datasets:[{data:s.novos_por_mes.map(d=>d.count), backgroundColor:COLORS.muted, borderRadius:6, maxBarThickness:48}]},
    options:chartOpts({plugins:{legend:{display:false}}})
  });

  destroyChart('cultos');
  charts.cultos = new Chart(document.getElementById('chartCultos'),{
    type:'doughnut',
    data:{labels:s.distCulto.map(d=>d.nome), datasets:[{data:s.distCulto.map(d=>d.count), backgroundColor:COLORS.cultos, borderWidth:0}]},
    options:{responsive:true, maintainAspectRatio:false, cutout:'62%', plugins:{legend:{position:'right', labels:{color:COLORS.text, padding:14}}}}
  });

  destroyChart('evolucao');
  charts.evolucao = new Chart(document.getElementById('chartEvolucao'),{
    data:{
      labels:s.evolucao.map(d=>d.date.slice(0,5)),
      datasets:[
        {type:'bar', label:'Visitantes', data:s.evolucao.map(d=>d.count), backgroundColor:'rgba(255,255,255,.15)', borderRadius:3, maxBarThickness:12, order:2},
        {type:'line', label:'Média móvel (3)', data:s.evolucao.map(d=>d.ma3), borderColor:COLORS.white, pointRadius:0, borderWidth:2, tension:.35, order:1}
      ]
    },
    options:chartOpts({interaction:{mode:'index',intersect:false}, scales:{x:{ticks:{maxRotation:90,minRotation:90,maxTicksLimit:20}}}})
  });

  destroyChart('freq');
  charts.freq = new Chart(document.getElementById('chartFreq'),{
    type:'bar',
    data:{labels:Object.keys(s.freq).map(v=>v==='1'?'1 visita':v+' visitas'), datasets:[{data:Object.values(s.freq), backgroundColor:COLORS.white, borderRadius:6}]},
    options:chartOpts({indexAxis:'y', plugins:{legend:{display:false}}})
  });

  // Placeholder charts
  destroyChart('genero');
  const g = RAW.genero;
  const hasGenero = g.masculino + g.feminino > 0;
  document.getElementById('generoPlaceholder').style.display = hasGenero? 'none':'block';
  charts.genero = new Chart(document.getElementById('chartGenero'),{
    type:'doughnut',
    data:{labels:['Masculino','Feminino','Não informado'], datasets:[{data:[g.masculino,g.feminino,g.nao_informado], backgroundColor:['#fff','#aaa','#333'], borderWidth:0}]},
    options:{responsive:true, maintainAspectRatio:false, cutout:'55%', plugins:{legend:{position:'bottom', labels:{color:COLORS.text}}}}
  });

  destroyChart('origem');
  const origens = RAW.origem || [];
  const hasOrigem = origens.length > 0;
  document.getElementById('origemPlaceholder').style.display = hasOrigem? 'none':'block';
  charts.origem = new Chart(document.getElementById('chartOrigem'),{
    type:'bar',
    data:{labels: hasOrigem? origens.map(o=>o.nome):['—'], datasets:[{data: hasOrigem? origens.map(o=>o.count):[0], backgroundColor:COLORS.muted, borderRadius:6}]},
    options:chartOpts({indexAxis:'y', plugins:{legend:{display:false}}})
  });
}

function renderWeekday(s){
  const max = Math.max(...s.distWd.map(d=>d.count), 1);
  document.getElementById('weekdayBars').innerHTML = s.distWd.map(d=>`
    <div class="bar-row"><div class="bl">${d.day}</div><div class="bt"><div class="bf" style="width:${(d.count/max*100).toFixed(1)}%"></div></div><div class="bn">${d.count}</div></div>
  `).join('');
}

function renderRanking(s){
  const rows = s.ranking.slice(0,20).map((r,i)=>`
    <tr><td><span class="rank ${i<3?'top':''}">${i+1}</span>${r.date}</td><td>${r.culto}</td><td>${r.weekday}</td><td class="num">${r.count}</td></tr>
  `).join('');
  document.getElementById('rankingTable').innerHTML = `<thead><tr><th>Data</th><th>Culto</th><th>Dia</th><th style="text-align:right">Visitantes</th></tr></thead><tbody>${rows}</tbody>`;
}

function renderPessoasStats(s){
  const pct = s.unicos? ((s.retornaram/s.unicos)*100).toFixed(1) : 0;
  const top = s.pessoas.find(p=>p.visitas>1) || s.pessoas[0];
  document.getElementById('pessoasStats').innerHTML = `
    <div class="card"><h3>Únicos</h3><div class="hint">Identificados por telefone</div><div style="font-size:32px;font-weight:700;margin-top:8px">${s.unicos}</div></div>
    <div class="card"><h3>Retorno</h3><div class="hint">${pct}% voltaram +1x</div><div style="font-size:32px;font-weight:700;margin-top:8px">${s.retornaram}</div></div>
    <div class="card"><h3>Mais fiel</h3><div class="hint">${top?top.nome:'—'}</div><div style="font-size:32px;font-weight:700;margin-top:8px">${top?top.visitas+'x':'—'}</div></div>
  `;
}

function filteredPessoas(s){
  let list = s.pessoas;
  const q = state.search.toLowerCase().trim();
  if(q) list = list.filter(p =>
    p.nome.toLowerCase().includes(q) || p.telefone.includes(q) ||
    (p.email&&p.email.toLowerCase().includes(q)) || p.cultos.some(c=>c.toLowerCase().includes(q))
  );
  if(state.retorno==='novos') list = list.filter(p=>p.visitas===1);
  if(state.retorno==='retorno') list = list.filter(p=>p.visitas>1);
  return list;
}

function renderPessoasTable(s){
  const list = filteredPessoas(s);
  const totalPages = Math.max(1, Math.ceil(list.length / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page-1)*state.pageSize;
  const page = list.slice(start, start+state.pageSize);

  document.getElementById('pessoasBody').innerHTML = page.map((p,i)=>`
    <tr data-idx="${start+i}" style="cursor:pointer">
      <td><strong>${p.nome}</strong>${p.visitas>1?'<span class="badge retorno">retorno</span>':''}</td>
      <td>${p.telefone||'—'}<br><span style="color:var(--muted);font-size:11px">${p.email||''}</span></td>
      <td>${p.cultos.map(c=>`<span class="badge">${c}</span>`).join('')}</td>
      <td class="num">${p.visitas}</td>
      <td>${p.ultima}</td>
    </tr>
  `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:32px">Nenhuma pessoa encontrada</td></tr>';

  document.getElementById('pageInfo').textContent = `${list.length} pessoas · página ${state.page}/${totalPages}`;
  document.getElementById('prevPage').disabled = state.page<=1;
  document.getElementById('nextPage').disabled = state.page>=totalPages;

  document.querySelectorAll('#pessoasBody tr[data-idx]').forEach(tr=>{
    tr.onclick = ()=> showPersonDetail(list[+tr.dataset.idx]);
  });
}

function showPersonDetail(p){
  const el = document.getElementById('personDetail');
  el.className = 'person-detail open';
  el.innerHTML = `
    <h4>${p.nome}</h4>
    <div class="detail-grid">
      <div class="detail-item"><div class="k">Telefone</div><div class="v">${p.telefone||'—'}</div></div>
      <div class="detail-item"><div class="k">E-mail</div><div class="v">${p.email||'—'}</div></div>
      <div class="detail-item"><div class="k">Total de visitas</div><div class="v">${p.visitas}</div></div>
      <div class="detail-item"><div class="k">Primeira / Última</div><div class="v">${p.primeira} → ${p.ultima}</div></div>
    </div>
    <div class="detail-item"><div class="k">Histórico de cultos</div>
      <div class="visit-timeline">${p.historico.map(v=>`<span class="visit-tag">${v.data} · ${v.culto}</span>`).join('')}</div>
    </div>
  `;
  el.scrollIntoView({behavior:'smooth', block:'nearest'});
}

function renderRecorrentes(s){
  const top = s.pessoas.filter(p=>p.visitas>1).slice(0,10);
  document.getElementById('recorrentesTable').innerHTML = `
    <thead><tr><th>Nome</th><th style="text-align:right">Visitas</th></tr></thead>
    <tbody>${top.map((r,i)=>`<tr><td><span class="rank ${i<3?'top':''}">${i+1}</span>${r.nome}</td><td class="num">${r.visitas}x</td></tr>`).join('')}</tbody>
  `;
}

function renderAll(){
  const regs = filterRegistros();
  const s = computeStats(regs);
  renderHero(s); renderKPIs(s); renderInsights(s);
  renderCharts(s); renderWeekday(s); renderRanking(s);
  renderPessoasStats(s); renderPessoasTable(s); renderRecorrentes(s);
  document.getElementById('footer').innerHTML =
    `Sara Morumbi Sul · ${RAW.meta.fonte} · ${s.total} registros em cultos oficiais · gerado em ${RAW.meta.gerado_em}`;
}

// Init filters UI
(function init(){
  document.getElementById('dateFrom').value = state.dateFrom;
  document.getElementById('dateTo').value = state.dateTo;
  document.getElementById('cultoChips').innerHTML = CULTOS.map(c=>`
    <button class="chip on" data-id="${c.id}" title="${c.nota||''}"><span class="dot"></span>${c.dia} · ${c.nome}${c.nota?` (${c.nota})`:''}</button>
  `).join('');

  document.getElementById('cultoChips').onclick = e=>{
    const chip = e.target.closest('.chip'); if(!chip) return;
    const id = chip.dataset.id;
    chip.classList.toggle('on');
    if(chip.classList.contains('on')) state.cultos.add(id); else state.cultos.delete(id);
    if(!state.cultos.size) state.cultos.add(id), chip.classList.add('on');
    renderAll();
  };

  document.getElementById('btnApply').onclick = ()=>{
    state.dateFrom = document.getElementById('dateFrom').value;
    state.dateTo = document.getElementById('dateTo').value;
    state.page = 1; renderAll();
  };
  document.getElementById('btnReset').onclick = ()=>{
    state.dateFrom = isoFromBr(RAW.meta.periodo_inicio);
    state.dateTo = isoFromBr(RAW.meta.periodo_fim);
    state.cultos = new Set(CULTOS.map(c=>c.id));
    document.getElementById('dateFrom').value = state.dateFrom;
    document.getElementById('dateTo').value = state.dateTo;
    document.querySelectorAll('.chip').forEach(c=>c.classList.add('on'));
    state.search=''; state.retorno='all'; state.page=1;
    document.getElementById('searchPessoa').value='';
    document.getElementById('filterRetorno').value='all';
    renderAll();
  };

  document.getElementById('navTabs').onclick = e=>{
    const tab = e.target.closest('.tab'); if(!tab) return;
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('page-'+tab.dataset.page).classList.add('active');
  };

  document.getElementById('searchPessoa').oninput = e=>{ state.search=e.target.value; state.page=1; renderAll(); };
  document.getElementById('filterRetorno').onchange = e=>{ state.retorno=e.target.value; state.page=1; renderAll(); };
  document.getElementById('prevPage').onclick = ()=>{ if(state.page>1){ state.page--; renderAll(); }};
  document.getElementById('nextPage').onclick = ()=>{ state.page++; renderAll(); };

  renderAll();
})();
</script>
</body>
</html>
"""


def main():
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    records = build_records(rows)
    data = aggregate(records)
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("__DATA_JSON__", json_str)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"OK: {OUT_HTML.name} ({len(records)} registros, {len(html)//1024} KB)")


if __name__ == "__main__":
    main()
