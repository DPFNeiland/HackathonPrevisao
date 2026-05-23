from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_number(value: float | int | str | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if pd.isna(value):
        return "n/a"
    return f"{float(value):,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_integer(value: float | int | str | None) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "n/a"
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100 * float(value):.2f}%"


def build_css() -> str:
    return """
body {
  font-family: "Segoe UI", Arial, sans-serif;
  background: #f5f7fb;
  color: #132238;
  margin: 0;
  padding: 0;
}
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 28px 48px;
}
.hero {
  background: linear-gradient(135deg, #0b2545, #1f4d78);
  color: white;
  padding: 28px;
  border-radius: 18px;
  margin-bottom: 24px;
}
.hero h1, .hero h2 {
  margin: 0 0 10px;
}
.hero p {
  margin: 0;
  color: #d9e4f2;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin: 20px 0 26px;
}
.card {
  background: white;
  border-radius: 16px;
  padding: 18px 18px 16px;
  box-shadow: 0 8px 24px rgba(15, 30, 54, 0.08);
}
.card-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #5f7187;
  margin-bottom: 8px;
}
.card-value {
  font-size: 28px;
  font-weight: 700;
  color: #0b2545;
}
.section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 24px rgba(15, 30, 54, 0.08);
  margin-bottom: 20px;
}
.section h3 {
  margin-top: 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th, td {
  padding: 10px 12px;
  border-bottom: 1px solid #e4eaf1;
  text-align: left;
  vertical-align: top;
}
th {
  background: #edf3f8;
  color: #17324f;
}
tr:nth-child(even) td {
  background: #fafcfe;
}
.pill {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 999px;
  background: #edf3f8;
  color: #17324f;
  font-size: 12px;
  font-weight: 600;
}
.pill-a { background: #d9ecff; color: #0b4b94; }
.pill-b { background: #fef3d2; color: #8a5b00; }
.pill-c { background: #eceff3; color: #4c5b6b; }
a {
  color: #0b4b94;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
.note {
  color: #5f7187;
  font-size: 13px;
}
.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}
.metric-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.metric-item {
  background: #f7f9fc;
  border-radius: 14px;
  padding: 12px;
}
.metric-item strong {
  display: block;
  font-size: 12px;
  text-transform: uppercase;
  color: #5f7187;
  margin-bottom: 6px;
}
.metric-item span {
  font-size: 18px;
  font-weight: 700;
}
.chart-wrap {
  background: #f8fafc;
  border-radius: 14px;
  padding: 10px;
}
.back-link {
  margin-bottom: 14px;
  display: inline-block;
}
"""


