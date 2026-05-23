# MASTER BRIEFING — Hackathon Previsão de Estoque (Q4/2024)

> **Data de consolidação:** 23/05/2026  
> **Fontes consolidadas:** `generate_project_guide.py` (fonte do `guia_projeto_estoque_q4_2024.docx`), 8 datasets CSV, `.gitattributes`, `LICENSE`  
> **Arquivos não lidos por limitação técnica (sem bibliotecas Python instaladas):** `PROBLEM_STATEMENT.md.docx`, `Hackathon_CDN_desafio.pdf`  
> **Escopo confirmado:** 29 SKUs | 2 lojas | Categoria "Gripe e Resfriado"

---

## 1. Visão Geral do Hackathon

### Objetivo Principal
Propor e validar uma **política de reposição de estoque** para medicamentos da categoria **Gripe e Resfriado** em **2 lojas**, durante o **Q4/2024 (1º out 2024 a 31 dez 2024)**, que otimize o equilíbrio entre:

- **Nível de serviço** (≥ 92%)
- **Capital médio em estoque**
- **Custo operacional de reposição**

### Problema a Ser Resolvido
As lojas enfrentam um trade-off clássico de gestão de inventário: manter estoque suficiente para atender a demanda sem ruptura, sem imobilizar capital excessivo em produtos parados. O desafio é ainda maior devido a:

- Lead times diferentes entre lojas (3 vs 9 dias)
- Sazonalidade e promoções na categoria
- Demanda censurada (ruptura esconde demanda real)
- Múltiplos SKUs com perfis de giro distintos

### Contexto de Negócio
- **Segmento:** Farmácia / Varejo farmacêutico
- **Categoria:** Medicamentos para gripe e resfriado (código hierárquico: `1.102.011.00.00.00.00.00`)
- **Operação:** CD 2 (Centro de Distribuição em Hidrolândia, GO) abastece 2 lojas
- **Fornecedores:** Múltiplos, com ciclos e lead times variados

### Motivação do Desafio
Reduzir ruptura (falta de produtos na prateleira) sem elevar excessivamente o capital de giro imobilizado em estoque, melhorando a disponibilidade para o cliente final e a eficiência financeira da operação.

---

## 2. Resumo Executivo

### Síntese do Desafio
O hackathon propõe um problema de **otimização de inventário multi-SKU, multi-loja** com dados reais de uma rede farmacêutica. Os participantes devem:

1. **Analisar** dados históricos (jan/2023 a set/2024)
2. **Prever** demanda por SKU-loja para o Q4/2024
3. **Definir** uma política de reposição (recomendado: política (s, S))
4. **Simular** dia a dia o comportamento do estoque no Q4/2024
5. **Comparar** KPIs contra baseline da casa

### Resultados Esperados
- Arquivo `policy.csv` com parâmetros `reorder_point_s` e `order_up_to_S` por SKU-loja
- Simulador funcional que valide a política com backtest temporal
- Pitch apresentando raciocínio de negócio e resultados

### Dores a Resolver
| Dor | Descrição |
|-----|-----------|
| **Ruptura** | Estoque insuficiente → perda de vendas e insatisfação |
| **Excesso de capital** | Estoque alto → recursos imobilizados sem retorno |
| **Custo operacional** | Pedidos frequentes → custo de processamento elevado |
| **Complexidade de decisão** | Múltiplos SKUs e loças com perfis diferentes |

---

## 3. Requisitos Oficiais

### 3.1 Requisitos Funcionais (Obrigatórios)

| ID | Descrição |
|----|-----------|
| RF01 | Gerar política de reposição por par **SKU x loja** |
| RF02 | Simular execução dia a dia da política entre **01/10/2024 e 31/12/2024** |
| RF03 | Calcular **nível de serviço** (≥ 92%), **capital médio em estoque** e **custo total de reposição** |
| RF04 | Respeitar **lead time** entre CD e loja ao emitir pedidos |
| RF05 | Tratar **demanda censurada**: quando estoque = 0, venda observada < demanda real |
| RF06 | Usar **posição de estoque** (estoque físico + pedidos em trânsito) para decisão de pedido |
| RF07 | Iniciar simulação com último saldo disponível antes de 01/10/2024 (snapshot de 30/09/2024) |

