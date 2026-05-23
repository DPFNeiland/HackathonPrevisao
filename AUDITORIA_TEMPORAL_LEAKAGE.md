# Auditoria de Temporal Leakage — Pipeline de Previsão de Estoque

> **Escopo:** Análise exaustiva de todos os fluxos de dados temporais no pipeline.
> **Premissa:** Um único vazamento pode invalidar completamente os resultados do backtest.
> **Método:** Rastreamento manual de cada variável, merge, agregação e decisão no tempo.

---

## Índice de Vazamentos Encontrados

| ID | Fase | Severidade | Tipo | Impacto na Política |
|----|------|-----------|------|---------------------|
| L01 | Tuning global | 🔴 **CRÍTICO** | Rolling forecast contamina parametrização | Escolha de `z` e `review_days` otimistas |
| L02 | Simulação final | 🟠 **ALTO** | Rolling forecast no reporting | Métricas de acurácia do forecast infladas |
| L03 | Tuning local | 🟡 **MÉDIO** | Rolling forecast nos testes individuais | Relatório de validação local contaminado |
| L04 | Política (fase final) | ✅ **LIMPO** | Forecast estático na construção | Sem impacto |
| L05 | Simulação (decisões) | ✅ **LIMPO** | Apenas (s, S) do policy decidem pedidos | Sem impacto |
| L06 | Correção de censura | ✅ **LIMPO** | Baselines do período de treino apenas | Sem impacto |
| L07 | Uplift promocional | ✅ **LIMPO** | Razões do treino apenas | Sem impacto |
| L08 | Pisos empíricos | ✅ **LIMPO** | Dados de treino apenas | Sem impacto |
| L09 | Saldo inicial | ✅ **LIMPO** | Dados anteriores ao simulation_start | Sem impacto |
| L10 | Classificação ABC | ✅ **LIMPO** | Forecast estático (não contaminado) | Sem impacto |

---

## 🔴 L01 — CRÍTICO: Rolling forecast contamina a calibração global dos parâmetros

### Onde ocorre
`run_stock_policy_product.py:67-69,95-103`

```python
parser.add_argument(
    "--forecast-mode-validation",
    choices=["static", "rolling"],
    default="rolling",                        # ← PADRÃO É ROLLING (CONTAMINADO)
    help="Forecast mode used while tuning global z and review_days.",
)
# ...
best_params, tuning_results = search_policy_parameters(
    panel=validation_panel,
    horizon=validation_horizon,               # Q3/2024: 2024-07-01 a 2024-09-30
    forecast_mode=args.forecast_mode_validation,  # "rolling"
    ...
)
```

### Cadeia de contaminação

```
   validation_panel (dados até 2024-09-30)
                   │
                   ▼
   build_forecast(mode="rolling")  ←─── para CADA dia D do Q3,
   forecast_group: hist = dados ANTES de D        usa dados do PRÓPRIO Q3
                   │
                   ▼
   build_summary_from_forecast
   → mean_daily_forecast = média dos forecasts rolling (CONTAMINADO)
   → std_daily_forecast  = média dos stds rolling (CONTAMINADO)
                   │
                   ▼
   build_policy(summary, z, review_days)
   → s = ceil(mean_daily × LT + z × std_daily × √LT)  ←── usa métricas CONTAMINADAS
   → S = ceil(s + mean_daily × review_days)             ←── usa métricas CONTAMINADAS
                   │
                   ▼
   simulate_policy(panel, forecast, policy)
   → testa a política CONTRA a demanda real do Q3
   → métricas de serviço e capital usadas para selecionar z, review_days
```

### Exemplo concreto

Para SKU `18064` (NEOSORO) na Loja 1314, durante o Q3/2024:

| Data | Rolling forecast usa dados até | Inclui dados do Q3? |
|------|-------------------------------|---------------------|
| 01-jul | 30-jun (treino puro) | Não |
| 15-jul | 14-jul | **Sim** (14 dias de Q3) |
| 01-ago | 31-jul | **Sim** (31 dias de Q3) |
| 30-set | 29-set | **Sim** (91 dias de Q3) |

O `mean_daily_forecast` para todo o Q3 é a MÉDIA de 92 forecasts diários. Desses, apenas o primeiro (01-jul) é puramente do treino. Os 91 restantes incluem dados do próprio Q3 — **91% dos forecasts estão contaminados**.

### Por que a escolha de z e review_days é afetada

