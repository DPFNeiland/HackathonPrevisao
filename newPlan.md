## Plano Final: 9h → 15h (6h) — 4 pessoas

### Papeis (mantidos e refinados)

| Pessoa | Papel | Foco |
|---|---|---|
| **A** | Engenheiro de dados | Pipeline, forecast, fórmulas de (s, S) |
| **B** | Arquiteto do simulador | Coração do backtest + cadeia fornecedor→CD |
| **C** | Otimizador / Validador | Grid search, calibração, validação temporal |
| **D** | Produto + Pitch | Dashboard animado + slides + narrativa |

---

### Cronograma (6h = 360 min)

#### 09:00 – 09:20 (20 min) — FUNDAÇÃO 👥 TODOS

| Tarefa | Tempo | Quem |
|---|---|---|
| Alinhar convenções do simulador: recebe pedidos no início do dia, consome demanda depois, posição = saldo + trânsito | 5min | TODOS |
| Setup do repositório, instalar dependências (pandas, matplotlib, plotly) | 10min | C |
| Dividir tarefas finais e acordar formato do policy.csv | 5min | D (documenta) |

---

#### 09:20 – 10:00 (40 min) — PIPELINE DE DADOS 🅰️ (lidera)

| Tarefa | Detalhe | Quem |
|---|---|---|
| Grade diária SKU × loja (jan/2023 a dez/2024) | Com todas as combinações possíveis | A |
| Merge 8_inventario_venda (type=SALE) | Demanda real | A |
| Merge 7_saldo | Estoque diário | A |
| Merge 4_campanhas + 5_produtos_locais_campanhas | Sinal promocional | A |
| Merge 2_produtos_locais | purchase_price, cost_of_ordering | A |
| Merge 3_locais | lead_time por loja | A |
| Merge 6_fornecedores | lead_time_fornecedor, order_cycle, minimum_order | A |
| Split treino (jan/2023 a 30-set-2024) / teste (01-out a 31-dez-2024) | Crítico: sem vazamento | A |

**A faz isso sozinho** — os outros 3 já começam a próxima etapa.

---

#### 09:20 – 10:20 (60 min) — SIMULADOR MVP 🅱️ + 🅲️ + 🅳️ (paralelo ao pipeline)

Enquanto A monta os dados, os outros 3 constroem o **simulador em Python puro** (sem pandas) com política dummy (s=10, S=50):

| Tarefa | Quem |
|---|---|
| **B:** Loop dia a dia do período de teste (01-out a 31-dez) | Arquitetura principal |
| **C:** Estrutura de estado (inventory, in_transit, orders_history) | Classes/dicionários |
| **D:** Lógica de decisão (se estoque ≤ s, pedir S - estoque + validação de lead time) | Regras de negócio |

```python
# Estrutura do simulador (produto final)
def simulate(policy, demand_real, initial_balance, lead_times, 
             purchase_price, cost_of_ordering, fornecedores):
    # policy: dict[(product, location)] -> (s, S)
    # demand_real: dict[(date, product, location)] -> qty
    # initial_balance: saldo em 30-set-2024
    
    inventory = {}      # estoque físico
    in_transit = {}     # pedidos pendentes
    supply_chain = {}   # estoque no CD (para bonus)
    orders = []         # historico de pedidos
    daily_balance = []  # para KPI de capital
    
    for day in test_days:
        # 1. Receber pedidos do CD que chegam hoje (respeitando lead_time)
        # 2. Receber pedidos do fornecedor no CD (bonus)
        # 3. Calcular posição de estoque = inventory + in_transit
        # 4. Decidir se pede para fornecedor (bonus) ou para CD
        # 5. Consumir demanda real (se demanda > estoque = ruptura)
        # 6. Registrar saldo final
        # 7. Se dia de revisão, pode pedir para CD
    
    # Calcular KPIs
    service_level = 1 - ruptura_days / total_days
    avg_capital = sum(daily_balance * purchase_price) / len(daily_balance)
    total_cost = len(orders) * cost_of_ordering
    score = 0.50 * service_level + 0.40 * (-avg_capital) + 0.10 * (-total_cost)
```