### 3.2 Entregáveis Obrigatórios

| # | Entregável | Descrição |
|---|------------|-----------|
| 1 | `policy.csv` | Uma linha por SKU-loja com colunas: `product`, `location`, `reorder_point_s`, `order_up_to_S` |
| 2 | **Simulador** | Código que roda dia a dia entre 01/10/2024 e 31/12/2024, respeitando lead time e calculando KPIs |
| 3 | **Pitch** | Slides com raciocínio de negócio, pipeline analítico, backtest e recomendações |

### 3.3 Restrições Técnicas

| Restrição | Detalhamento |
|-----------|--------------|
| **Lead time** | Loja 841 = 3 dias; Loja 1314 = 9 dias (conforme `3_locais.csv`) |
| **Período de avaliação** | Q4/2024: 01/10/2024 a 31/12/2024 (92 dias) |
| **Período de treino** | 02/01/2023 a 30/09/2024 (~21 meses) |
| **Unidade de análise** | Par SKU x loja (cada par tem seu próprio parâmetro de reposição) |
| **Capital em estoque** | Valorado ao preço de compra (`purchase_price`) |
| **Custo de pedido** | Usar `cost_of_ordering` do cadastro (`2_produtos_locais.csv`) |
| **Tipo de demanda principal** | Movimentos com `type = SALE` em `8_inventario_venda.csv` (valores negativos = saída) |
| **Dia do pedido** | Pedido emitido no dia `d` só chega em `d + lead_time` |
| **Ruptura** | Quando demanda > saldo, estoque vai a zero e diferença = venda perdida |

### 3.4 Tecnologias — Sem Restrição Explícita
- **Permitidas:** Qualquer linguagem/ferramenta (Python, R, SQL, Excel, etc.)
- **Sugeridas pelo guia:** Python com pandas, numpy para manipulação; Prophet, ARIMA, LightGBM para forecast
- **Proibidas:** Nenhuma explicitamente mencionada

### 3.5 Critérios de Avaliação

| Critério | Peso (implícito) | Detalhe |
|----------|-------------------|---------|
| **Nível de serviço** | Alto | Deve ficar **acima de 92%** |
| **Capital médio em estoque** | Alto | Menor capital = melhor (mantendo serviço) |
| **Custo total de reposição** | Médio | Soma dos custos de pedido no período |
| **Consistência metodológica** | Alto | Backtest sem vazamento temporal, convenções claras |
| **Qualidade do pitch** | Médio | Clareza do raciocínio de negócio, visualizações |

> **Nota:** O score final é dado pelo backtest com nível de serviço ≥ 92%. O melhor forecast nem sempre gera a melhor política — a calibração deve ser feita diretamente sobre o simulador.

---

## 4. Contexto de Negócio

### Domínio do Problema
**Gestão de inventário no varejo farmacêutico.** O CD 2 (Centro-Oeste) recebe produtos de diversos fornecedores e abastece duas lojas. A categoria "Gripe e Resfriado" tem alta sazonalidade (picos no inverno) e é sensível a campanhas promocionais.

### Stakeholders

| Stakeholder | Interesse |
|-------------|-----------|
| **Cliente final** | Disponibilidade do produto na prateleira |
| **Gerente de loja** | Evitar ruptura sem excesso de estoque |
| **Analista de suprimentos** | Eficiência operacional e custo de pedido |
| **Financeiro** | Redução de capital de giro imobilizado |
| **Marketing/Comercial** | Campanhas promocionais e uplift de demanda |

### Impacto Esperado
- Redução de ruptura → aumento de receita
- Redução de capital imobilizado → melhora de fluxo de caixa
- Política automatizada → redução de esforço manual de reposição

### Indicadores Importantes

