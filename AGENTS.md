# AGENTS — Hackathon Previsão de Estoque (Q4/2024)

## Contexto do Projeto

Hackathon de otimização de inventário para rede farmacêutica. Propor política de reposição (s, S) para 29 SKUs da categoria **Gripe e Resfriado** em 2 lojas, validada via simulação dia a dia no **Q4/2024**.

- **Loja 841** (Ceres, GO): lead time = 3 dias, ~174 unidades vendidas no Q4
- **Loja 1314** (Corumbá, MS): lead time = 9 dias, ~1051 unidades vendidas no Q4
- **CD 2 GO** (Hidrolândia, GO): centro de distribuição único
- SKU **18064 (NEOSORO)** domina o volume
- ~30% das vendas do Q4 ocorreram em dias promocionais
- `minimum_delivery_batch` = 1 para lojas (não é restrição)

## Dados

8 CSVs em `data/`, relacionados por `product`, `location`, `campaign`:

| Arquivo | Conteúdo |
|---------|----------|
| `1_hierarquia.csv` | Categoria (1 linha, confirma escopo) |
| `2_produtos_locais.csv` | Cadastro SKU x local (preço compra/venda, custo pedido) |
| `3_locais.csv` | Lojas, CD, lead times |
| `4_campanhas.csv` | Períodos promocionais |
| `5_produtos_locais_campanhas.csv` | Vínculo SKU-loja-campanha |
| `6_fornecedores.csv` | Dados de fornecedor (lead time, ciclo, mínimo) |
| `7_saldo.csv` | Snapshots de estoque diário |
| `8_inventario_venda.csv` | Movimentações (SALE=demanda, DELIVERY, etc.) |

**Atenção:** Vendas (`SALE`) têm `quantity` negativo — inverter sinal para forecast.

## Períodos

- **Treino:** 02/01/2023 a 30/09/2024
- **Avaliação (backtest):** 01/10/2024 a 31/12/2024

## Requisitos Obrigatórios

- Política por SKU-loja com `reorder_point_s` e `order_up_to_S`
- Simulador dia a dia respeitando lead time e posição de estoque (físico + trânsito)
- **Nível de serviço ≥ 92%**
- KPIs: nível de serviço, capital médio em estoque, custo total de reposição
- Sem vazamento temporal no backtest
- Estado inicial: último saldo em `7_saldo.csv` antes de 01/10/2024

## Recomendação Técnica

- Política **(s, S)**: `s = ceil(mu * L + z * sigma * sqrt(L))`, `S = ceil(s + mu * review_cover_days)`
- Loja 841: L=3; Loja 1314: L=9
- Forecast simples (média móvel / dia da semana) + uplift promocional + correção de censura
- Calibrar `z` e `review_cover_days` via grid search no simulador

## Convenções

- `cost_of_ordering` é incorrido por pedido, não por unidade
- Estoque valorado a `purchase_price`
- Ruptura: demanda > saldo → estoque = 0, diferença = venda perdida
- Pedido no dia `d` chega em `d + lead_time`
- Decidir pedido ao amanhecer (com posição de estoque), consumir demanda, fechar saldo

## Entregas

1. `policy.csv` com colunas: `product;location;reorder_point_s;order_up_to_S`
2. Simulador funcional
3. Pitch (slides)

## Observações

- Dicionário de dados (`Estrutura dos Dados.xlsx`) não encontrado no repositório
- Baseline da casa não definido — comparar com política real/nula
- Alguns SKUs têm `introduction_date` recente (2024) — séries curtas
- Para documentação completa e detalhada, consulte `MASTER_BRIEFING.md`
