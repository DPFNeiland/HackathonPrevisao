# Previsão de Demanda e Política de Estoque

**Área:** Supply Chain / Analytics

**Tipo:** Hackathon de previsão e otimização de estoque

**Status:** Concluído

## Objetivo

Construir uma política de reposição por combinação de `produto x loja`, capaz de:

- prever a demanda diária;
- definir o ponto de reposição (`s`);
- definir o estoque-alvo (`S`);
- respeitar lead time e lote mínimo de compra;
- reduzir rupturas e capital parado em estoque;
- comparar a política simulada com o estoque historicamente observado.

Quando a posição de estoque fica menor ou igual a `s`, o simulador emite um pedido suficiente para elevar a posição até `S`, arredondando a quantidade para o lote mínimo do produto.

## Visão Geral da Solução

O pipeline executa as seguintes etapas:

1. Carrega cadastros de produtos e lojas, campanhas, vendas e saldos de estoque.
2. Monta um painel diário para cada combinação de produto e loja.
3. Corrige demanda potencialmente censurada em dias de ruptura.
4. Estima o efeito de campanhas promocionais sobre a demanda.
5. Gera previsões diárias estáticas e móveis.
6. Valida combinações de fator de segurança (`z`) e dias de revisão.
7. Classifica os itens em classes ABC de acordo com o volume de demanda.
8. Calcula a política de estoque `(s, S)`.
9. Simula pedidos, recebimentos, estoque disponível e vendas perdidas.
10. Exporta métricas, arquivos CSV e um painel HTML por SKU e loja.

O forecast combina três componentes históricos:

- média dos últimos 28 dias, com peso de 45%;
- média dos últimos 8 dias equivalentes da semana, com peso de 35%;
- média de uma janela próxima ao mesmo período do ano anterior, com peso de 20%.

Em dias promocionais, a previsão recebe o ajuste de uplift calculado a partir do histórico.

## Estrutura do Repositório

```text
HackathonPrevisao/
  data/
    1_hierarquia.csv
    2_produtos_locais.csv
    3_locais.csv
    4_campanhas.csv
    5_produtos_locais_campanhas.csv
    6_fornecedores.csv
    7_saldo.csv
    8_inventario_venda.csv
  stock_policy_product/
    __init__.py
    engine.py
    reporting.py
  stock_policy_product_output/
    products/
    index.html
    policy.csv
    policy_enriched.csv
    daily_forecast_static.csv
    daily_forecast_rolling.csv
    simulation_daily.csv
    sku_metrics.csv
    tuning_search.csv
    local_tuning_search.csv
    local_overrides.csv
    overall_metrics.json
    best_validation_params.json
    run_metadata.json
  tests/
    test_comprehensive.py
    test_chaos.py
  run_stock_policy_product.py
  simulator.ipynb
  policy.csv
  LICENSE
  README.md
```

## Dados de Entrada

Os dados devem estar na pasta `data/` ou diretamente na raiz do projeto. Os CSVs usam `;` como separador.

Arquivos consumidos pelo pipeline:

- `2_produtos_locais.csv`: produtos por loja, preços, fornecedor, lote mínimo e custo de pedido;
- `3_locais.csv`: cadastro das lojas e lead time;
- `4_campanhas.csv`: período e tipo das campanhas;
- `5_produtos_locais_campanhas.csv`: vínculo entre campanhas, produtos e lojas;
- `7_saldo.csv`: posição histórica de estoque;
- `8_inventario_venda.csv`: movimentações usadas para obter as vendas.

Os arquivos `1_hierarquia.csv` e `6_fornecedores.csv` fazem parte do conjunto fornecido, mas não são lidos pela versão atual do pipeline.

> A pasta `data/` está ignorada pelo Git. Para reproduzir o projeto em outro ambiente, copie os oito arquivos para essa pasta mantendo os nomes e schemas originais.

## Configuração do Ambiente

O projeto requer Python 3.10 ou superior e utiliza `pandas`, `numpy` e `pytest`. A execução foi conferida com Python 3.12.

No Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pandas numpy pytest
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas numpy pytest
```

## Como Executar

Na raiz do projeto, execute:

```bash
python run_stock_policy_product.py
```

O comando localiza automaticamente a pasta `data/` e grava os resultados em `stock_policy_product_output/`.

### Parâmetros opcionais

```bash
python run_stock_policy_product.py \
  --base-dir . \
  --output-dir stock_policy_product_output \
  --service-level-target 0.92 \
  --forecast-mode-validation static