| Indicador | Fórmula / Definição |
|-----------|---------------------|
| **Nível de Serviço (NS)** | Dias sem ruptura / Total de dias do período |
| **Capital Médio em Estoque** | Média do valor em estoque (balance * purchase_price) no período |
| **Custo Total de Reposição** | Soma de cost_of_ordering para cada pedido emitido |
| **Giro de Estoque** | Demanda total / Estoque médio |
| **Cobertura (dias)** | Estoque disponível / Demanda média diária |

---

## 5. Análise dos Dados Disponíveis

### 5.1 Estrutura Geral

A base contém **8 arquivos CSV** relacionáveis por chaves em comum. Abaixo, o diagrama de relações:

```
1_hierarquia (categoria)
       │
2_produtos_locais (SKU x local x fornecedor) ─── 6_fornecedores (SKU x fornecedor x CD)
       │
       ├── 3_locais (lojas, CD, lead time)
       │
       ├── 4_campanhas (períodos promocionais)
       │    └── 5_produtos_locais_campanhas (vínculo SKU-loja-campanha)
       │
       ├── 7_saldo (estoque diário SKU x loja)
       │
       └── 8_inventario_venda (movimentação dia a dia)
```

### 5.2 Dataset por Dataset

#### `1_hierarquia.csv`

| Campo | Valor |
|-------|-------|
| **Finalidade** | Validar que o escopo é a categoria "Gripe e Resfriado" |
| **Conteúdo** | 1 linha, código hierárquico completo |
| **Problemas** | Apenas 1 linha — serve exclusivamente para confirmação de escopo |
| **Aplicação** | Filtro de categorias |

#### `2_produtos_locais.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `product` | int (PK) | Código do SKU |
| `location` | string | "CD 2", "LOJA 841", "LOJA 1314" |
| `supplier` | int | Código do fornecedor |
| `product_name` | string | Nome comercial do produto |
| `product_group` | string | Código da categoria |
| `inventory_unit` | string | "unds" (unidades) |
| `purchase_price` | float | Preço de compra (custo) |
| `sales_price` | float | Preço de venda (pode estar vazio para CD) |
| `minimum_delivery_batch` | int | Lote mínimo de entrega |
| `product_locations.introduction_date` | date | Data de introdução do produto no local |
| `cost_of_ordering` | float | Custo de emitir um pedido |

**Observações críticas:**
- **29 SKUs únicos** na categoria
- **58 linhas no total** (CD + lojas)
- `minimum_delivery_batch` = **1 para todas as linhas de loja** → lote mínimo não é restrição relevante
- `cost_of_ordering` varia muito (R$ 2,57 a R$ 249,25)
- SKU 18064 (NEOSORO) tem o menor `cost_of_ordering` (R$ 2,57) e `purchase_price` (R$ 9,19) — produto de alto giro
- Alguns produtos têm `introduction_date` recente (ex: SKU 76834 introduzido em 2024-02-08) — cuidado com séries históricas curtas

#### `3_locais.csv`

| Campo | Valor |
|-------|-------|
| **Finalidade** | Lead time e dados geográficos das lojas |
| **Lojas** | 841 (Ceres, GO — lead time 3 dias) e 1314 (Corumbá, MS — lead time 9 dias) |
| **CD** | CD 2 GO (Hidrolândia, GO) |
| **Problemas** | Apenas 2 lojas no escopo; lead time do CD não preenchido |
| **Aplicação** | Parâmetro crucial de lead time para política (s, S) |

#### `4_campanhas.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `start_date` | date | Início da campanha |
| `end_date` | date | Fim da campanha |
| `name` | string | Nome descritivo |
| `campaign` | int (PK) | Código da campanha |
| `type` | string | "PAGUE E LEVE" ou "REBAIXA" |

**Observações:**
- 93 campanhas no total (2023-2024)
- Tipos: "PAGUE E LEVE" (predominante) e "REBAIXA"
- Nomes como "YELLOW FRIDAY", "MAIS É MENOS", "INVERNO AMARELO", promoções de fabricantes (CIMED, NEOSORO, etc.)
- Há campanhas no Q4/2024: Yellow Friday (nov), "Mais é Menos" (out-dez), "L4P3 NEOSORO" (set-out)
- **Problema de qualidade:** Alguns `start_date` têm tabulação/tabs (`\t`) no início

