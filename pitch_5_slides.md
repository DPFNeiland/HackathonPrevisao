# Pitch de 5 Slides

## Slide 1 - Problema e objetivo

- Desafio: decidir quanto pedir e quando pedir para cada `SKU x loja` no periodo de `2024-10-01` a `2024-12-31`.
- Objetivo de negocio: reduzir ruptura sem deixar capital demais parado em estoque.
- Restricoes principais: sem olhar o futuro, respeitando lead time de `3 dias` para a loja `841` e `9 dias` para a loja `1314`.

## Slide 2 - Estrategia usada

- Forecast diario por `SKU x loja` usando apenas historico ate `2024-09-30`.
- Ajustes de demanda para:
- dias de ruptura, tratando venda observada como demanda censurada.
- campanhas promocionais, usando `4_campanhas.csv` e `5_produtos_locais_campanhas.csv`.
- Politica de reposicao `(s, S)`:
- `s` = ponto de reposicao para acionar pedido.
- `S` = nivel alvo de estoque apos o pedido chegar.

## Slide 3 - Resultado de negocio

- Nivel de servico: `[preencher com KPI final]`.
- Capital medio em estoque: `R$ [preencher]`.
- Custo total de reposicao: `R$ [preencher]`.
- Comparacao com baseline da casa:
- economia de capital: `R$ [preencher]`.
- reducao de ruptura: `[preencher] p.p.`.
- mensagem principal: nossa politica melhora disponibilidade com menor ou controlado capital parado.

## Slide 4 - Exemplo de 1 SKU bem narrado

- Escolher 1 SKU relevante, de preferencia o `18064`, porque ele concentra muito volume.
- Mostrar grafico com:
- estoque real no Q4/2024.
- estoque simulado com a politica proposta.
- linha de pedidos emitidos e recebidos.
- Narrativa sugerida:
- onde houve risco de ruptura.
- como o ponto `s` antecipou a reposicao.
- como o `S` evitou excesso de estoque.

## Slide 5 - Conclusao e proximos passos

- O que funcionou: politica simples, explicavel e calibrada por backtest.
- O que melhorariamos com mais tempo:
- simulacao completa fornecedor -> CD -> loja.
- calibracao mais fina por SKU ABC.
- modelos mais fortes para promocao e sazonalidade.
- Fechamento: o melhor resultado veio de combinar forecast defensavel com politica operacional consistente.