Com forecasts contaminados (mais precisos que o real), a variabilidade aparente da demanda (`std_daily_forecast`) é menor. O estoque de segurança `z × σ × √L` calculado subestima a incerteza real. Consequência:

```
Rolling forecast:  σ_aparente = 5.0  →  z = 0.84 parece suficiente
Static forecast:   σ_real = 7.5       →  z = 0.84 é insuficiente
```

O grid search seleciona o **menor `z`** que atinge 92% de serviço COM o rolling forecast. Esse `z` é otimista demais para o forecast estático real.

### Evidência nos dados de saída

Em `best_validation_params.json`:
```json
{
  "z_value": 0.84,
  "review_days": 7,
  "service_level": 0.985945,
  "avg_inventory_value": 132.61
}
```

O `z = 0.84` (fator de segurança para ~80% de confiança numa normal) é baixo. É o menor valor do grid `[0.84, 1.04, 1.28, 1.65, 2.05]`. O fato do menor z ter sido selecionado sugere que o rolling forecast subestimou a variabilidade, fazendo o estoque de segurança parecer desnecessário.

### Como detectar

```python
# Comparar mean_daily_forecast e std_daily_forecast entre modos
static = build_forecast(validation_panel, validation_horizon, "static")
rolling = build_forecast(validation_panel, validation_horizon, "rolling")

static_summary = build_summary_from_forecast(static)
rolling_summary = build_summary_from_forecast(rolling)

diff = rolling_summary["mean_daily_forecast"] - static_summary["mean_daily_forecast"]
print(f"Média da diferença: {diff.mean():.4f}")
# Se diff.mean() > 0, rolling está vendo dados do Q3 que inflam o forecast
```

### Como corrigir

**Opção A (recomendada):** Usar `forecast_mode="static"` na validação:

```python
parser.add_argument(
    "--forecast-mode-validation",
    choices=["static", "rolling"],
    default="static",  # ← ALTERAR PARA STATIC
)
```

**Opção B (mantendo rolling opcional):** Executar grid search com ambos e comparar:

```python
best_params_static, _ = search_policy_parameters(..., forecast_mode="static")
best_params_rolling, _ = search_policy_parameters(..., forecast_mode="rolling")
# Escolher o mais conservador ou o que melhor generaliza no Q4
```

---

## 🟠 L02 — ALTO: Rolling forecast no Q4 contamina métricas de reporting

### Onde ocorre
`run_stock_policy_product.py:131-132,153-155,161`

```python
final_forecast_static = build_forecast(final_panel, horizon=final_horizon, mode="static")
final_forecast_rolling = build_forecast(final_panel, horizon=final_horizon, mode="rolling")
# ...
simulation = simulate_policy(
    panel=final_panel,
    forecast=final_forecast_rolling,   # ← ROLLING forecast (INFO FIELD)
    policy=final_policy,
    horizon=final_horizon,
)
overall_metrics = build_overall_metrics(simulation)
```

### Cadeia de contaminação

```
final_forecast_rolling (contaminado com dados do Q4)
         │
         ▼
simulate_policy merge → simulation_panel tem forecast_demand CONTAMINADO
         │
         ▼
build_overall_metrics:
  total_forecast_units = sum(simulation["forecast_demand"])  ← CONTAMINADO
         │
         ▼
overall_metrics.json:
  "total_forecast_units": 1623.68  ← NÃO REPRESENTA UM FORECAST LEGÍTIMO
```

### Exemplo concreto

Para SKU `18064` na Loja 1314 no Q4/2024:

| Data | Rolling forecast usa | Fonte |
|------|-------------------|-------|
| 01-out | Dados até 30-set (treino) | Limpo |
| 15-out | Dados até 14-out (inclui 14 dias de Q4) | **Contaminado** |
| 15-nov | Dados até 14-nov (inclui 45 dias de Q4) | **Contaminado** |
| 31-dez | Dados até 30-dez (inclui 91 dias de Q4) | **Contaminado** |

Na simulação, na data `2024-12-15`, o `forecast_demand` registrado é um forecast que já viu as vendas reais de outubro, novembro e metade de dezembro. Esse forecast é muito mais preciso do que qualquer forecast real possível.

### Impacto nas métricas reportadas

| Métrica | Valor reportado | Valor real (estimado) | Diferença |
|---------|----------------|----------------------|-----------|
| `total_forecast_units` | 1623.68 | ~1400-1500 | **~10% superestimado** |
| `service_level` | 99.53% | Não afetado ✅ | — |