#### `5_produtos_locais_campanhas.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `campaign` | int | FK → `4_campanhas.campaign` |
| `product` | int | FK → `2_produtos_locais.product` |
| `location` | int | FK → `3_locais.location` |

**Observações:**
- 311 linhas vinculando SKU x loja x campanha
- SKUs mais promovidos: 57814, 57816, 57817, 57818 (Oseltamivir / Tamiflu genéricos) e 18064 (NEOSORO)
- Loja 1314 tem mais vínculos promocionais que loja 841

#### `6_fornecedores.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `supplier` | int | Código do fornecedor |
| `name` | string | Nome do fornecedor |
| `product` | int | FK → `2_produtos_locais.product` |
| `lead_time` | int | Lead time fornecedor → CD (dias) |
| `ordering_days` | string | Dias permitidos para pedido |
| `delivery_days` | string | Dias de entrega |
| `order_cycle` | string | "EVERY_WEEK", "EVERY_2_WEEKS", "EVERY_4_WEEKS" |
| `minimum_order_value` | float | Valor mínimo do pedido |
| `minimum_order_quantity` | int | Quantidade mínima do pedido |
| `location` | string | "CD 2" |

**Observações:**
- 30 linhas (alguns SKUs compartilham fornecedor)
- Lead times fornecedor→CD variam de 5 a 38 dias
- Ciclos de pedido: semanal, quinzenal, mensal
- **Uso:** Modelagem avançada do elo fornecedor-CD (não obrigatório, mas pode render bônus)

#### `7_saldo.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date` | date | Data do snapshot |
| `location` | int | FK → local |
| `product` | int | FK → produto |
| `balance` | int | Quantidade em estoque |
| `value` | float | Valor do estoque (balance * purchase_price) |

**Observações:**
- ~1800+ linhas
- Snapshot **não é diário** para todos os SKUs — há gaps temporais
- Últimos registros: ago/2024 para loja 841, jul-ago/2024 para loja 1314
- **Uso crítico:** Estado inicial da simulação (último snapshot antes de 01/10/2024)

#### `8_inventario_venda.csv`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date` | date | Data do movimento |
| `location` | int | FK → local |
| `product` | int | FK → produto |
| `type` | string | Tipo: `SALE`, `DELIVERY`, `TRANSFER`, `ADJUSTMENT`, `INVENTORY_CHECK`, `SPOILAGE` |
| `quantity` | int | Quantidade (negativo = saída, positivo = entrada) |
| `value` | float | Valor financeiro |
| `partner_code` | string | "CLIENTE", "CD 2", "CD 1", "OUTROS" |

**Observações críticas:**
- `SALE` com `quantity` negativo = demanda real (inverter sinal)
- Datas de 2023-01-01 a 2024-12-31
- **Problema de qualidade:** Não há marcação explícita de ruptura — inferir por estoque zerado
- **Aplicação principal:** Série de demanda para forecast e simulação

### 5.3 Problemas de Qualidade Identificados

| Problema | Impacto | Mitigação |
|----------|---------|-----------|
| **Dicionário ausente** (`Estrutura dos Dados.xlsx`) | Risco de interpretação incorreta de campos | Usar convenções do guia do projeto |
| **Snapshot de saldo irregular** | Estado inicial pode não corresponder a 30/09/2024 | Usar snapshot mais próximo antes de 01/10/2024 |
| **Tabulações em `4_campanhas.csv`** | Erro de parsing | Sanitizar ao carregar |
| **Vendas negativas sem sinal explícito de ruptura** | Demanda censurada não identificável diretamente | Heurística: substituir demanda em dias de ruptura por média recente |
| **Preços de venda ausentes para CD** | Margem não calculável no CD | Ignorar margem no CD, focar varejo |
| **Datas de introdução recentes** | Alguns SKUs com séries curtas (< 1 ano) | Tratar separadamente no forecast |

---

## 6. Oportunidades Técnicas

### 6.1 Abordagens de Solução

A documentação do guia sugere 3 níveis de solução:

