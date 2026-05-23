from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    r"C:\Users\rodrigo.neiland\OneDrive - ESPM\Documentos\3sem\Github\HackathonPrevisao\stock_policy_product_colab.ipynb"
)


def md_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().splitlines()],
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.strip().splitlines()],
    }


def main() -> None:
    cells = [
        md_cell(
            """
            # Stock Policy Product - Notebook para Jupyter e Colab

            Este notebook executa o produto de planejamento de politica de estoque fim a fim:

            - le os CSVs da pasta `data/`
            - monta a serie diaria por `SKU x loja`
            - corrige demanda censurada em dias de ruptura
            - ajusta forecast em dias de campanha
            - calibra parametros globais da politica `(s, S)`
            - aplica calibracao local por `SKU x loja`
            - sobe pisos empiricos e sazonais para itens intermitentes
            - gera `policy.csv`, simulacao diaria e metricas por produto
            - permite analisar um `SKU x loja` especifico com graficos

            ## Como usar no Colab

            1. Suba este notebook para o Colab.
            2. Garanta que a pasta `stock_policy_product/` e a pasta `data/` estejam no mesmo diretorio do notebook.
            3. Rode as celulas em ordem.

            Se voce estiver no Jupyter local dentro do repositorio, basta rodar normalmente.
            """
        ),
        md_cell(
            """
            ## Metodo usado para chegar ao nivel de servico

            O nivel de servico alto nao veio de um modelo complexo isolado. Veio de uma combinacao de regras bem calibradas:

            - forecast por `SKU x loja`, em vez de um modelo unico para tudo
            - mistura de tres sinais de demanda:
              - media dos ultimos 28 dias
              - media dos ultimos 8 dias equivalentes da semana
              - media do periodo equivalente do ano anterior
            - correcao de demanda censurada quando houve saldo zero
            - uplift promocional com base em campanhas historicas
            - calibracao global de `z` e `review_days` em uma janela de validacao anterior ao Q4
            - calibracao local por `SKU x loja` para dar uma segunda camada de ajuste
            - piso empirico baseado em janelas de lead time historicas
            - piso sazonal usando o mesmo trimestre do ano anterior
            - simulacao com aquecimento antes do periodo avaliado
            - estoque minimo de apresentacao para itens ativos

            Na ultima execucao validada no produto local, os melhores parametros globais ficaram em:

            - `z = 0.84`
            - `review_days = 7`

            E o resultado agregado no Q4/2024 ficou em torno de:

            - `service_level = 99.53%`
            - `capital medio simulado = R$ 171.42`
            - `capital medio historico = R$ 163.27`

            Observacao importante: essa versao prioriza robustez de servico. Se voce quiser um perfil mais enxuto em capital, pode aliviar o piso sazonal.
            """
        ),
        code_cell(
            """
            from pathlib import Path
            import json
            import pandas as pd
            import matplotlib.pyplot as plt

            from stock_policy_product.engine import (
                Horizon,
                apply_empirical_demand_floors,
                resolve_data_dir,
                prepare_enriched_panel,
                search_policy_parameters,
                build_forecast,
                build_summary_from_forecast,
                build_policy,
                simulate_policy,
                build_sku_metrics,
                build_overall_metrics,
                tune_local_sku_overrides,
            )
            from stock_policy_product.reporting import write_report_bundle

            pd.set_option("display.max_columns", 100)
            pd.set_option("display.width", 140)
            plt.style.use("seaborn-v0_8-whitegrid")
            """
        ),
        code_cell(
            """
            BASE_DIR = Path(".").resolve()
            DATA_DIR = resolve_data_dir(BASE_DIR)
            OUTPUT_DIR = BASE_DIR / "stock_policy_product_output_notebook"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            print("BASE_DIR:", BASE_DIR)
            print("DATA_DIR:", DATA_DIR)
            print("OUTPUT_DIR:", OUTPUT_DIR)
            """
        ),
        md_cell(
            """
            ## 1. Definir horizontes

            A calibracao global acontece em uma janela anterior ao teste final:

            - treino da validacao: ate `2024-06-30`
            - validacao: `2024-07-01` a `2024-09-30`
            - teste final: `2024-10-01` a `2024-12-31`
            """
        ),
        code_cell(
            """
            validation_horizon = Horizon(
                name="validation_q3_2024",
                train_end=pd.Timestamp("2024-06-30"),
                start=pd.Timestamp("2024-07-01"),
                end=pd.Timestamp("2024-09-30"),
            )

            final_horizon = Horizon(
                name="test_q4_2024",
                train_end=pd.Timestamp("2024-09-30"),
                start=pd.Timestamp("2024-10-01"),
                end=pd.Timestamp("2024-12-31"),
            )
            """
        ),
        md_cell(
            """
            ## 2. Calibrar parametros globais

            Aqui buscamos a melhor combinacao de `z` e `review_days`.
            O objetivo penaliza fortemente qualquer combinacao abaixo da meta de nivel de servico e, entre as que sobrevivem, privilegia menos capital medio e menor custo de pedido.
            """
        ),
        code_cell(
            """
            validation_panel = prepare_enriched_panel(
                data_dir=DATA_DIR,
                horizon_end=validation_horizon.end,
                train_end=validation_horizon.train_end,
            )

            best_params, tuning_results = search_policy_parameters(
                panel=validation_panel,
                horizon=validation_horizon,
                forecast_mode="rolling",
                service_level_target=0.92,
                z_grid=[0.84, 1.04, 1.28, 1.65, 2.05],
                cover_days_grid=[3, 5, 7, 10, 14],
                warmup_days=45,
            )

            best_params
            """
        ),
        code_cell(
            """
            tuning_results.head(10)
            """
        ),
        md_cell(
            """
            ## 3. Segunda camada de calibracao local

            Depois do ajuste global, rodamos uma busca por `SKU x loja` na janela de validacao.
            A meta local e mais rigida (`97%`) para proteger os itens mais frageis antes do Q4.
            """
        ),
        code_cell(
            """
            validation_forecast_static = build_forecast(
                validation_panel, horizon=validation_horizon, mode="static"
            )
            validation_forecast_rolling = build_forecast(
                validation_panel, horizon=validation_horizon, mode="rolling"
            )
            validation_summary = build_summary_from_forecast(validation_forecast_static)

            local_overrides, local_search = tune_local_sku_overrides(
                panel=validation_panel,
                horizon=validation_horizon,
                static_summary=validation_summary,
                rolling_forecast=validation_forecast_rolling,
                global_z_value=float(best_params["z_value"]),
                global_review_days=int(best_params["review_days"]),
                service_level_target=0.97,
                z_grid=[0.84, 1.04, 1.28, 1.65, 2.05, 2.33, 2.58],
                cover_days_grid=[5, 7, 10, 14],
                warmup_days=45,
                apply_only_if_changed=True,
            )

            local_overrides.head(15)
            """
        ),
        md_cell(
            """
            ## 4. Gerar forecast, politica e simulacao final para o Q4/2024

            Regra metodologica importante:

            - usamos `forecast static` para construir a politica fixa do Q4 sem vazamento temporal
            - usamos `forecast rolling` para leitura operacional dia a dia dentro da simulacao e dos relatorios
            - depois da politica estatistica, aplicamos pisos empiricos e sazonais
            """
        ),
        code_cell(
            """
            final_panel = prepare_enriched_panel(
                data_dir=DATA_DIR,
                horizon_end=final_horizon.end,
                train_end=final_horizon.train_end,
            )

            final_forecast_static = build_forecast(final_panel, horizon=final_horizon, mode="static")
            final_forecast_rolling = build_forecast(final_panel, horizon=final_horizon, mode="rolling")

            final_summary = build_summary_from_forecast(final_forecast_static)
            final_policy = build_policy(
                summary=final_summary,
                z_value=float(best_params["z_value"]),
                review_days=int(best_params["review_days"]),
                overrides=local_overrides,
            )

            final_policy = apply_empirical_demand_floors(
                final_policy,
                final_panel,
                train_end=final_horizon.train_end,
                reorder_quantile=0.75,
                order_up_to_quantile=0.90,
                seasonal_reference_start=final_horizon.start - pd.DateOffset(years=1),
                seasonal_reference_end=final_horizon.end - pd.DateOffset(years=1),
            )

            simulation = simulate_policy(
                panel=final_panel,
                forecast=final_forecast_rolling,
                policy=final_policy,
                horizon=final_horizon,
                warmup_days=45,
            )

            sku_metrics = build_sku_metrics(simulation, policy=final_policy)
            overall_metrics = build_overall_metrics(simulation)

            overall_metrics
            """
        ),
        code_cell(
            """
            pd.DataFrame([overall_metrics])
            """
        ),
        code_cell(
            """
            sku_metrics.sort_values(["abc_class", "forecast_units"], ascending=[True, False]).head(15)
            """
        ),
        md_cell(
            """
            ## 5. Exportar artefatos do produto

            Isso cria:

            - `policy.csv`
            - `simulation_daily.csv`
            - `sku_metrics.csv`
            - `index.html`
            - uma pagina HTML por `SKU x loja`
            """
        ),
        code_cell(
            """
            final_forecast_static.to_csv(OUTPUT_DIR / "daily_forecast_static.csv", index=False)
            final_forecast_rolling.to_csv(OUTPUT_DIR / "daily_forecast_rolling.csv", index=False)
            final_policy.to_csv(OUTPUT_DIR / "policy_enriched.csv", index=False)
            final_policy[["product", "location", "reorder_point_s", "order_up_to_S"]].to_csv(
                OUTPUT_DIR / "policy.csv", index=False
            )
            simulation.to_csv(OUTPUT_DIR / "simulation_daily.csv", index=False)
            sku_metrics.to_csv(OUTPUT_DIR / "sku_metrics.csv", index=False)
            tuning_results.to_csv(OUTPUT_DIR / "tuning_search.csv", index=False)
            local_overrides.to_csv(OUTPUT_DIR / "local_overrides.csv", index=False)
            local_search.to_csv(OUTPUT_DIR / "local_tuning_search.csv", index=False)

            (OUTPUT_DIR / "overall_metrics.json").write_text(
                json.dumps(overall_metrics, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )

            write_report_bundle(
                output_dir=OUTPUT_DIR,
                overall_metrics=overall_metrics,
                tuning_results=tuning_results,
                sku_metrics=sku_metrics,
                simulation=simulation,
                run_metadata={
                    "horizon": final_horizon.name,
                    "forecast_mode": "static policy + rolling report",
                    "z_value": f"{float(best_params['z_value']):.2f}",
                    "review_days": str(int(best_params["review_days"])),
                },
            )

            print("Arquivos exportados em:", OUTPUT_DIR)
            """
        ),
        md_cell(
            """
            ## 6. Analise de um produto especifico

            Troque os valores de `LOCATION` e `PRODUCT` para o item que voce quiser investigar.
            """
        ),
        code_cell(
            """
            LOCATION = "1314"
            PRODUCT = "18064"

            product_metrics = sku_metrics[
                (sku_metrics["location"].astype(str) == LOCATION)
                & (sku_metrics["product"].astype(str) == PRODUCT)
            ].copy()

            product_daily = simulation[
                (simulation["location"].astype(str) == LOCATION)
                & (simulation["product"].astype(str) == PRODUCT)
            ].copy().sort_values("date")

            product_metrics
            """
        ),
        code_cell(
            """
            fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)

            axes[0].plot(product_daily["date"], product_daily["actual_demand"], label="Demanda real", color="#1f4d78")
            axes[0].plot(product_daily["date"], product_daily["forecast_demand"], label="Forecast", color="#c9681f")
            axes[0].set_title("Demanda real vs forecast")
            axes[0].legend()

            axes[1].plot(product_daily["date"], product_daily["actual_balance"], label="Saldo real", color="#64748b")
            axes[1].plot(product_daily["date"], product_daily["ending_inventory"], label="Estoque simulado", color="#0b4b94")

            if not product_metrics.empty:
                s_value = float(product_metrics.iloc[0]["reorder_point_s"])
                S_value = float(product_metrics.iloc[0]["order_up_to_S"])
                axes[1].axhline(s_value, linestyle="--", color="#b45309", label="s")
                axes[1].axhline(S_value, linestyle="--", color="#047857", label="S")

            axes[1].set_title("Saldo real vs estoque simulado")
            axes[1].legend()

            plt.tight_layout()
            plt.show()
            """
        ),
        code_cell(
            """
            product_daily[product_daily["order_qty"] > 0][
                ["date", "order_qty", "arrival_date", "actual_demand", "ending_inventory", "ordering_cost"]
            ].head(20)
            """
        ),
        md_cell(
            """
            ## 7. Leitura executiva do metodo

            Se voce precisar explicar em apresentacao, resume assim:

            1. Construimos forecast por `SKU x loja`, porque as duas lojas tem volumes e lead times muito diferentes.
            2. Corrigimos os dias de ruptura para nao confundir falta de estoque com falta de demanda.
            3. Aplicamos ajuste para campanhas promocionais.
            4. Traduzimos forecast em politica `(s, S)` usando estoque de seguranca.
            5. Calibramos os parametros globais em um periodo anterior ao Q4.
            6. Aplicamos uma segunda camada de calibracao local por `SKU x loja`.
            7. Subimos pisos empiricos e sazonais para itens com comportamento intermitente ou mais forte no Q4.
            8. Validamos tudo em simulacao diaria com lead time real e sem olhar o futuro.
            """
        ),
        md_cell(
            """
            ## 8. Arquivos que voce vai usar no pitch

            Depois de rodar o notebook, os mais importantes costumam ser:

            - `stock_policy_product_output_notebook/policy.csv`
            - `stock_policy_product_output_notebook/sku_metrics.csv`
            - `stock_policy_product_output_notebook/index.html`
            - `stock_policy_product_output_notebook/local_overrides.csv`
            - `stock_policy_product_output_notebook/products/product_<loja>_<sku>.html`
            """
        ),
    ]

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2, ensure_ascii=False), encoding="utf-8")
    print(NOTEBOOK_PATH)


if __name__ == "__main__":
    main()
