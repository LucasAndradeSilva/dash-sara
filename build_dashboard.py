#!/usr/bin/env python3
"""Gera dashboard-visitantes.html com dados embutidos."""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "datatable-sem-trilha.csv"
XLSX_PATH = ROOT / "visitantes-2.0.xlsx"
MEMBROS_XLSX_PATH = ROOT / "membros-2.0.xlsx"
OUT_HTML = ROOT / "dashboard-visitantes.html"
INDEX_HTML = ROOT / "index.html"
OUT_JSON = ROOT / "dashboard-data.json"
CHARTJS_PATH = ROOT / "vendor" / "chart.umd.min.js"

CULTOS = {
    "fe-milagres": {"id": "fe-milagres", "nome": "Fé e Milagres", "dia": "Terça"},
    "quinta-profetica": {
        "id": "quinta-profetica",
        "nome": "Quinta Profética",
        "dia": "Quinta",
    },
    "arena": {"id": "arena", "nome": "Arena", "dia": "Sábado"},
    "culto-familia-manha": {
        "id": "culto-familia-manha",
        "nome": "Culto da Família (Manhã)",
        "dia": "Domingo",
        "nota": "Domingo · Manhã",
    },
    "culto-familia-noite": {
        "id": "culto-familia-noite",
        "nome": "Culto da Família (Noite)",
        "dia": "Domingo",
        "nota": "Domingo · Noite",
    },
    "culto-familia": {
        "id": "culto-familia",
        "nome": "Culto da Família",
        "dia": "Domingo",
        "nota": "Domingo · sem horário",
    },
}
CULTO_ORDER = [
    "fe-milagres",
    "quinta-profetica",
    "arena",
    "culto-familia-manha",
    "culto-familia-noite",
    "culto-familia",
]
CULTOS_BY_WEEKDAY = {
    1: CULTOS["fe-milagres"],
    3: CULTOS["quinta-profetica"],
    5: CULTOS["arena"],
}
CULTO_WEEKDAY = {
    "fe-milagres": 1,
    "quinta-profetica": 3,
    "arena": 5,
    "culto-familia-manha": 6,
    "culto-familia-noite": 6,
    "culto-familia": 6,
}
WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def parse_date(value: str):
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def norm_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def dedupe_key(row) -> tuple:
    """Mesmo nome + celular + data + horário = duplicata. Manhã e noite no mesmo dia são distintos."""
    return (
        norm_name(row.get("Nome")),
        norm_phone(row.get("Celular")),
        row.get("Data de Cadastro"),
        row.get("Hora de Cadastro") or "",
    )


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


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s or s in {"-", "nan", "NaT", "None"}:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            if fmt == "%d/%m/%Y %H:%M":
                return datetime.strptime(s[:16], fmt)
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def valid_visit_date(dt: datetime | None) -> bool:
    return bool(dt and 2020 <= dt.year <= 2030)


def normalize_genero(value) -> str | None:
    if not value:
        return None
    s = re.sub(r"[^\w\s]", "", str(value).lower())
    if "femin" in s:
        return "feminino"
    if "masc" in s:
        return "masculino"
    return None


def normalize_origem(value) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    return s if s and s not in {"-", "nan", "None"} else None


def fold_text(value: str) -> str:
    s = str(value or "").lower()
    replacements = str.maketrans(
        {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ü": "u",
            "ç": "c",
        }
    )
    return s.translate(replacements)