| Abordagem | Complexidade | Vantagem | Risco |
|-----------|-------------|----------|-------|
| **MVP defensável** | Baixa | Rápida, explicável | Pode errar promoção e censura |
| **Intermediária (recomendada)** | Média | Explicável + boa performance no score | Requer cuidado com simulador |
| **Avançada** | Alta | Captura nuances | Overfitting, bug, falta de tempo |

### 6.2 Ideias Concretas para Implementação

**Forecast:**
- Começar simples: média móvel ponderada, média por dia da semana com janela recente
- Considerar componente de dia da semana
- Ajuste promocional (uplift) quando SKU estiver em campanha
- Correção de demanda censurada: substituir demanda em dias de ruptura pelo max(venda observada, média de dias equivalentes sem ruptura)
- Evoluir para Prophet, ARIMA ou LightGBM se houver tempo

**Política de Reposição:**
- Política recomendada: **(s, S)** — ponto de pedido e nível-alvo
- Parametrização:
  - `mu_LT = mu * L` (demanda média durante lead time)
  - `safety_stock = z * sigma * sqrt(L)`
  - `s = ceil(mu_LT + safety_stock)`
  - `S = ceil(s + mu * review_cover_days)`
- Loja 841: L = 3; Loja 1314: L = 9
- Calibrar `z` e `review_cover_days` por backtest

**Simulador:**
- Convenção operacional: receber pedidos ao amanhecer → decidir novo pedido → consumir demanda → fechar saldo
- Usar **posição de estoque** (estoque físico + trânsito), não saldo físico
- Tratar ruptura: estoque não pode ficar negativo; diferença = venda perdida
- Calcular KPIs ao final

**Otimização:**
- Grid search de `z` (fator de segurança) e `review_cover_days`
- Segmentação ABC para dedicar mais atenção a itens de maior giro (SKU 18064 = classe A)
- Políticas separadas por loja (obrigatório, devido a lead times e volumes diferentes)

### 6.3 Oportunidades de Visualização
- Gráfico de estoque real vs. simulado (antes/depois)
- Curva ABC por SKU (valor vs. volume)
- Heatmap de ruptura por SKU-loja
- Evolução diária do nível de serviço
- Trade-off: nível de serviço vs. capital médio (fronteira eficiente)

---

## 7. Possíveis Riscos e Dificuldades

### 7.1 Limitações Técnicas

| Risco | Descrição | Severidade |
|-------|-----------|------------|
| **Demanda censurada** | Ruptura histórica esconde demanda real, viesando forecast | Alta |
| **Dados esparsos** | Alguns SKUs têm muitas vendas zero (demanda intermitente) | Média |
| **Séries curtas** | SKUs introduzidos em 2024 têm < 1 ano de histórico | Alta |
| **Lead time longo (loja 1314)** | 9 dias de lead time amplifica erro de forecast | Alta |
| **Snapshots de saldo irregulares** | Estado inicial impreciso compromete simulação | Média |

### 7.2 Lacunas de Informação

| Lacuna | Impacto |
|--------|---------|
| **Dicionário de dados oficial não encontrado** (`Estrutura dos Dados.xlsx`) | Incerteza sobre campos e convenções |
| **Baseline da casa não definido** | Sem comparação explícita para o backtest |
| **Critérios de desempate do score** | Não se sabe o peso relativo exato de cada KPI |
| **Regra de negócio para pedidos mínimos** | `minimum_delivery_batch` = 1, mas `minimum_order_value` e `minimum_order_quantity` em `6_fornecedores.csv` podem se aplicar ao CD |

### 7.3 Riscos de Implementação

| Risco | Descrição |
|-------|-----------|
| **Vazamento temporal** | Usar informação futura no forecast ou simulação (ex: demanda real para calibrar pedido) |
| **Overfitting** | Modelo muito complexo que funciona nos dados de treino mas falha no backtest |
| **Inconsistência de convenção** | Mudar regra de pedido ou KPI no meio do desenvolvimento |
| **Simulador com bug** | Erro na contagem de lead time, ruptura ou capital médio invalida todo o trabalho |

---

## 8. Sugestão de Arquitetura Inicial

