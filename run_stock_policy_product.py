from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from stock_policy_product.engine import (
    Horizon,
    apply_empirical_demand_floors,
    build_forecast,
    build_overall_metrics,
    build_policy,
    build_sku_metrics,
    build_summary_from_forecast,
    prepare_enriched_panel,
    resolve_data_dir,
    search_policy_parameters,
    simulate_policy,
    tune_local_sku_overrides,
)
from stock_policy_product.reporting import write_report_bundle


def to_serializable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def write_json(path: Path, payload: dict) -> None:
    serializable = {key: to_serializable(value) for key, value in payload.items()}
    path.write_text(json.dumps(serializable, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the stock policy product end-to-end on the CSV inputs."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Workspace root that contains the data folder or CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "stock_policy_product_output",
        help="Folder where the product outputs will be written.",
    )
    parser.add_argument(
        "--service-level-target",
        type=float,
        default=0.92,
        help="Minimum target service level used during parameter tuning.",
    )
    parser.add_argument(
        "--forecast-mode-validation",
        choices=["static", "rolling"],
        default="static",
        help="Forecast mode used while tuning global z and review_days (recommended: static to avoid temporal leakage).",
    )
    args = parser.parse_args()

    base_dir = args.base_dir
    data_dir = resolve_data_dir(base_dir)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

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

    validation_panel = prepare_enriched_panel(
        data_dir=data_dir,
        horizon_end=validation_horizon.end,
        train_end=validation_horizon.train_end,
    )
    best_params, tuning_results = search_policy_parameters(
        panel=validation_panel,
        horizon=validation_horizon,
        forecast_mode=args.forecast_mode_validation,
        service_level_target=args.service_level_target,
        z_grid=[0.84, 1.04, 1.28, 1.65, 2.05],
        cover_days_grid=[3, 5, 7, 10, 14],
        warmup_days=45,
    )

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
        validation_forecast=validation_forecast_static,
        global_z_value=float(best_params["z_value"]),
        global_review_days=int(best_params["review_days"]),
        service_level_target=0.97,
        z_grid=[0.84, 1.04, 1.28, 1.65, 2.05, 2.33, 2.58],
        cover_days_grid=[5, 7, 10, 14],
        warmup_days=45,
        apply_only_if_changed=True,
    )

    final_panel = prepare_enriched_panel(
        data_dir=data_dir,
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
    final_policy_export = final_policy[
        ["product", "location", "reorder_point_s", "order_up_to_S"]
    ].copy()

    simulation = simulate_policy(
        panel=final_panel,
        forecast=final_forecast_static,
        policy=final_policy,
        horizon=final_horizon,
        warmup_days=45,
    )
    sku_metrics = build_sku_metrics(simulation, policy=final_policy)
    overall_metrics = build_overall_metrics(simulation)

    final_forecast_static.to_csv(output_dir / "daily_forecast_static.csv", index=False)
    final_forecast_rolling.to_csv(output_dir / "daily_forecast_rolling.csv", index=False)
    final_policy.to_csv(output_dir / "policy_enriched.csv", index=False)
    final_policy_export.to_csv(output_dir / "policy.csv", index=False)
    simulation.to_csv(output_dir / "simulation_daily.csv", index=False)
    sku_metrics.to_csv(output_dir / "sku_metrics.csv", index=False)
    tuning_results.to_csv(output_dir / "tuning_search.csv", index=False)
    local_overrides.to_csv(output_dir / "local_overrides.csv", index=False)
    local_search.to_csv(output_dir / "local_tuning_search.csv", index=False)

    metadata = {
        "base_dir": str(base_dir),
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "horizon": final_horizon.name,
        "validation_horizon": validation_horizon.name,
        "forecast_mode": "static_forecast_all_phases",
        "validation_forecast_mode": args.forecast_mode_validation,
        "service_level_target": args.service_level_target,
        "local_service_level_target": 0.97,
        "z_value": best_params["z_value"],
        "review_days": best_params["review_days"],
        "local_override_count": int(len(local_overrides)),
        "empirical_floor_reorder_quantile": 0.75,
        "empirical_floor_order_up_to_quantile": 0.90,
        "seasonal_reference_start": str(final_horizon.start - pd.DateOffset(years=1)),
        "seasonal_reference_end": str(final_horizon.end - pd.DateOffset(years=1)),
    }
    write_json(output_dir / "run_metadata.json", metadata)
    write_json(output_dir / "overall_metrics.json", overall_metrics)
    write_json(output_dir / "best_validation_params.json", best_params)

    write_report_bundle(
        output_dir=output_dir,
        overall_metrics=overall_metrics,
        tuning_results=tuning_results,
        sku_metrics=sku_metrics,
        simulation=simulation,
        run_metadata={
            "horizon": final_horizon.name,
            "forecast_mode": "static_all_phases",
            "z_value": f"{float(best_params['z_value']):.2f}",
            "review_days": str(int(best_params["review_days"])),
        },
    )

    print(f"output_dir={output_dir}")
    print(f"policy_path={output_dir / 'policy.csv'}")
    print(f"index_report={output_dir / 'index.html'}")
    print(f"sku_metrics_path={output_dir / 'sku_metrics.csv'}")


if __name__ == "__main__":
    main()