**Meta:** simulador rodando sem erro até 10:20. Não importa se os KPIs são ruins — o motor precisa funcionar.

---

#### 10:00 – 10:40 (40 min) — FORECAST HÍBRIDO 🅰️ (sozinho)

Com o pipeline pronto, A implementa o forecast igual ao do amigo (mas em Python puro):

```python
def forecast_hybrid(demanda_historico, dia_atual):
    # 45% média 28 dias
    ma_28 = demanda_historico[-28:].mean()
    
    # 35% média 8 dias equivalentes da semana
    mesmo_dia = [d for i, d in enumerate(demanda_historico) 
                 if i % 7 == dia_atual % 7]
    ma_8_weekday = mesmo_dia[-8:].mean()
    
    # 20% média mesmo trimestre do ano anterior
    ma_yoy = demanda_ano_anterior[trimestre_atual].mean()
    
    forecast = 0.45 * ma_28 + 0.35 * ma_8_weekday + 0.20 * ma_yoy
    
    # Se tem campanha no dia, aplicar uplift
    if em_campanha(dia_atual):
        forecast *= promo_uplift
    
    return forecast
```

**Correção de demanda censurada:** onde `balance == 0`, substituir demanda por `max(venda_real, ma_14_dias_recente)`.

---

#### 10:20 – 11:00 (40 min) — PAREDE: INTEGRAR TUDO 🅰️ + 🅱️ + 🅲️

| Quem | Tarefa |
|---|---|
| **A** | Entrega forecast para B |
| **B** | Conecta forecast no simulador: forecast → s = ceil(mu*LT + z*sigma*sqrt(LT)) → S = ceil(s + mu*review_days) |
| **C** | Valida integração: simulador recebe policy, roda, gera KPIs |
| **D** | Começa a fazer ***esboço do dashboard animado*** (pode trabalhar sozinho nessa) |

**Nesta etapa o simulador já deve estar rodando com uma política real** (mesmo que não calibrada).

---

#### 11:00 – 12:00 (60 min) — CALIBRAÇÃO + AJUSTE LOCAL 👥 TODOS

**Grid search global (C lidera, B valida):**

```
Testar combinações de:
  z: [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]
  review_days: [7, 14, 21]
  promo_uplift: [1.0, 1.1, 1.2, 1.3]
  
Total: 7 x 3 x 4 = 84 combinações
```

**Validação temporal (C):** treinar com jan/2023 a jun/2024, validar com jul-set/2024. Só testar no Q4 depois.

**Ajuste local (A + B):** depois do melhor global, refinar `z` individualmente por SKU-loja que ficar abaixo de 92%.

**ABC analysis (A):** classificar SKUs por giro. Itens A (top 20% do volume) → z maior. Itens C → z menor.

---

#### 12:00 – 12:30 (30 min) — ALMOÇO E DESCOMPRESSÃO 🍕

Todos param. Voltar com energia.

---

#### 12:30 – 13:30 (60 min) — INOVAÇÃO EM PARALELO