### 8.1 Estrutura Recomendada do Sistema

```
hackathon-previsao/
├── data/                          # Dados brutos (CSVs)
├── notebooks/                     # Exploração e prototipagem
│   ├── 01_eda.ipynb
│   ├── 02_forecast.ipynb
│   └── 03_policy_optimization.ipynb
├── src/
│   ├── data/
│   │   ├── loader.py              # Carregamento e sanitização dos CSVs
│   │   └── preprocessor.py        # Merge, feature engineering, painel diário
│   ├── forecast/
│   │   ├── models.py              # Modelos de previsão (baseline, Prophet, etc.)
│   │   └── demand_utils.py        # Correção de censura, uplift promocional
│   ├── policy/
│   │   ├── ss_policy.py           # Implementação da política (s, S)
│   │   └── optimizer.py           # Grid search / calibração
│   ├── simulator/
│   │   ├── engine.py              # Simulador dia a dia
│   │   └── kpi.py                 # Cálculo de KPIs
│   └── output/
│       └── policy_generator.py    # Gera policy.csv
├── MASTER_BRIEFING.md
└── requirements.txt
```

### 8.2 Divisão Backend / Frontend

- **Backend (data science):** Pipeline completo em Python (pandas, numpy, scikit-learn, statsmodels)
- **Frontend:** Não explicitamente requerido — pitch pode usar slides ou dashboard simples (Streamlit)
- **API:** Não requerida para o hackathon (simulação offline)

### 8.3 Pipeline de Dados

```
CSVs → Loader → Data Preprocessor → Painel Diário SKU-Loja
                                         │
                                         ├──→ Forecast Model → Demanda Prevista
                                         │
                                         ├──→ Policy (s, S) → reorder_point, order_up_to
                                         │
                                         └──→ Simulator → KPIs (NS, Capital, Custo)
```

### 8.4 Banco de Dados Sugerido
- Para o escopo do hackathon: **não é necessário banco de dados** — dados cabem em memória (CSVs < 10 MB)
- Se houver pipeline mais robusta: SQLite ou DuckDB para consultas

### 8.5 Serviços Externos Úteis
- `python-docx` para gerar relatório final (se desejado)
- `matplotlib`/`plotly`/`seaborn` para visualizações

---

## 9. Roadmap de Desenvolvimento

### 9.1 MVP (Funcionalidades Essenciais)

| Ordem | Funcionalidade | Descrição |
|-------|---------------|-----------|
| 1 | Painel diário SKU-loja | Merge de todos CSVs em grade diária (jan/2023 a dez/2024) |
| 2 | Simulador baseline | Simulador simples sem forecast (política fixa) para validar lógica |
| 3 | Política (s, S) ingênua | Média histórica como forecast, z fixo (ex: 1.65), política (s, S) |
| 4 | Cálculo de KPIs | Nível de serviço, capital médio, custo de reposição |
| 5 | `policy.csv` | Geração do arquivo de entrega |

### 9.2 Funcionalidades Prioritárias

| Ordem | Funcionalidade | Descrição |
|-------|---------------|-----------|
| 6 | Forecast por SKU-loja | Média móvel ou por dia da semana com janela recente |
| 7 | Uplift promocional | Ajuste de forecast para dias de campanha |
| 8 | Correção de censura | Substituição de demanda em dias de ruptura |
| 9 | Grid search de parâmetros | Calibração de `z` e `review_cover_days` no simulador |
| 10 | Segmentação ABC | Priorização de itens A na calibração |

### 9.3 Funcionalidades Opcionais

| Funcionalidade | Descrição |
|----------------|-----------|
| Modelo avançado de forecast | Prophet, ARIMA ou LightGBM |
| Simulação do elo fornecedor-CD | Modelagem completa da cadeia |
| Análise de trade-off | Fronteira eficiente serviço vs. capital |
| Dashboard visual | Streamlit com gráficos interativos |

### 9.4 Melhorias Futuras
- Modelagem probabilística de demanda completa
- Otimização multi-objetivo (NS, capital, custo)
- Diferenciação de tipos de movimento (devolução, ajuste, etc.)
- Simulação estocástica (Monte Carlo)
- Integração com sistema real de reposição