def svg_line_chart(
    title: str,
    dates: list[pd.Timestamp],
    series: list[tuple[str, list[float], str]],
    horizontal_lines: list[tuple[str, float, str]] | None = None,
    width: int = 940,
    height: int = 280,
) -> str:
    horizontal_lines = horizontal_lines or []
    left_pad = 54
    right_pad = 18
    top_pad = 28
    bottom_pad = 32
    plot_width = width - left_pad - right_pad
    plot_height = height - top_pad - bottom_pad

    clean_values: list[float] = [0.0]
    for _, values, _ in series:
        clean_values.extend(float(v) for v in values if pd.notna(v))
    for _, value, _ in horizontal_lines:
        if pd.notna(value):
            clean_values.append(float(value))
    y_max = max(clean_values) if clean_values else 1.0
    if y_max <= 0:
        y_max = 1.0
    y_max *= 1.12

    x_count = max(len(dates), 1)
    x_step = plot_width / max(x_count - 1, 1)

    def x_pos(index: int) -> float:
        return left_pad + index * x_step

    def y_pos(value: float) -> float:
        return top_pad + plot_height - (float(value) / y_max) * plot_height

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" aria-label="{escape(title)}">',
        f'<text x="{left_pad}" y="18" font-size="14" font-weight="700" fill="#17324f">{escape(title)}</text>',
        f'<line x1="{left_pad}" y1="{top_pad + plot_height}" x2="{width - right_pad}" y2="{top_pad + plot_height}" stroke="#b9c7d8" stroke-width="1"/>',
        f'<line x1="{left_pad}" y1="{top_pad}" x2="{left_pad}" y2="{top_pad + plot_height}" stroke="#b9c7d8" stroke-width="1"/>',
    ]

    for tick in np.linspace(0, y_max, 5):
        y = y_pos(float(tick))
        parts.append(
            f'<line x1="{left_pad}" y1="{y:.2f}" x2="{width - right_pad}" y2="{y:.2f}" stroke="#e2e9f1" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left_pad - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#5f7187">{format_number(tick, 1)}</text>'
        )

    for label, value, color in horizontal_lines:
        if pd.isna(value):
            continue
        y = y_pos(float(value))
        parts.append(
            f'<line x1="{left_pad}" y1="{y:.2f}" x2="{width - right_pad}" y2="{y:.2f}" stroke="{color}" stroke-width="1.5" stroke-dasharray="6 5"/>'
        )
        parts.append(
            f'<text x="{width - right_pad - 4}" y="{y - 4:.2f}" text-anchor="end" font-size="11" fill="{color}">{escape(label)} = {format_number(value, 1)}</text>'
        )

    for index, date in enumerate([dates[0], dates[len(dates) // 2], dates[-1]] if dates else []):
        actual_index = [0, len(dates) // 2, len(dates) - 1][index]
        x = x_pos(actual_index)
        parts.append(
            f'<text x="{x:.2f}" y="{height - 8}" text-anchor="middle" font-size="11" fill="#5f7187">{escape(date.strftime("%d/%m"))}</text>'
        )

    legend_x = width - right_pad - 180
    legend_y = 18
    for idx, (label, _, color) in enumerate(series):
        ly = legend_y + idx * 16
        parts.append(
            f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 18}" y2="{ly}" stroke="{color}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24}" y="{ly + 4}" font-size="11" fill="#17324f">{escape(label)}</text>'
        )

    for label, values, color in series:
        points = []
        for idx, value in enumerate(values):
            if pd.isna(value):
                continue
            points.append(f"{x_pos(idx):.2f},{y_pos(float(value)):.2f}")
        if points:
            parts.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.4" points="{" ".join(points)}" />'
            )

    parts.append("</svg>")
    return "".join(parts)


def metric_cards(metrics: list[tuple[str, str]]) -> str:
    cards = []
    for label, value in metrics:
        cards.append(
            f'<div class="card"><div class="card-label">{escape(label)}</div><div class="card-value">{escape(value)}</div></div>'
        )
    return f'<div class="card-grid">{"".join(cards)}</div>'


def pill_for_abc(abc_class: str) -> str:
    css = {"A": "pill pill-a", "B": "pill pill-b", "C": "pill pill-c"}.get(abc_class, "pill")
    return f'<span class="{css}">{escape(abc_class)}</span>'


def build_table(headers: list[str], rows: list[list[str]]) -> str:
    head_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = []
    for row in rows:
        body_html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{''.join(body_html)}</tbody></table>"


def product_file_name(location: str, product: str) -> str:
    return f"product_{location}_{product}.html"


def build_product_narrative(row: pd.Series) -> list[str]:
    notes = []
    notes.append(
        f"Classe ABC {row['abc_class']}, lead time de {format_integer(row['lead_time_days'])} dias e politica sugerida com s = {format_integer(row['reorder_point_s'])} e S = {format_integer(row['order_up_to_S'])}."
    )
    if float(row["promo_days"]) > 0:
        notes.append(
            f"O item passou por {format_integer(row['promo_days'])} dias promocionais no periodo analisado, entao a politica precisa suportar picos de demanda."
        )
    if float(row["service_level_delta_vs_actual"]) > 0:
        notes.append(
            f"A simulacao melhora o nivel de servico em {format_pct(row['service_level_delta_vs_actual'])} contra o saldo historico observado."
        )
    else:
        notes.append(
            f"A simulacao ainda nao supera o servico observado; o item merece recalibracao de seguranca ou cobertura."
        )
    if float(row["inventory_value_delta_vs_actual"]) < 0:
        notes.append(
            f"O capital medio simulado fica abaixo do historico em R$ {format_number(abs(row['inventory_value_delta_vs_actual']))} por dia."
        )
    else:
        notes.append(
            f"O capital medio simulado fica acima do historico em R$ {format_number(row['inventory_value_delta_vs_actual'])} por dia."
        )
    if float(row["total_lost_sales_units"]) > 0:
        notes.append(
            f"Mesmo com a politica sugerida ainda existem {format_number(row['total_lost_sales_units'])} unidades perdidas na simulacao, o que pode justificar revisar z ou review_days."
        )
    return notes


def write_product_report(
    output_dir: Path,
    metrics_row: pd.Series,
    daily: pd.DataFrame,
) -> None:
    dates = list(pd.to_datetime(daily["date"]))
    demand_chart = svg_line_chart(
        title="Demanda real vs forecast diario",
        dates=dates,
        series=[
            ("Demanda real", list(daily["actual_demand"]), "#1f4d78"),
            ("Forecast", list(daily["forecast_demand"]), "#c9681f"),
        ],
    )
    inventory_chart = svg_line_chart(
        title="Saldo real vs estoque simulado",
        dates=dates,
        series=[
            ("Saldo real", list(daily["actual_balance"]), "#64748b"),
            ("Estoque simulado", list(daily["ending_inventory"]), "#0b4b94"),
        ],
        horizontal_lines=[
            ("s", float(metrics_row["reorder_point_s"]), "#b45309"),
            ("S", float(metrics_row["order_up_to_S"]), "#047857"),
        ],
    )

    order_rows = []
    for row in daily[daily["order_qty"] > 0].itertuples(index=False):
        order_rows.append(
            [
                escape(pd.to_datetime(row.date).strftime("%d/%m/%Y")),
                format_integer(row.order_qty),
                escape(pd.to_datetime(row.arrival_date).strftime("%d/%m/%Y"))
                if pd.notna(row.arrival_date)
                else "n/a",
                format_number(row.ordering_cost),
            ]
        )
    if not order_rows:
        order_rows = [["-", "-", "-", "-"]]

    notes_html = "".join(f"<li>{escape(note)}</li>" for note in build_product_narrative(metrics_row))

    metric_items = [
        ("Servico simulado", format_pct(metrics_row["service_level"])),
        ("Servico real", format_pct(metrics_row["actual_service_level"])),
        ("Capital medio simulado", f"R$ {format_number(metrics_row['avg_inventory_value'])}"),
        ("Capital medio real", f"R$ {format_number(metrics_row['actual_avg_inventory_value'])}"),
        ("Demanda Q4", format_number(metrics_row["total_actual_demand"])),
        ("Forecast Q4", format_number(metrics_row["forecast_units"])),
        ("Pedidos emitidos", format_integer(metrics_row["total_orders"])),
        ("Perda simulada", format_number(metrics_row["total_lost_sales_units"])),
    ]

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Analise SKU {escape(str(metrics_row['product']))} | Loja {escape(str(metrics_row['location']))}</title>
  <style>{build_css()}</style>
</head>
<body>
  <div class="page">
    <a class="back-link" href="../index.html">Voltar para o painel principal</a>
    <div class="hero">
      <h1>{escape(str(metrics_row['product_name']))}</h1>
      <p>SKU {escape(str(metrics_row['product']))} | Loja {escape(str(metrics_row['location']))} | Classe {escape(str(metrics_row['abc_class']))}</p>
    </div>

    {metric_cards(metric_items)}

    <div class="section">
      <h3>Leitura rapida</h3>
      <ul>{notes_html}</ul>
    </div>

    <div class="section">
      <h3>Parametros da politica</h3>
      <div class="metric-list">
        <div class="metric-item"><strong>reorder_point_s</strong><span>{format_integer(metrics_row['reorder_point_s'])}</span></div>
        <div class="metric-item"><strong>order_up_to_S</strong><span>{format_integer(metrics_row['order_up_to_S'])}</span></div>
        <div class="metric-item"><strong>Lead time</strong><span>{format_integer(metrics_row['lead_time_days'])} dias</span></div>
        <div class="metric-item"><strong>z calibrado</strong><span>{format_number(metrics_row['z_value'], 2)}</span></div>
        <div class="metric-item"><strong>Cobertura</strong><span>{format_integer(metrics_row['review_days'])} dias</span></div>
        <div class="metric-item"><strong>Batch minimo</strong><span>{format_integer(metrics_row['minimum_delivery_batch'])}</span></div>
      </div>
    </div>

    <div class="two-col">
      <div class="section chart-wrap">{demand_chart}</div>
      <div class="section chart-wrap">{inventory_chart}</div>
    </div>

    <div class="section">
      <h3>Pedidos simulados</h3>
      {build_table(["Data do pedido", "Qtd", "Chegada", "Custo"], order_rows)}
    </div>
  </div>
</body>
</html>"""

    file_path = output_dir / product_file_name(str(metrics_row["location"]), str(metrics_row["product"]))
    file_path.write_text(html, encoding="utf-8")


def write_index_report(
    output_dir: Path,
    overall_metrics: dict[str, float],
    tuning_results: pd.DataFrame,
    sku_metrics: pd.DataFrame,
    run_metadata: dict[str, str],
) -> None:
    cards = metric_cards(
        [
            ("Servico simulado", format_pct(overall_metrics["service_level"])),
            ("Servico real", format_pct(overall_metrics["actual_service_level"])),
            ("Capital medio simulado", f"R$ {format_number(overall_metrics['avg_inventory_value'])}"),
            ("Capital medio real", f"R$ {format_number(overall_metrics['actual_avg_inventory_value'])}"),
            ("Pedidos emitidos", format_integer(overall_metrics["total_orders"])),
            ("Custo total de pedido", f"R$ {format_number(overall_metrics['total_ordering_cost'])}"),
        ]
    )

    top_tuning = tuning_results.head(10).copy()
    tuning_rows = []
    for row in top_tuning.itertuples(index=False):
        tuning_rows.append(
            [
                format_number(row.z_value, 2),
                format_integer(row.review_days),
                format_pct(row.service_level),
                f"R$ {format_number(row.avg_inventory_value)}",
                f"R$ {format_number(row.total_ordering_cost)}",
                format_number(row.objective),
            ]
        )

    sku_rows = []
    for row in sku_metrics.sort_values(["abc_class", "forecast_units"], ascending=[True, False]).itertuples(
        index=False
    ):
        file_name = product_file_name(str(row.location), str(row.product))
        sku_rows.append(
            [
                f'<a href="products/{escape(file_name)}">{escape(str(row.product_name))}</a><div class="note">SKU {escape(str(row.product))} | Loja {escape(str(row.location))}</div>',
                pill_for_abc(str(row.abc_class)),
                format_pct(row.service_level),
                format_pct(row.actual_service_level),
                f"R$ {format_number(row.avg_inventory_value)}",
                format_number(row.total_actual_demand),
                format_number(row.total_lost_sales_units),
                format_integer(row.reorder_point_s),
                format_integer(row.order_up_to_S),
            ]
        )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Stock Policy Product</title>
  <style>{build_css()}</style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>Stock Policy Product</h1>
      <p>Pipeline escalavel para forecast, politica de estoque, backtest e analise por SKU x loja.</p>
      <p class="note">Horizonte: {escape(run_metadata['horizon'])} | Forecast mode: {escape(run_metadata['forecast_mode'])} | z escolhido: {escape(run_metadata['z_value'])} | review_days: {escape(run_metadata['review_days'])}</p>
    </div>

    {cards}

    <div class="section">
      <h3>Como usar este produto</h3>
      <p>Comece pela tabela de SKU x loja abaixo. Cada linha abre uma pagina propria com forecast, simulacao de estoque, pedidos emitidos e leitura rapida de risco.</p>
    </div>

    <div class="section">
      <h3>Busca de parametros globais</h3>
      <p class="note">A grade abaixo mostra as 10 melhores combinacoes de z e review_days na janela de validacao. O objetivo penaliza servico abaixo da meta e depois busca menos capital e menor custo de pedido.</p>
      {build_table(["z", "review_days", "Servico", "Capital medio", "Custo total", "Objetivo"], tuning_rows)}
    </div>

    <div class="section">
      <h3>Carteira por SKU x loja</h3>
      {build_table(["Produto", "ABC", "Servico simulado", "Servico real", "Capital medio", "Demanda Q4", "Perda simulada", "s", "S"], sku_rows)}
    </div>
  </div>
</body>
</html>"""

    (output_dir / "index.html").write_text(html, encoding="utf-8")


def write_report_bundle(
    output_dir: Path,
    overall_metrics: dict[str, float],
    tuning_results: pd.DataFrame,
    sku_metrics: pd.DataFrame,
    simulation: pd.DataFrame,
    run_metadata: dict[str, str],
) -> None:
    output_dir = ensure_dir(output_dir)
    products_dir = ensure_dir(output_dir / "products")

    write_index_report(
        output_dir=output_dir,
        overall_metrics=overall_metrics,
        tuning_results=tuning_results,
        sku_metrics=sku_metrics,
        run_metadata=run_metadata,
    )

    for _, metrics_row in sku_metrics.iterrows():
        daily = simulation[
            (simulation["location"] == metrics_row["location"])
            & (simulation["product"] == metrics_row["product"])
        ].sort_values("date")
        write_product_report(products_dir, metrics_row=metrics_row, daily=daily)