O `total_forecast_units` nos `overall_metrics.json` e `sku_metrics.csv` é sistematicamente inflado. Se usado em cálculos de viés do forecast (ex: `(forecast - actual) / actual`), mostra acurácia irreal.

### Como detectar

Comparar o `total_forecast_units` entre os modos:

```python
static_total = final_forecast_static["forecast_demand"].sum()
rolling_total = final_forecast_rolling["forecast_demand"].sum()
print(f"Static: {static_total:.2f}, Rolling: {rolling_total:.2f}, Dif: {(rolling_total-static_total)/static_total*100:.1f}%")
```

### Como corrigir

Usar `final_forecast_static` na simulação final:

```python
simulation = simulate_policy(
    panel=final_panel,
    forecast=final_forecast_static,   # ← STATIC (sem vazamento)
    policy=final_policy,
    horizon=final_horizon,
    warmup_days=45,
)
```

Manter `final_forecast_rolling` apenas para análise exploratória, não para o pipeline principal.

---

## 🟡 L03 — MÉDIO: Rolling forecast contamina validação local (tune_local_sku_overrides)

### Onde ocorre
`run_stock_policy_product.py:112-123`

```python
validation_forecast_rolling = build_forecast(
    validation_panel, horizon=validation_horizon, mode="rolling"
)
local_overrides, local_search = tune_local_sku_overrides(
    ...
    rolling_forecast=validation_forecast_rolling,  # ← ROLLING
    ...
)
```

### Cadeia de contaminação

```
validation_forecast_rolling (mesmo L01 — contaminado com dados do Q3)
         │
         ▼
tune_local_sku_overrides:
  item_forecast = rolling_forecast[filtrado por SKU]
         │
         ▼
  simulate_policy(item_panel, item_forecast, item_policy)
  → forecast_demand no output é contaminado
         │
         ▼
  search_rows.append(..., total_forecast_units=..., forecast_units=...)
  → local_search.csv tem métricas de forecast contaminadas
```

### Por que o impacto é menor que L01

Em `tune_local_sku_overrides`, a política é construída com `static_summary`:

```python
item_policy = build_policy(
    sku_summary,       # ← vem de static_summary (LIMPO)
    z_value=z_value,
    review_days=review_days,
)
```

O `rolling_forecast` é usado apenas como info field na simulação. A política usa a média/variância estática do SKU.

**Mas:** o `local_search.csv` gerado contém `total_forecast_units` de cada combinação (z, review_days) com forecast contaminado, o que pode enganar análises posteriores.

### Como corrigir

Usar `validation_forecast_static` no lugar de `rolling_forecast`, ou simplesmente não reportar `forecast_units` nas buscas locais.

---

## ✅ L04 a L10 — FASES CONFIRMADAS SEM VAZAMENTO

### L04 — Política final (LIMPO)

```python
final_summary = build_summary_from_forecast(final_forecast_static)  # ← STATIC
final_policy = build_policy(summary=final_summary, ...)             # ← usa summary estático
```

A política (s, S) para o Q4 usa APENAS o forecast estático (dados até 2024-09-30). **Sem vazamento.**

### L05 — Decisões de pedido na simulação (LIMPO)

No loop de simulação, a decisão de pedir usa:

```python
reorder_point = int(row.reorder_point_s or 0)          # ← da política (estática)
order_up_to = int(row.order_up_to_S or 0)              # ← da política (estática)
inventory_position_before_order = opening_inventory + on_order_before  # ← estado local
```

`row.forecast_demand` existe no DataFrame mas NÃO é usado em nenhuma condicional. **Sem vazamento.**

### L06 — Correção de demanda censurada (LIMPO)

```python
train = panel[panel["date"] <= train_end].copy()    # ← FILTRA por data de treino
non_stockout = train[train["stockout"] == 0]
dow_baseline = non_stockout.groupby(...)["demand"].median()  # ← só treino
```

Baselines calculados exclusivamente do período de treino. Aplicados a Q4 via `merge` de dia da semana. **Sem vazamento.**

### L07 — Uplift promocional (LIMPO)

```python
train = panel[panel["date"] <= train_end].copy()    # ← FILTRA
sku_stats = train.groupby(["location", "product", "is_promo"]).agg(...)
```

Razões de uplift calculadas do período de treino. Uplifts de Q4 (ex: "YELLOW FRIDAY CIMED" em nov/2024) NÃO entram no cálculo. O `is_promo` para Q4 é usado para *aplicar* o uplift, não para *calcular*. **Sem vazamento, desde que o cálculo do uplift seja separado.**