---

## 10. Contexto para Outros Modelos de IA

### 10.1 Resumo Altamente Contextualizado

Este projeto é um **desafio de otimização de inventário** para uma rede farmacêutica. O objetivo é definir **quanto e quando pedir** cada medicamento para cada loja, minimizando ruptura e capital imobilizado. O período de avaliação é o Q4/2024. Dados históricos de janeiro/2023 a setembro/2024 estão disponíveis em 8 CSVs.

### 10.2 Terminologias Importantes

| Termo | Definição |
|-------|-----------|
| **SKU** | Stock Keeping Unit — identificador único do produto |
| **Lead time (L)** | Dias entre emissão do pedido e recebimento |
| **Política (s, S)** | Ponto de pedido (s) e nível-alvo (S); quando estoque ≤ s, pede até S |
| **Posição de estoque** | Estoque físico + pedidos em trânsito |
| **Ruptura / Stockout** | Esto que = 0, demanda insatisfeita |
| **Demanda censurada** | Demanda observada < demanda real porque estoque zerou |
| **Nível de serviço** | % de dias sem ruptura (target ≥ 92%) |
| **Capital médio em estoque** | Valor financeiro médio do estoque no período |
| **Custo de reposição** | Soma dos `cost_of_ordering` por pedido |
| **Backtest** | Simulação da política no período de avaliação usando dados reais |
| **Uplift promocional** | Aumento esperado na demanda devido a campanhas |
| **CD** | Centro de Distribuição |

### 10.3 Decisões Técnicas Relevantes para Modelos de Código

1. **Separar política por loja** — a loja 1314 (L=9, maior volume) e loja 841 (L=3, menor volume) não podem compartilhar parâmetros
2. **Sinal das vendas** — em `8_inventario_venda.csv`, `SALE` tem `quantity` negativo; inverter para positivo no forecast
3. **Movimentos não-SALE** — `DELIVERY`, `TRANSFER`, `ADJUSTMENT`, `INVENTORY_CHECK`, `SPOILAGE` não entram no forecast de demanda, mas podem ser úteis no simulador realista
4. **Estado inicial** — usar o último snapshot de saldo em `7_saldo.csv` antes de 01/10/2024
5. **Convenção do simulador** — receber pedidos ao amanhecer → decidir (com base na posição de estoque) → consumir demanda → fechar
6. **Custo de pedido** — aplicar `cost_of_ordering` apenas quando um pedido é emitido (não por unidade)
7. **Valoração do estoque** — usar `purchase_price` do `2_produtos_locais.csv` (cada loja pode ter preços diferentes para o mesmo SKU)
8. **Lead times** — LOJA 841 = 3 dias (via `3_locais.csv`), LOJA 1314 = 9 dias. Fornecedor→CD pode ser usado para modelagem completa

### 10.4 Instruções Úteis para Modelos de Código

**Para modelos de Data Science / ML:**
- A demanda é o foco principal. Trate `SALE` como variável target.
- Considere sazonalidade semanal e efeitos promocionais como features.
- Demanda censurada: se estoque = 0 no snapshot do dia, a venda observada pode subestimar a demanda real.
- SKU 18064 (NEOSORO) é o mais vendido — deve ser prioridade na calibração.

**Para modelos de Backend:**
- Não há API ou banco de dados — tudo é processamento batch em Python.
- A saída principal é `policy.csv` (formato: `product;location;reorder_point_s;order_up_to_S`).

**Para modelos de Frontend / Apresentação:**
- O pitch deve focar em: (1) lógica de negócio, (2) pipeline dados→forecast→política→simulador, (3) um SKU representativo com antes/depois, (4) próximos passos honestos.

**Para modelos de Negócios:**
- O trade-off central: mais estoque → maior nível de serviço → mais capital imobilizado.
- O custo de ruptura (venda perdida + insatisfação) não está explicitamente modelado, mas é o motivador do desafio.
- Recomendação: defensável, separada por loja, respeitando lead time.

---

