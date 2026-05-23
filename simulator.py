from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from stock_policy_product.engine import (
    Horizon,
    build_forecast,
    build_overall_metrics,
    build_sku_metrics,
    build_summary_from_forecast,
    prepare_enriched_panel,
    resolve_data_dir,
    simulate_policy,
)


REQUIRED_POLICY_COLUMNS = {"product", "location", "reorder_point_s", "order_up_to_S"}


def read_policy_csv(policy_path: Path) -> pd.DataFrame:
    policy = pd.read_csv(policy_path)
    missing = REQUIRED_POLICY_COLUMNS - set(policy.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"policy.csv is missing required columns: {missing_str}")

    policy = policy.copy()
    policy["product"] = policy["product"].astype(str)
    policy["location"] = policy["location"].astype(str)
    policy["reorder_point_s"] = pd.to_numeric(policy["reorder_point_s"], errors="coerce").fillna(0)
    policy["order_up_to_S"] = pd.to_numeric(policy["order_up_to_S"], errors="coerce").fillna(0)
    return policy


def enrich_submission_policy(
    submission_policy: pd.DataFrame,
    reference_summary: pd.DataFrame,
) -> pd.DataFrame:
    enriched = submission_policy.merge(
        reference_summary[
            [
                "location",
                "location_name",
                "product",
                "product_name",
                "supplier",
                "abc_class",
                "lead_time_days",
                "purchase_price",
                "sales_price",
                "cost_of_ordering",
                "minimum_delivery_batch",
            ]
        ],
        on=["location", "product"],
        how="left",
    )

    missing_meta = enriched[
        enriched["lead_time_days"].isna() | enriched["purchase_price"].isna()
    ][["location", "product"]]
    if not missing_meta.empty:
        rows = ", ".join(
            f"({row.location}, {row.product})" for row in missing_meta.itertuples(index=False)
        )
        raise ValueError(
            "Could not enrich some policy rows with product/location metadata: "
            f"{rows}. Check if policy.csv uses the expected SKU/location pairs."
        )

    enriched["z_value"] = 0.0
    enriched["review_days"] = 0
    enriched["reorder_point_s"] = enriched["reorder_point_s"].round().astype(int)
    enriched["order_up_to_S"] = enriched["order_up_to_S"].round().astype(int)
    enriched["lead_time_days"] = enriched["lead_time_days"].round().astype(int)
    enriched["minimum_delivery_batch"] = (
        pd.to_numeric(enriched["minimum_delivery_batch"], errors="coerce").fillna(1).round().astype(int)
    )
    return enriched


def build_forecast_stub(panel: pd.DataFrame, horizon: Horizon) -> pd.DataFrame:
    stub = panel[(panel["date"] >= horizon.start) & (panel["date"] <= horizon.end)][
        ["date", "location", "product"]
    ].copy()
    stub["forecast_demand"] = 0.0
    stub["forecast_std"] = 0.0
    stub["promo_uplift"] = 1.0
    return stub


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest a submitted policy.csv on the Q4/2024 demand window."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Workspace root that contains the data folder.",
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        default=Path.cwd() / "policy.csv",
        help="Path to the submitted policy.csv file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "simulator_output",
        help="Directory where simulation outputs will be written.",
    )
    parser.add_argument(
        "--warmup-days",
        type=int,
        default=45,
        help="Number of days before 2024-10-01 used to warm up the simulation state.",
    )
    args = parser.parse_args()

    base_dir = args.base_dir
    data_dir = resolve_data_dir(base_dir)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    q4_horizon = Horizon(
        name="test_q4_2024",
        train_end=pd.Timestamp("2024-09-30"),
        start=pd.Timestamp("2024-10-01"),
        end=pd.Timestamp("2024-12-31"),
    )

    panel = prepare_enriched_panel(
        data_dir=data_dir,
        horizon_end=q4_horizon.end,
        train_end=q4_horizon.train_end,
    )

    reference_forecast = build_forecast(panel, horizon=q4_horizon, mode="static")
    reference_summary = build_summary_from_forecast(reference_forecast)

    submission_policy = read_policy_csv(args.policy_path)
    enriched_policy = enrich_submission_policy(submission_policy, reference_summary)
    forecast_stub = build_forecast_stub(panel, q4_horizon)

    simulation = simulate_policy(
        panel=panel,
        forecast=forecast_stub,
        policy=enriched_policy,
        horizon=q4_horizon,
        warmup_days=args.warmup_days,
    )
    sku_metrics = build_sku_metrics(simulation, policy=enriched_policy)
    overall_metrics = build_overall_metrics(simulation)

    simulation.to_csv(output_dir / "simulation_daily.csv", index=False)
    sku_metrics.to_csv(output_dir / "sku_metrics.csv", index=False)
    write_json(output_dir / "overall_metrics.json", overall_metrics)

    summary_rows = [
        {
            "metric": "service_level",
            "value": overall_metrics["service_level"],
        },
        {
            "metric": "actual_service_level",
            "value": overall_metrics["actual_service_level"],
        },
        {
            "metric": "avg_inventory_value",
            "value": overall_metrics["avg_inventory_value"],
        },
        {
            "metric": "actual_avg_inventory_value",
            "value": overall_metrics["actual_avg_inventory_value"],
        },
        {
            "metric": "total_ordering_cost",
            "value": overall_metrics["total_ordering_cost"],
        },
        {
            "metric": "total_lost_sales_units",
            "value": overall_metrics["total_lost_sales_units"],
        },
    ]
    pd.DataFrame(summary_rows).to_csv(output_dir / "kpi_summary.csv", index=False)

    print(f"policy_path={args.policy_path}")
    print(f"output_dir={output_dir}")
    print(f"service_level={overall_metrics['service_level']:.6f}")
    print(f"avg_inventory_value={overall_metrics['avg_inventory_value']:.4f}")
    print(f"total_ordering_cost={overall_metrics['total_ordering_cost']:.4f}")


if __name__ == "__main__":
    main()