```

- `--base-dir`: raiz que contém os CSVs ou a pasta `data/`;
- `--output-dir`: pasta de destino dos artefatos;
- `--service-level-target`: nível mínimo de serviço considerado no tuning;
- `--forecast-mode-validation`: aceita `static` ou `rolling`. O modo `static` é o recomendado para evitar o uso de observações futuras durante a validação.

As janelas usadas atualmente estão definidas no script:

- validação: julho a setembro de 2024, com treino até 30/06/2024;
- teste final: outubro a dezembro de 2024, com treino até 30/09/2024.

## Como Abrir o Painel

Após a execução, abra [`stock_policy_product_output/index.html`](stock_policy_product_output/index.html) no navegador.

O painel apresenta:

- nível de serviço simulado e histórico;
- capital médio em estoque;
- quantidade e custo dos pedidos;
- ranking das combinações testadas;
- métricas por produto e loja;
- páginas individuais com demanda, forecast, estoque e pedidos simulados.

## Principais Artefatos

### Política final

- `stock_policy_product_output/policy.csv`: entrega enxuta com `product`, `location`, `reorder_point_s` e `order_up_to_S`;
- `stock_policy_product_output/policy_enriched.csv`: política completa, incluindo classe ABC, lead time, preços e parâmetros;
- `policy.csv`: cópia da política final disponível na raiz do projeto.

### Previsões e simulação

- `daily_forecast_static.csv`: previsão calculada apenas com dados disponíveis até o fim do treino;
- `daily_forecast_rolling.csv`: previsão diagnóstica atualizada ao longo do horizonte;
- `simulation_daily.csv`: estoque, pedidos, recebimentos, atendimento e perdas por dia;
- `sku_metrics.csv`: indicadores consolidados por produto e loja.

### Tuning e auditoria

- `tuning_search.csv`: busca global de `z` e dias de revisão;
- `local_tuning_search.csv`: busca local por SKU e loja;
- `local_overrides.csv`: parâmetros locais candidatos;
- `best_validation_params.json`: melhor combinação encontrada na validação;
- `overall_metrics.json`: métricas consolidadas do teste final;
- `run_metadata.json`: configuração usada na execução.

## Resultados Atuais

Os artefatos presentes no repositório registram os seguintes resultados para o quarto trimestre de 2024:

| Métrica | Política simulada | Histórico observado |
|---|---:|---:|
| Nível de serviço | 99,85% | 99,14% |
| Capital médio por SKU/dia | R$ 143,71 | R$ 163,27 |
| Diferença de capital | -R$ 19,57 | — |
| Pedidos emitidos | 113 | — |
| Custo total de pedidos | R$ 2.674,42 | — |
| Unidades de venda perdidas | 12 | — |

Na validação, a melhor configuração global foi:

- `z = 0,84`;
- `review_days = 7`;
- meta mínima de nível de serviço de 92%.

Na política final, o fator de segurança varia por classe: `A = 1,28`, `B = 0,84` e `C = 0,00`. Os limites acumulados da classificação ABC são 70% para A e 88% para B.

Os valores acima refletem os arquivos gerados atualmente e podem mudar quando os dados ou parâmetros forem alterados.

## Como Interpretar a Política `(s, S)`

Exemplo:

```text
product = 18064
location = 841
reorder_point_s = 9
order_up_to_S = 23
```

Para esse produto na loja `841`, quando a posição de estoque chegar a 9 unidades ou menos, deve ser emitido um pedido que leve a posição até 23 unidades. A quantidade final é ajustada ao lote mínimo de compra.

## Testes

Para executar toda a suíte:

```bash
python -m pytest tests -q
```

Também é possível executar os grupos separadamente:

```bash
python -m pytest tests/test_comprehensive.py -v
python -m pytest tests/test_chaos.py -v
```

Os testes cobrem cálculos de lote, forecast, classificação ABC, política `(s, S)`, lead time, estoque em trânsito, métricas, integração e cenários extremos.

## Regras Importantes

- Apenas movimentações com `type = SALE` são tratadas como vendas.
- O pipeline espera que quantidades e valores de venda estejam negativos no arquivo de movimentações e converte esses sinais para demanda positiva.
- Os nomes `LOJA 841` e `LOJA 1314` são convertidos para os códigos `841` e `1314`.
- A simulação final usa o forecast estático; o forecast móvel é exportado para análise.
- O nível de serviço mede a proporção de dias sem ruptura.
- O fill rate mede a proporção da demanda efetivamente atendida.

## Limitações Conhecidas

- As datas de validação e teste estão fixas no código para 2024.
- O forecast é uma combinação estatística de médias históricas, não um modelo de machine learning treinado.
- Variáveis externas, como clima, feriados e eventos locais, não são consideradas explicitamente.
- A classificação ABC final e a regra de zerar itens com demanda muito baixa consultam a demanda observada no próprio trimestre de teste. Portanto, os resultados atuais devem ser interpretados como análise retrospectiva; para uso preditivo em produção, essas regras precisam ser calculadas somente com dados anteriores ao horizonte.
- Os arquivos da pasta de saída são substituídos em uma nova execução feita no mesmo destino.
- O projeto ainda não possui API, agendamento automático, monitoramento ou arquivo de dependências com versões fixadas.

## Próximos Passos

1. Parametrizar as janelas temporais pela linha de comando.
2. Remover o uso da demanda observada do horizonte nas regras finais de ABC e baixa demanda.
3. Comparar o forecast atual com modelos como LightGBM, XGBoost e séries temporais hierárquicas.
4. Incluir calendário, feriados, clima e outros sinais externos.
5. Adicionar um arquivo de dependências versionado e uma rotina de integração contínua.
6. Publicar o painel e criar uma API para consulta da política por SKU e loja.

## Materiais Complementares

- [`simulator.ipynb`](simulator.ipynb): notebook de apoio para exploração e simulação;
- [apresentação do projeto no Canva](https://www.canva.com/design/DAHKgqxWLmY/CVNnVVRHbfio3tMMeRxciA/edit).

## Licença

Este projeto está disponível sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE).