def parse_count(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or s in {"-", "nan", "None", "NaN", "NaT"}:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def load_csv_rows():
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["Hora de Cadastro"] = ""
    return rows


def load_xlsx_rows():
    if not XLSX_PATH.exists():
        return []
    df = pd.read_excel(XLSX_PATH, header=1)
    rows = []
    for _, item in df.iterrows():
        visita = parse_datetime(item.get("Data da Visita"))
        resposta = parse_datetime(item.get("Data da Resposta"))
        dt = visita if valid_visit_date(visita) else resposta
        if not valid_visit_date(dt):
            continue
        hora = resposta.strftime("%H:%M") if resposta else ""
        rows.append(
            {
                "Nome": str(item.get("Nome Completo") or "").strip(),
                "Email": "",
                "Data de Cadastro": dt.strftime("%d/%m/%Y"),
                "Hora de Cadastro": hora,
                "Celular": str(item.get("Celular") or "").strip(),
                "Contato": str(item.get("Observação") or "").strip(),
                "Sexo": str(item.get("Sexo") or "").strip(),
                "Como Conheceu a Igreja": str(item.get("Como Conheceu a Igreja") or "").strip(),
                "Culto Label": str(item.get("Culto") or "").strip(),
            }
        )
    return rows


def merge_rows(csv_rows, xlsx_rows):
    merged = {}
    order = []

    def add_row(row, prefer_new=False):
        key = dedupe_key(row)
        if key in merged:
            existing = merged[key]
            for field in ("Sexo", "Como Conheceu a Igreja", "Contato", "Culto Label"):
                new_val = row.get(field)
                if new_val and (prefer_new or not existing.get(field)):
                    existing[field] = new_val
            if row.get("Nome") and (prefer_new or not existing.get("Nome")):
                existing["Nome"] = row["Nome"]
        else:
            merged[key] = dict(row)
            order.append(key)

    for row in csv_rows:
        add_row(row)
    for row in xlsx_rows:
        add_row(row, prefer_new=True)

    return [merged[key] for key in order]


def load_all_rows():
    return merge_rows(load_csv_rows(), load_xlsx_rows())


def resolve_culto(dt: datetime, culto_label: str | None, hora: str | None):
    if dt.weekday() != 6:
        return CULTOS_BY_WEEKDAY.get(dt.weekday())

    label = (culto_label or "").lower()
    if "manh" in label:
        return CULTOS["culto-familia-manha"]
    if "noite" in label:
        return CULTOS["culto-familia-noite"]
    if hora:
        try:
            hour = int(hora.split(":")[0])
            return CULTOS["culto-familia-manha"] if hour < 16 else CULTOS["culto-familia-noite"]
        except (ValueError, IndexError):
            pass
    return CULTOS["culto-familia"]


def resolve_culto_from_label(culto_label: str | None):
    label = fold_text(culto_label or "")
    if not label or label == "-":
        return None
    if "fe e milagres" in label:
        return CULTOS["fe-milagres"]
    if "quinta" in label:
        return CULTOS["quinta-profetica"]
    if "arena" in label:
        return CULTOS["arena"]
    if "familia" in label:
        if "manh" in label:
            return CULTOS["culto-familia-manha"]
        if "noite" in label:
            return CULTOS["culto-familia-noite"]
        return CULTOS["culto-familia"]
    return None


def infer_culto_date(resposta: datetime, culto_id: str) -> datetime:
    """Usa o dia do culto mais recente até a data da resposta."""
    target = CULTO_WEEKDAY.get(culto_id)
    if target is None:
        return resposta
    day = resposta.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(7):
        if day.weekday() == target:
            return day
        day -= timedelta(days=1)
    return resposta


def load_membros_rows():
    if not MEMBROS_XLSX_PATH.exists():
        return []
    df = pd.read_excel(MEMBROS_XLSX_PATH, header=1)
    rows = []
    for _, item in df.iterrows():
        resposta = parse_datetime(item.get("Data da Resposta"))
        if not resposta:
            continue
        culto = resolve_culto_from_label(str(item.get("Culto") or ""))
        if not culto:
            continue
        member_count = parse_count(item.get("Quantidade de Membros"))
        if member_count is None:
            member_count = parse_count(item.get("Quantidade de Adultos"))
        children_count = parse_count(item.get("Quantidade de Crianças")) or 0
        if member_count is None:
            continue
        culto_dt = infer_culto_date(resposta, culto["id"])
        rows.append(
            {
                "id": item.get("#ID"),
                "date": culto_dt.strftime("%d/%m/%Y"),
                "date_iso": iso_date(culto_dt),
                "weekday": WEEKDAYS[culto_dt.weekday()],
                "culto_id": culto["id"],
                "culto": culto["nome"],
                "member_count": member_count,
                "children_count": children_count,
                "culto_label": str(item.get("Culto") or "").strip() or None,
                "resposta": resposta.strftime("%d/%m/%Y %H:%M"),
            }
        )
    culto_pos = {cid: i for i, cid in enumerate(CULTO_ORDER)}
    rows.sort(key=lambda r: (r["date_iso"], culto_pos.get(r["culto_id"], 999)))
    return rows


def build_records(rows):
    records = []
    for row in rows:
        dt = parse_date(row["Data de Cadastro"])
        if not dt or dt.year < 2020:
            continue
        hora = (row.get("Hora de Cadastro") or "").strip() or None
        culto = resolve_culto(dt, row.get("Culto Label"), hora)
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
                "hora": hora,
                "weekday": WEEKDAYS[dt.weekday()],
                "culto_id": culto["id"],
                "culto": culto["nome"],
                "genero": normalize_genero(row.get("Sexo")),
                "origem": normalize_origem(row.get("Como Conheceu a Igreja")),
                "culto_label": (row.get("Culto Label") or "").strip() or None,
            }
        )
    return records