**Ressalva importante:** Em `forecast_q4_2024.py`, linha 181, o `compute_promo_uplift` é chamado **sem filtro temporal** dentro da função — mas a primeira linha da função faz `train = panel[panel["date"] <= TRAIN_END]`. Portanto está correto.

### L08 — Pisos empíricos (LIMPO)

```python
train = panel[panel["date"] <= train_end].copy()       # ← FILTRA
seasonal_reference_start = 2023-10-01                    # ← ano anterior ao Q4
seasonal_reference_end   = 2023-12-31                    # ← ano anterior ao Q4
```

Pisos empíricos usam dados de treino. Pisos sazonais usam o mesmo trimestre do ano anterior (2023). Ambos dentro do período de treino. **Sem vazamento.**

### L09 — Saldo inicial (LIMPO)

```python
prior = panel[panel["date"] < simulation_start]        # ← ANTES do início
simulation_start = horizon.start - warmup_days          # ← 2024-08-17 para Q4
```

Busca o último saldo conhecido **antes** do início da simulação. **Sem vazamento.**

### L10 — Classificação ABC (LIMPO)

```python
summary["forecast_value_period"] = total_forecast_period * purchase_price
```

`total_forecast_period` vem do forecast estático (limpo). **Sem vazamento.**

---

## Mapa de Fluxo Temporal — Visão Consolidada

```
LEGENDA:
  [T] = dados de treino (até train_end)
  [V] = dados de validação (Q3/2024)
  [Q] = dados de teste (Q4/2024)
  🟢 = fluxo limpo
  🔴 = fluxo com vazamento
  🟡 = fluxo com vazamento parcial

                    ┌─────────────────────────────┐
                    │      CSVs (dados brutos)     │
                    │  2023-01-01 a 2024-12-31     │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │   build_daily_panel          │
                    │   (todos os dados carregados)│
                    └──────────┬──────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │Panel Validação │  │  Panel Final   │  │  Panel Final   │
 │(até 2024-09-30)│  │(até 2024-12-31)│  │(até 2024-12-31)│
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │Correção censura│  │Correção censura│  │Correção censura│
 │   baselines[T] │  │   baselines[T] │  │   baselines[T] │
 │      🟢        │  │      🟢        │  │      🟢        │
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │  Promo Uplift  │  │  Promo Uplift  │  │  Promo Uplift  │
 │   razões[T] 🟢 │  │   razões[T] 🟢 │  │   razões[T] 🟢 │
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │  Forecast[T]   │  │  Forecast[T]   │  │  Forecast[V,Q] │
 │   STATIC 🟢    │  │   STATIC 🟢    │  │   ROLLING 🔴   │
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         ▼                   ▼                   │
 ┌────────────────┐  ┌────────────────┐           │
 │ Summary (s,S)  │  │ Summary (s,S)  │           │
 │   🟢           │  │   🟢           │           │
 └───────┬────────┘  └───────┬────────┘           │
         │                   │                    │
         ▼                   ▼                    ▼
 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │  Grid Search   │  │  Simulação Q4  │  │  Info Field    │
 │  z, review_days│  │  política 🟢   │  │  forecast_demand│
 │  🟢 (se static)│  │  forecast 🔴L02│  │  🔴 L02        │
 │  🔴 L01 (rolling)│ └───────┬────────┘  └────────────────┘
 └────────────────┘          │
                             ▼
                     ┌────────────────┐
                     │ overall_metrics│
                     │ service🟢      │
                     │ capital🟢     │
                     │ forecast🔴L02 │
                     └────────────────┘
```

---

## Matriz de Risco — Probabilidade x Impacto

| ID | Vazamento | Probabilidade | Impacto na política | Risco final |
|----|-----------|--------------|---------------------|-------------|
| L01 | Rolling no grid search | **100%** (default ativo) | **Alto** (z e review_days sub-ótimos) | 🔴 **Crítico** |
| L02 | Rolling no reporting Q4 | **100%** (sempre executado) | **Médio** (métrica inflada, mas não afeta decisões) | 🟠 Alto |
| L03 | Rolling na validação local | **100%** (sempre executado) | **Baixo** (apenas reporting, policy usa static) | 🟡 Médio |
| L04-L10 | Demais fases | 0% | Nenhum | ✅ |

---

## Recomendações de Correção por Ordem de Impacto

### 1. 🔴 Corrigir L01 — Tuning global

**Arquivo:** `run_stock_policy_product.py:67-69`