**Trilha 1 — Cadeia fornecedor → CD → loja 🅱️ + 🅲️ (diferencial #1)**

Usar `6_fornecedores.csv` para modelar:
- CD tem seu próprio estoque (vem do saldo inicial)
- CD faz pedido para fornecedor respeitando `order_cycle`, `minimum_order_value`
- Fornecedor entrega no CD em `lead_time_fornecedor` dias
- Só depois CD entrega para loja em `leadtime_dc_store`

```python
# Camada extra no simulador
if day % fornecedor['order_cycle_days'] == 0:
    if cd_estoque <= s_fornecedor:
        pedido = max(S_fornecedor - cd_estoque, fornecedor['minimum_order_quantity'])
        # pedido chega em day + fornecedor['lead_time']
```

**Trilha 2 — Dashboard animado 🅳️ + 🅰️ (diferencial #2)**

```python
# Com matplotlib.animation ou plotly
# Frame a frame do Q4:
# - Eixo X: tempo (dias)
# - Eixo Y: unidades
# - Linha azul: estoque
# - Região vermelha: ruptura
# - Marcadores verdes: pedido feito
# - Marcadores laranja: pedido chega
# - Score atualizando no canto
```

**O que mostrar na animação (1 SKU bem contado):**
1. Estoque REAL (do saldo.csv no Q4) — onde a loja realmente errou
2. Estoque SIMULADO (com sua política) — onde vocês evitaram ruptura
3. Comparação lado a lado ou sobreposta

---

#### 13:30 – 14:00 (30 min) — POLIMENTO E GERAÇÃO DE ARTEFATOS

| Tarefa | Quem |
|---|---|
| Gerar `policy.csv` final | C |
| Rodar simulador completo, exportar resultados | B |
| Capturar screenshots/prints do dashboard | D |
| Calcular economia anualizada (Impacto — 20%) | A |
| Verificar regras: sem vazamento, lead time respeitado | B + C |

**Cálculo de impacto anual:**
```python
# Economia por loja no Q4 × 4 trimestres × 6 lojas
economia_q4 = capital_baseline - capital_sua_politica
economia_anual = economia_q4 * 4 * (6/2)  # 6 lojas na rede, 2 no escopo
```

---

#### 14:00 – 14:40 (40 min) — PITCH 👥 TODOS

**Estrutura final dos 5 slides (5 min):**

| Slide | Conteúdo | Quem apresenta | Tempo |
|---|---|---|---|
| **1** | **O problema:** "Ruptura de 4-7% na rede = cliente sem remédio + receita perdida. Nosso trade-off: menos ruptura sem explodir capital." | D | 45s |
| **2** | **Nossa solução:** Fluxo visual → Pipeline → Forecast híbrido (45/35/20) → Política (s, S) → Simulador. Mostrar que tem base sólida. | A | 1min |
| **3** | **1 SKU bem contado:** ABRIR O DASHBOARD ANIMADO. Mostrar estoque real vs simulado. "Aqui em outubro a loja zerou. A gente teria pedido 5 dias antes." | D | 1min30 |
| **4** | **Resultados:** Tabela comparativa (Baseline vs Sua política). Curva de Pareto da calibração. Economia anual projetada. | B | 1min |
| **5** | **Diferenciais + próximos passos:** Cadeia completa fornecedor-CD-loja. O que fariam com mais tempo (modelo probabilístico). Chamada final. | C | 45s |

---

#### 14:40 – 15:00 (20 min) — ENSAIO E AJUSTES FINAIS

- Ensaio completo 2x
- Ajustar timing
- Subir tudo no repositório
- Checklist final de regras

---

### Resumo de diferenciais competitivos

| O amigo fez | Vocês fazem a mais | Impacto na nota |
|---|---|---|
| Forecast híbrido (45/35/20) | Mesmo forecast + **validação temporal rigorosa** | Execução (15%) |
| (s, S) com grid search | (s, S) com grid search + **ABC analysis** | Impacto (20%) |
| Apenas script Python | **Dashboard animado interativo** | Inovação (25%) |
| Só CD→loja | **Cadeia fornecedor→CD→loja completa** | Inovação (25%) |
| Pitch técnico | **Narrativa com 1 SKU + demonstração ao vivo** | Pitch (15%) |

**Recado final:** O modelo do seu amigo é bom, mas **não tem produto visual nem cadeia completa**. São exatamente esses dois itens que dão 25% de inovação. Se vocês executarem esse plano, chegam no pitch com:
- Simulador funcionando ✅
- Política calibrada ✅
- Dashboard animado ✅
- Cadeia completa ✅
- Um SKU narrado com demonstração ao vivo ✅

Isso **vence** um modelo 99% sem apresentação visual.