def aggregate(records, participacao=None):
    participacao = participacao or []
    by_culto_date = defaultdict(list)
    by_phone = defaultdict(list)
    for rec in records:
        by_culto_date[(rec["data"], rec["culto_id"])].append(rec)
        if rec["telefone_norm"]:
            by_phone[rec["telefone_norm"]].append(rec)

    culto_pos = {cid: i for i, cid in enumerate(CULTO_ORDER)}
    ranking = []
    for (date, culto_id), items in sorted(
        by_culto_date.items(), key=lambda x: (parse_date(x[0][0]), culto_pos.get(x[0][1], 999))
    ):
        rec = items[0]
        dt = parse_date(date)
        ranking.append(
            {
                "date": date,
                "date_iso": iso_date(dt),
                "count": len(items),
                "weekday": WEEKDAYS[dt.weekday()],
                "culto_id": culto_id,
                "culto": rec["culto"],
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
        historico = [
            {"data": v["data"], "culto": v["culto"], "hora": v.get("hora")}
            for v in visits_sorted
        ]
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
                "genero": next((v["genero"] for v in reversed(visits_sorted) if v.get("genero")), None),
                "origem": next((v["origem"] for v in reversed(visits_sorted) if v.get("origem")), None),
                "observacao": next((v["contato"] for v in reversed(visits_sorted) if v.get("contato")), None),
            }
        )
    pessoas.sort(
        key=lambda p: (
            -datetime.strptime(p["ultima"], "%d/%m/%Y").toordinal(),
            -p["visitas"],
            p["nome"].lower(),
        )
    )

    retornaram = sum(1 for p in pessoas if p["visitas"] > 1)
    freq = Counter(p["visitas"] for p in pessoas)
    domingos = [r["count"] for r in ranking if r["weekday"] == "Domingo"]
    half = len(counts) // 2
    first_half = sum(counts[:half]) or 1
    second_half = sum(counts[half:]) or 0
    tendencia = round((second_half - first_half) / first_half * 100, 1)

    genero_counts = Counter()
    origem_counts = Counter()
    for rec in records:
        genero = rec.get("genero")
        if genero == "masculino":
            genero_counts["masculino"] += 1
        elif genero == "feminino":
            genero_counts["feminino"] += 1
        else:
            genero_counts["nao_informado"] += 1
        if rec.get("origem"):
            origem_counts[rec["origem"]] += 1

    total_membros = sum(p["member_count"] for p in participacao)
    total_criancas = sum(p["children_count"] for p in participacao)
    fontes = ["datatable-sem-trilha.csv", "visitantes-2.0.xlsx"]
    if participacao:
        fontes.append("membros-2.0.xlsx")

    return {
        "meta": {
            "igreja": "Sara Nossa Terra — Morumbi Sul",
            "fonte": " + ".join(fontes),
            "periodo_inicio": ranking[0]["date"] if ranking else None,
            "periodo_fim": ranking[-1]["date"] if ranking else None,
            "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        "cultos": [
            {"id": CULTOS[cid]["id"], "nome": CULTOS[cid]["nome"], "dia": CULTOS[cid]["dia"], "nota": CULTOS[cid].get("nota")}
            for cid in CULTO_ORDER
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
                "nome": CULTOS[cid]["nome"],
                "count": dist_culto[cid],
            }
            for cid in CULTO_ORDER
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
        "genero": {
            "masculino": genero_counts["masculino"],
            "feminino": genero_counts["feminino"],
            "nao_informado": genero_counts["nao_informado"],
        },
        "origem": [
            {"nome": nome, "count": count}
            for nome, count in origem_counts.most_common()
        ],
        "total_membros": total_membros,
        "total_criancas": total_criancas,
        "participacao": participacao,
        "registros": records,
        "pessoas": pessoas,
    }


TEMPLATE_PATH = ROOT / "template.html"


def main():
    rows = load_all_rows()
    records = build_records(rows)
    participacao = load_membros_rows()
    data = aggregate(records, participacao)
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    chartjs_src = CHARTJS_PATH.read_text(encoding="utf-8")
    html = (template.replace("__CHARTJS__", chartjs_src)
            .replace("__STYLE__", (ROOT / "radar.css").read_text(encoding="utf-8"))
            .replace("__APPJS__", (ROOT / "radar.js").read_text(encoding="utf-8"))
            .replace("__DATA_JSON__", json_str.replace("<", "\\u003c")))
    OUT_HTML.write_text(html, encoding="utf-8")
    INDEX_HTML.write_text(html, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: {OUT_HTML.name} e {INDEX_HTML.name} ({len(records)} registros, "
        f"M:{data['genero']['masculino']} F:{data['genero']['feminino']}, "
        f"{len(data['origem'])} origens, {len(participacao)} contagens, "
        f"{data['total_membros']} membros / {data['total_criancas']} crianças, "
        f"{len(html)//1024} KB)"
    )


if __name__ == "__main__":
    main()