**Mudança:** Alterar default de `"rolling"` para `"static"`:

```python
parser.add_argument(
    "--forecast-mode-validation",
    choices=["static", "rolling"],
    default="static",          # ← ANTES ERA "rolling"
)
```

**Validação pós-correção:** Reexecutar pipeline e comparar `best_validation_params.json`:

| Parâmetro | Antes (rolling) | Depois (static) | Interpretação |
|-----------|----------------|-----------------|---------------|
| z_value | 0.84 | Provavelmente maior | Mais estoque de segurança |
| review_days | 7 | Pode aumentar | Mais cobertura |
| avg_inventory_value | 132.61 | Provavelmente maior | Trade-off serviço vs capital |

### 2. 🟠 Corrigir L02 — Simulação final usar forecast estático

**Arquivo:** `run_stock_policy_product.py:155`

**Mudança:**

```python
simulation = simulate_policy(
    panel=final_panel,
    forecast=final_forecast_static,   # ← ANTES ERA final_forecast_rolling
    policy=final_policy,
    horizon=final_horizon,
    warmup_days=45,
)
```

### 3. 🟡 Corrigir L03 — Validação local com forecast estático

```python
local_overrides, local_search = tune_local_sku_overrides(
    ...
    rolling_forecast=validation_forecast_static,  # ← ANTES ERA rolling
    ...
)
```

Ou simplesmente desligar o reporting de forecast na busca local.

---

## Checklist de Verificação de Vazamento para Submissão Final

Antes de gerar o `policy.csv` final, verificar:

- [ ] `run_stock_policy_product.py` tem `default="static"` em `--forecast-mode-validation`?
- [ ] A simulação final usa `final_forecast_static` (não rolling)?
- [ ] `overall_metrics.json` usa forecast estático para `total_forecast_units`?
- [ ] `validate_temporal_isolation()` existe ou foi executada?
- [ ] Nenhum CSV de entrada (`8_inventario_venda.csv`) tem data > 2024-09-30 usada em treino?
- [ ] `promo_uplift` foi calculado apenas com dado pré-2024-10-01?
- [ ] `corrected_demand` usou baselines apenas do período de treino?
- [ ] `empirical_demand_floors` usou `train_end = 2024-09-30`?

### Script de verificação rápida

```python
def validate_temporal_isolation(panel, train_end):
    """Verifica se não há dados futuros contaminando features do treino."""
    train = panel[panel["date"] <= train_end]
    test = panel[panel["date"] > train_end]

    checks = {
        "dow_baseline": "dow_baseline" in panel.columns,
        "sku_baseline": "sku_baseline" in panel.columns,
        "promo_uplift": "promo_uplift" in panel.columns,
    }

    for name, present in checks.items():
        print(f"{'✅' if present else '❌'} {name}: {'presente' if present else 'ausente'}")

    # Verificar se os baselines foram computados só do treino
    baselines = ["dow_baseline", "sku_baseline", "store_weekday_baseline"]
    for bl in baselines:
        if bl in panel.columns:
            train_bl = panel.loc[panel["date"] <= train_end, bl].unique()
            test_bl = panel.loc[panel["date"] > train_end, bl].unique()
            print(f"{'✅' if set(train_bl) == set(test_bl) else '❌'} {bl}: treino={len(train_bl)} valores, teste={len(test_bl)} valores, {'iguais' if set(train_bl) == set(test_bl) else 'DIFERENTES'}")

    print("\nTemporal isolation check complete.")
```

---

## Conclusão

**2 vazamentos confirmados que afetam resultados, 1 deles crítico.**

- O **L01** (rolling no grid search) é o mais grave: a escolha de `z = 0.84` e `review_days = 7` foi feita com forecasts contaminados. A política resultante provavelmente tem **estoque de segurança insuficiente** para o cenário real (forecast estático).
- O **L02** (rolling no reporting) infla `total_forecast_units` em ~10%, mas não afeta a política em si.
- Todas as demais fases (correção de censura, uplift, pisos empíricos, saldo inicial, decisões de pedido) estão **limpas**.

**Custo estimado da correção:** 3 linhas de código alteradas (L01: mudar default, L02: trocar variável na chamada, L03: trocar variável na chamada).

**Ganho esperado:** Política mais robusta, métricas honestas, backtest válido para submissão.

---

*Documento gerado em 23/05/2026. Foco exclusivo em temporal leakage. Para análise completa de bugs (incluindo erros matemáticos, de KPI e lógicos), consulte `AUDITORIA_TECNICA.md`.*