## 11. Perguntas em Aberto

### 11.1 Ambiguidades e Requisitos Indefinidos

| # | Pergunta | Impacto |
|---|----------|---------|
| 1 | Qual é o **baseline** (política atual) para comparação? Sem ele, não é possível calcular o "ganho" da nova política |
| 2 | O dicionário de dados (`Estrutura dos Dados.xlsx`) não foi encontrado. Existem convenções não documentadas nos CSVs? | Risco de interpretação incorreta |
| 3 | O score final é uma **combinação ponderada** dos KPIs? Qual o peso de cada um? | Sem saber, não é possível otimizar corretamente |
| 4 | O `minimum_delivery_batch` é 1, mas há `minimum_order_value` e `minimum_order_quantity` no fornecedor. Eles devem ser respeitados no pedido do CD ao fornecedor? | Impacta o custo de reposição |
| 5 | Os pedidos podem ser emitidos **todos os dias** ou apenas em dias úteis? | Impacta o timing da reposição |
| 6 | O `partner_code = "OUTROS"` em movimentos inclui o quê exatamente? Pode ser ignorado? | Risco de漏 r movimento relevante |
| 7 | O que fazer com SKUs com `introduction_date` recente (pouco histórico)? | Tratamento especial necessário |
| 8 | **Transferências** entre lojas ou CD→loja ocorrem? O campo `TRANSFER` em `8_inventario_venda.csv` sugere que sim, mas não há documentação | Impacta o saldo real |

### 11.2 Pontos que Precisam ser Assumidos

| # | Assunção Necessária | Justificativa |
|---|---------------------|---------------|
| 1 | O baseline é a política real da loja no período | Sem alternativa documentada |
| 2 | O snapshot mais próximo de 30/09/2024 em `7_saldo.csv` representa o estado inicial | Única fonte disponível |
| 3 | Dias sem snapshot de saldo e sem movimento de venda têm demanda = 0 | Dado esparso |
| 4 | Movimentos `SPOILAGE` e `INVENTORY_CHECK` são perdas não planejadas e não devem ser previstas | Eventos exógenos |
| 5 | O custo de pedido (`cost_of_ordering`) é incorrido integralmente por pedido, independentemente do tamanho | Conforme guia |
| 6 | A loja pode pedir a qualquer momento (não há janela de pedido obrigatória) — a menos que se modele o elo fornecedor | Simplificação razoável |

### 11.3 Dúvidas que Impactam a Implementação

1. **Como determinar exatamente quais dias tiveram ruptura histórica?** O saldo é snapshot, não contínuo. Um dia pode começar com estoque e terminar sem.
2. **O forecast deve ser diário ou semanal?** A simulação é diária, mas o forecast pode ser agregado por semana.
3. **Até que nível de detalhe modelar o custo de pedido?** `cost_of_ordering` é fixo por pedido ou variável?
4. **O `partner_code` deve ser usado como filtro?** "CLIENTE" para vendas, "CD 2" para entregas, "CD 1" e "OUTROS" para eventos especiais?

---

## Apêndice A — Licença

MIT License © 2026 Neiland. O código-fonte e dados são fornecidos "as is", sem garantias.

## Apêndice B — Notas sobre Arquivos Não Lidos

Os arquivos `PROBLEM_STATEMENT.md.docx` e `Hackathon_CDN_desafio.pdf` **não puderam ser processados** devido à ausência de bibliotecas Python (`python-docx`, `PyPDF2`/`pdfplumber`) no ambiente de execução. O conteúdo aqui consolidado baseia-se integralmente em:

- `generate_project_guide.py` (código-fonte completo do `guia_projeto_estoque_q4_2024.docx`)
- Todos os 8 datasets CSV
- Arquivos auxiliares (`.gitattributes`, `LICENSE`)

**Recomendação:** Se `PROBLEM_STATEMENT.md.docx` e `Hackathon_CDN_desafio.pdf` contiverem instruções adicionais (ex: critérios de avaliação oficiais, regras de submissão, formatos de entrega), eles devem ser lidos com as ferramentas apropriadas e este documento deve ser atualizado.
