import pandas as pd
import numpy as np

sim = pd.read_csv('stock_policy_product_output/simulation_daily.csv')
sku_metrics = pd.read_csv('stock_policy_product_output/sku_metrics.csv')
policy = pd.read_csv('stock_policy_product_output/policy_enriched.csv')
sim['date'] = pd.to_datetime(sim['date'])

summary = {}

# =====================================================================
# 1. LEAD TIME COMPLIANCE — orders arrive exactly on d+LT?
# =====================================================================
print('=' * 90)
print('1. LEAD TIME — orders arriving on correct day?')
print('=' * 90)
# Find order rows and their arrival dates
orders = sim[sim['order_qty'] > 0].copy()
orders['expected_arrival'] = orders['date'] + pd.to_timedelta(orders['lead_time_days'], unit='D')
orders['arrival_date_parsed'] = pd.to_datetime(orders['arrival_date'], errors='coerce')
orders['arrival_on_time'] = orders['arrival_date_parsed'] == orders['expected_arrival']

total_orders = len(orders)
on_time = orders['arrival_on_time'].sum()
late = total_orders - on_time
summary['lead_time'] = {
    'total_orders': total_orders,
    'on_time': on_time,
    'late': late
}
print(f'  Total orders placed: {total_orders}')
print(f'  Arriving on expected d+LT: {on_time} ({on_time/total_orders*100:.1f}%)' if total_orders > 0 else '  0 orders')
if late > 0:
    print(f'  Late/missing: {late}')
    print()
    # Show the problematic orders
    late_orders = orders[~orders['arrival_on_time']]
    for _, r in late_orders.iterrows():
        exp = r['expected_arrival'].strftime('%Y-%m-%d') if pd.notna(r['expected_arrival']) else 'NA'
        act = r['arrival_date_parsed'].strftime('%Y-%m-%d') if pd.notna(r['arrival_date_parsed']) else 'NaN/None'
        print(f'  SKU {r["product"]} Loja {r["location"]} | Ordered: {r["date"].strftime("%Y-%m-%d")} | Expected: {exp} | Actual: {act} | Qty: {r["order_qty"]}')

print()

# Verify that received_qty matches order_qty at the right time
received = sim[sim['received_qty'] > 0].copy()
print(f'  Total receipt events (received_qty > 0): {len(received)}')

# Cross-check: every order should have a corresponding receipt
order_by_sku_loc_date = orders.groupby(['product', 'location', 'expected_arrival']).agg({'order_qty': 'sum'}).reset_index()
recv_by_sku_loc_date = received.groupby(['product', 'location', 'date']).agg({'received_qty': 'sum'}).reset_index()
merged = order_by_sku_loc_date.merge(recv_by_sku_loc_date, 
                                      left_on=['product', 'location', 'expected_arrival'],
                                      right_on=['product', 'location', 'date'],
                                      how='outer', indicator=True)
print(f'  Orders with matching receipt: {len(merged[merged["_merge"] == "both"])}')
print(f'  Receipts with no order match: {len(merged[merged["_merge"] == "right_only"])}')
no_match = merged[merged['_merge'] != 'both']
if len(no_match) > 0:
    print(f'  Dangling ({len(no_match)}):')
    for _, r in no_match.iterrows():
        print(f'    SKU {r["product"]} Loja {r["location"]} Date {str(r.get("date", r.get("expected_arrival", "?")))[:10]} | merge={r["_merge"]}')

# =====================================================================
# 2. NEGATIVE INVENTORY — silent negatives?
# =====================================================================
print()
print('=' * 90)
print('2. NEGATIVE INVENTORY — silent negatives?')
print('=' * 90)
neg = sim[sim['ending_inventory'] < 0]
neg_open = sim[sim['opening_inventory'] < 0]
print(f'  Days with negative ending_inventory: {len(neg)}')
if len(neg) > 0:
    for _, r in neg.iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | end_inv={r["ending_inventory"]:.0f} | open={r["opening_inventory"]:.0f} | demand={r["actual_demand"]:.0f} | lost={r["lost_sales_units"]:.0f}')
print(f'  Days with negative opening_inventory: {len(neg_open)}')

# Check: does ending_inventory = opening_inventory + received_qty - fulfilled_units?
sim['expected_end'] = sim['opening_inventory'] + sim['received_qty'] - sim['fulfilled_units']
sim['inv_diff'] = (sim['ending_inventory'] - sim['expected_end']).abs()
inconsistent_inv = sim[sim['inv_diff'] > 0.01]
print(f'  Days where ending != opening+received-fulfilled: {len(inconsistent_inv)}')
if len(inconsistent_inv) > 0:
    for _, r in inconsistent_inv.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | end={r["ending_inventory"]:.0f} | expect={r["expected_end"]:.0f} | open={r["opening_inventory"]:.0f} + recv={r["received_qty"]:.0f} - fulf={r["fulfilled_units"]:.0f}')

summary['negative_inv'] = {'ending_negative': len(neg), 'opening_negative': len(neg_open), 'inconsistent': len(inconsistent_inv)}

# =====================================================================
# 3. MULTIPLE SIMULTANEOUS ORDERS
# =====================================================================
print()
print('=' * 90)
print('3. MULTIPLE SIMULTANEOUS ORDERS — same SKU-store same day?')
print('=' * 90)
multi = orders.groupby(['product', 'location', 'date']).size()
multi_orders = multi[multi > 1]
print(f'  Days with multiple orders same SKU-store: {len(multi_orders)}')
if len(multi_orders) > 0:
    for idx, count in multi_orders.items():
        print(f'  SKU {idx[0]} Loja {idx[1]} {idx[2].strftime("%Y-%m-%d")} | {count} orders')

# Check: does on_order_after track correctly with pending receipts?
print()
print('  Checking on_order_after consistency:')
# For each day, on_order_after should be previous on_order - received_qty + order_qty
sim_sorted = sim.sort_values(['product', 'location', 'date']).reset_index(drop=True)
sim_sorted['prev_on_order'] = sim_sorted.groupby(['product', 'location'])['on_order_after'].shift(1).fillna(0)
sim_sorted['expected_on_order'] = sim_sorted['prev_on_order'] - sim_sorted['received_qty'] + sim_sorted['order_qty']
sim_sorted['on_order_diff'] = (sim_sorted['on_order_after'] - sim_sorted['expected_on_order']).abs()
bad_on_order = sim_sorted[sim_sorted['on_order_diff'] > 0.01]
print(f'  Days where on_order_after inconsistent: {len(bad_on_order)}')
if len(bad_on_order) > 0:
    for _, r in bad_on_order.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | on_order={r["on_order_after"]:.0f} | expected={r["expected_on_order"]:.0f} | prev={r["prev_on_order"]:.0f} - recv={r["received_qty"]:.0f} + order={r["order_qty"]:.0f}')

summary['multi_orders'] = {'days_with_multi': len(multi_orders), 'on_order_inconsistent': len(bad_on_order)}

# =====================================================================
# 4. INVENTORY POSITION CONSISTENCY
# =====================================================================
print()
print('=' * 90)
print('4. POSITION CONSISTENCY — inv_pos vs opening_inventory + on_order?')
print('=' * 90)
# inventory_position_before_order should = opening_inventory + on_order from previous day
sim_sorted['expected_pos_before'] = sim_sorted['opening_inventory'] + sim_sorted['prev_on_order']
sim_sorted['pos_before_diff'] = (sim_sorted['inventory_position_before_order'] - sim_sorted['expected_pos_before']).abs()
bad_pos = sim_sorted[sim_sorted['pos_before_diff'] > 0.01]
print(f'  Days where inv_position_before_order <> opening + prev_on_order: {len(bad_pos)}')
if len(bad_pos) > 0:
    for _, r in bad_pos.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | pos_before={r["inventory_position_before_order"]:.0f} | expected={r["expected_pos_before"]:.0f} | open={r["opening_inventory"]:.0f} + transit={r["prev_on_order"]:.0f}')

# inventory_position_after_order should = pos_before + order_qty
sim_sorted['expected_pos_after'] = sim_sorted['inventory_position_before_order'] + sim_sorted['order_qty']
sim_sorted['pos_after_diff'] = (sim_sorted['inventory_position_after_order'] - sim_sorted['expected_pos_after']).abs()
bad_pos2 = sim_sorted[sim_sorted['pos_after_diff'] > 0.01]
print(f'  Days where inv_position_after_order <> pos_before + order_qty: {len(bad_pos2)}')
if len(bad_pos2) > 0:
    for _, r in bad_pos2.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | pos_after={r["inventory_position_after_order"]:.0f} | expected={r["expected_pos_after"]:.0f} | before={r["inventory_position_before_order"]:.0f} + order={r["order_qty"]:.0f}')

summary['position_consistency'] = {'pos_before_bad': len(bad_pos), 'pos_after_bad': len(bad_pos2)}

# =====================================================================
# 5. LOST SALES COUNTING
# =====================================================================
print()
print('=' * 90)
print('5. LOST SALES — correct counting?')
print('=' * 90)
lost = sim[sim['lost_sales_units'] > 0]
print(f'  Days with lost sales: {len(lost)}')
if len(lost) > 0:
    print(f'  Total lost sales units: {lost["lost_sales_units"].sum():.0f}')
    for _, r in lost.iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | demand={r["actual_demand"]:.0f} | fulfilled={r["fulfilled_units"]:.0f} | lost={r["lost_sales_units"]:.0f} | open_inv={r["opening_inventory"]:.0f} + recv={r["received_qty"]:.0f} | end_inv={r["ending_inventory"]:.0f}')

    # Validate: lost_sales should = max(0, demand - available)
    sim['expected_lost'] = (sim['actual_demand'] - sim['opening_inventory'] - sim['received_qty']).clip(lower=0).fillna(0)
    bad_lost = sim[(sim['lost_sales_units'] - sim['expected_lost']).abs() > 0.01]
    print(f'  Rows where lost_sales differs from expected max(0, demand - available): {len(bad_lost)}')
    if len(bad_lost) > 0:
        for _, r in bad_lost.head(10).iterrows():
            print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | lost={r["lost_sales_units"]:.0f} | expected={r["expected_lost"]:.0f} | demand={r["actual_demand"]:.0f} | open={r["opening_inventory"]:.0f} + recv={r["received_qty"]:.0f}')
else:
    print('  No lost sales in the simulation.')
summary['lost_sales'] = {
    'days_with_lost': len(lost),
    'total_lost_units': lost['lost_sales_units'].sum() if len(lost) > 0 else 0,
    'miscount_rows': len(bad_lost) if len(lost) > 0 else 0
}

# =====================================================================
# 6. DAILY LOGIC — opening -> receive -> order -> demand -> close
# =====================================================================
print()
print('=' * 90)
print('6. DAILY LOGIC — correct sequence?')
print('=' * 90)
# Check: opening_inventory[t+1] should = ending_inventory[t]
sim_sorted['next_opening'] = sim_sorted.groupby(['product', 'location'])['ending_inventory'].shift(-1)
sim_sorted['open_diff'] = (sim_sorted['opening_inventory'] - sim_sorted['next_opening']).abs()
bad_open = sim_sorted[sim_sorted['open_diff'] > 0.01]
print(f'  Days where next opening <> current ending: {len(bad_open)}')
if len(bad_open) > 0:
    for _, r in bad_open.head(10).iterrows():
        rr = r['date'].strftime("%Y-%m-%d")
        print(f'  SKU {r["product"]} Loja {r["location"]} {rr} | opening={r["opening_inventory"]:.0f} | prev_ending={r.get("prev_ending", "?")} | next={r["next_opening"]:.0f}')

# Check: fulfilled_units should = min(demand, available)
sim['available_for_sale'] = sim['opening_inventory'] + sim['received_qty']
sim['expected_fulfilled'] = sim[['actual_demand', 'available_for_sale']].min(axis=1).clip(lower=0)
sim['fulfill_diff'] = (sim['fulfilled_units'] - sim['expected_fulfilled']).abs()
bad_fulfill = sim[sim['fulfill_diff'] > 0.01]
print(f'  Days where fulfilled <> min(demand, available): {len(bad_fulfill)}')
if len(bad_fulfill) > 0:
    for _, r in bad_fulfill.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | fulf={r["fulfilled_units"]:.0f} | expected={r["expected_fulfilled"]:.0f} | demand={r["actual_demand"]:.0f} | avail={r["available_for_sale"]:.0f}')

summary['daily_logic'] = {'open_close_mismatch': len(bad_open), 'fulfill_mismatch': len(bad_fulfill)}

# =====================================================================
# 7. PHYSICAL vs IN-TRANSIT INVENTORY
# =====================================================================
print()
print('=' * 90)
print('7. PHYSICAL vs IN-TRANSIT — potential divergences?')
print('=' * 90)
# on_order_after + ending_inventory should = inventory_position_after_order
sim['expected_pos_from_components'] = sim['ending_inventory'] + sim['on_order_after']
sim['pos_component_diff'] = (sim['inventory_position_after_order'] - sim['expected_pos_from_components']).abs()
bad_components = sim[sim['pos_component_diff'] > 0.01]
print(f'  Days where inv_pos_after <> ending_inv + on_order: {len(bad_components)}')
if len(bad_components) > 0:
    for _, r in bad_components.head(10).iterrows():
        print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | pos_after={r["inventory_position_after_order"]:.0f} | end={r["ending_inventory"]:.0f} + transit={r["on_order_after"]:.0f} = {r["expected_pos_from_components"]:.0f}')

# Check: peak in-transit levels
print(f'  Max on_order: {sim["on_order_after"].max():.0f} units')
print(f'  Mean on_order: {sim["on_order_after"].mean():.1f} units')
print(f'  Max ending_inventory: {sim["ending_inventory"].max():.0f} units')
print(f'  Mean ending_inventory: {sim["ending_inventory"].mean():.1f} units')

summary['physical_vs_transit'] = {
    'pos_component_mismatch': len(bad_components),
    'max_on_order': sim['on_order_after'].max(),
    'max_ending_inv': sim['ending_inventory'].max()
}

# =====================================================================
# 8. OPERATIONAL LOOP — can it oscillate badly?
# =====================================================================
print()
print('=' * 90)
print('8. OPERATIONAL LOOP — oscillation / ping-pong?')
print('=' * 90)
# Check: does the simulation ever order on consecutive days for the same SKU-store?
orders_sorted = orders.sort_values(['product', 'location', 'date']).reset_index(drop=True)
orders_sorted['prev_order_date'] = orders_sorted.groupby(['product', 'location'])['date'].shift(1)
orders_sorted['days_since_last_order'] = (orders_sorted['date'] - orders_sorted['prev_order_date']).dt.days
consecutive = orders_sorted[orders_sorted['days_since_last_order'] <= orders_sorted['lead_time_days']]
print(f'  Orders placed within lead time of previous order: {len(consecutive)}')
if len(consecutive) > 0:
    print('  (This is normal for (s,S) policy — can re-order as soon as inv drops below s)')

# Check: does inventory ever cycle (order -> stockout -> order -> stockout)?
# Check for repeated stockout flags
for product in sim['product'].unique():
    for loc in sim['location'].unique():
        subset = sim[(sim['product'] == product) & (sim['location'] == loc)]
        stockout_days = subset['simulated_stockout_flag'].sum()
        orders_count = subset['order_qty'].sum()
        if stockout_days > 0:
            total = subset['actual_demand'].sum()
            print(f'  SKU {product} Loja {loc}: {stockout_days:.0f} stockout days | {orders_count:.0f} units ordered | demand={total:.0f}')

# Check if there's an oscillation: order huge -> stockout -> order huge
print()
print('  Checking for order spikes (order_qty > 3x avg for that SKU-store):')
for product in sim['product'].unique():
    for loc in sim['location'].unique():
        subset = orders[(orders['product'] == product) & (orders['location'] == loc)]
        if len(subset) > 0:
            avg_order = subset['order_qty'].mean()
            spikes = subset[subset['order_qty'] > 3 * max(avg_order, 1)]
            if len(spikes) > 0:
                for _, r in spikes.iterrows():
                    print(f'  SKU {r["product"]} Loja {r["location"]} {r["date"].strftime("%Y-%m-%d")} | order={r["order_qty"]:.0f} vs avg={avg_order:.1f}')

summary['operational_loop'] = {
    'orders_within_lt': len(consecutive)
}

# =====================================================================
# 9. COST OF HOLDING 1 EXTRA UNIT
# =====================================================================
print()
print('=' * 90)
print('9. COST OF HOLDING EXTRA INVENTORY')
print('=' * 90)
# Capital cost: purchase_price * opportunity cost (assume 12% a.a. = ~3% per quarter)
# Storage cost: assume ~5% of purchase_price per year
opp_cost_rate = 0.03  # 12% a.a. / 4 quarters
storage_cost_per_year = 0.05
storage_cost_per_quarter = storage_cost_per_year / 4
total_holding_rate = opp_cost_rate + storage_cost_per_quarter  # ~3.25% per quarter

avg_purchase_price = sim['purchase_price'].mean()
avg_inv_units = sim['ending_inventory'].mean()
avg_inv_value = sim['simulated_inventory_value'].mean()
print(f'  Avg purchase price: R$ {avg_purchase_price:.2f}')
print(f'  Avg inventory units: {avg_inv_units:.1f}')
print(f'  Avg inventory value: R$ {avg_inv_value:.2f}')
print(f'  Holding cost (opp+storage) per quarter: {total_holding_rate*100:.2f}%')
print(f'  Cost to hold 1 extra unit per quarter: R$ {avg_purchase_price * total_holding_rate:.2f}')
print(f'  Total holding cost of avg inventory: R$ {avg_inv_value * total_holding_rate:.2f}')

# Per SKU cost of holding
print()
print('  Marginal holding cost by SKU (per extra unit / quarter):')
sku_holding = sim.groupby(['product', 'product_name', 'location']).agg(
    purchase_price=('purchase_price', 'first'),
).reset_index()
sku_holding['holding_cost_unit'] = sku_holding['purchase_price'] * total_holding_rate
sku_holding['holding_cost_extra_month'] = sku_holding['purchase_price'] * (total_holding_rate / 3) * 12  # per year actually
for _, r in sku_holding.sort_values('holding_cost_unit', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | preco: R$ {r["purchase_price"]:>6.2f} | custo manter 1un/trim: R$ {r["holding_cost_unit"]:>5.2f}')

summary['holding_cost'] = {
    'avg_purchase_price': avg_purchase_price,
    'holding_rate_per_quarter': total_holding_rate,
    'cost_per_unit_per_quarter': avg_purchase_price * total_holding_rate,
    'total_holding_cost': avg_inv_value * total_holding_rate
}

# =====================================================================
# 10. COST OF RUPTURE per SKU
# =====================================================================
print()
print('=' * 90)
print('10. COST OF RUPTURE (stockout) per SKU')
print('=' * 90)
# Cost of 1 stockout day = lost sales * sales_price (lost revenue) + lost margin contribution
sku_stockout_cost = sim[sim['lost_sales_units'] > 0].groupby(['product', 'product_name', 'location']).agg(
    lost_units=('lost_sales_units', 'sum'),
    sales_price=('sales_price', 'first'),
    purchase_price=('purchase_price', 'first'),
    stockout_days=('simulated_stockout_flag', 'sum'),
    total_demand=('actual_demand', 'sum'),
).reset_index()
sku_stockout_cost['lost_revenue'] = sku_stockout_cost['lost_units'] * sku_stockout_cost['sales_price']
sku_stockout_cost['lost_margin'] = sku_stockout_cost['lost_units'] * (sku_stockout_cost['sales_price'] - sku_stockout_cost['purchase_price'])

total_units = sim['lost_sales_units'].sum()
total_lost_rev = (sim['lost_sales_units'] * sim['sales_price']).sum()
print(f'  Total lost sales units: {total_units:.0f}')
print(f'  Total lost revenue: R$ {total_lost_rev:.2f}')
print()
if len(sku_stockout_cost) > 0:
    print('  Per SKU:')
    for _, r in sku_stockout_cost.iterrows():
        print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | {r["stockout_days"]:.0f}d | perdidas: {r["lost_units"]:.0f}un | receita perdida: R$ {r["lost_revenue"]:>7.2f} | margem perdida: R$ {r["lost_margin"]:>7.2f}')
else:
    print('  No stockout in this simulation.')

# Per-unit cost of stockout
print()
print(f'  Cost per stockout day (avg across all SKUs with stockout):')
print(f'  Avg lost revenue per stockout day: R$ {(total_lost_rev / max(len(lost), 1)):.2f}')

summary['rupture_cost'] = {
    'total_lost_units': total_units,
    'total_lost_revenue': total_lost_rev,
    'stockout_sku_count': len(sku_stockout_cost)
}

# =====================================================================
# 11. IMPACT OF POOR PROMO FORECAST
# =====================================================================
print()
print('=' * 90)
print('11. PROMO FORECAST IMPACT — poor promo prediction cost')
print('=' * 90)
promo = sim[sim['is_promo'] == 1]
non_promo = sim[sim['is_promo'] == 0]
print(f'  Promo days: {len(promo)}')
print(f'  Non-promo days: {len(non_promo)}')
promo_demand = promo['actual_demand'].sum()
non_promo_demand = non_promo['actual_demand'].sum()
print(f'  Promo demand: {promo_demand:.0f} | Non-promo: {non_promo_demand:.0f}')
promo_forecast = promo['forecast_demand'].sum()
non_promo_forecast = non_promo['forecast_demand'].sum()
print(f'  Promo forecast: {promo_forecast:.0f} | Non-promo forecast: {non_promo_forecast:.0f}')
print(f'  Promo FC error: {promo_forecast - promo_demand:.0f} ({(promo_forecast - promo_demand)/promo_demand*100:.0f}% over)')
print(f'  Non-promo FC error: {non_promo_forecast - non_promo_demand:.0f}')

# Cost of over-ordering due to inflated promo forecast
excess_inventory_promo = promo.groupby(['product', 'location', 'date']).agg(
    forecast=('forecast_demand', 'sum'),
    actual=('actual_demand', 'sum'),
    ending_inv=('ending_inventory', 'mean'),
).reset_index()
excess_inventory_promo['excess_fc'] = (excess_inventory_promo['forecast'] - excess_inventory_promo['actual']).clip(lower=0)
total_excess_fc_units = excess_inventory_promo['excess_fc'].sum()
print()
print(f'  Total excess forecast units on promo days (FC>actual): {total_excess_fc_units:.0f}')
estimated_excess_promo_cost = total_excess_fc_units * avg_purchase_price * total_holding_rate
print(f'  Estimated cost of holding promo-related excess: R$ {estimated_excess_promo_cost:.2f}')

summary['promo_impact'] = {
    'promo_days': len(promo),
    'promo_demand': promo_demand,
    'promo_fc_error': promo_forecast - promo_demand,
    'excess_fc_units': total_excess_fc_units,
    'excess_holding_cost': estimated_excess_promo_cost
}

# =====================================================================
# 12. HIGHEST RETURN PER STORED UNIT
# =====================================================================
print()
print('=' * 90)
print('12. RETURN PER STORED UNIT (margin / avg inventory)')
print('=' * 90)
sim['unit_margin'] = sim['sales_price'] - sim['purchase_price']
sku_return = sim.groupby(['product', 'product_name', 'location', 'purchase_price', 'sales_price']).agg(
    avg_inv_units=('ending_inventory', 'mean'),
    avg_inv_value=('simulated_inventory_value', 'mean'),
    total_demand=('actual_demand', 'sum'),
    total_fulfilled=('fulfilled_units', 'sum'),
    total_lost=('lost_sales_units', 'sum'),
).reset_index()
sku_return['unit_margin'] = sku_return['sales_price'] - sku_return['purchase_price']
sku_return['margin_per_stored_unit'] = sku_return['unit_margin'] / sku_return['avg_inv_units'].replace(0, np.nan)
sku_return['margin_per_revenue_dollar'] = sku_return['unit_margin'] / sku_return['purchase_price'].replace(0, np.nan)
sku_return['roi_stock'] = (sku_return['total_fulfilled'] * sku_return['unit_margin']) / sku_return['avg_inv_value'].replace(0, np.nan)

print('  Top 10 — Margin per stored unit:')
for _, r in sku_return.sort_values('margin_per_stored_unit', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | margem/un: R$ {r["unit_margin"]:>5.2f} | estq: {r["avg_inv_units"]:>5.1f} | margem/estq: R$ {r["margin_per_stored_unit"]:>6.2f}')

print()
print('  Top 10 — ROI (total margin / avg inventory value):')
for _, r in sku_return.sort_values('roi_stock', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | ROI: {r["roi_stock"]:>5.1f}x | margem total: R$ {(r["total_fulfilled"] * r["unit_margin"]):>7.2f} | estq: R$ {r["avg_inv_value"]:>6.2f}')

summary['return_per_unit'] = {
    'best_margin_per_unit': sku_return.sort_values('margin_per_stored_unit', ascending=False).head(3).to_dict('records')
}

# =====================================================================
# 13. WORST STOCK/REVENUE RATIO
# =====================================================================
print()
print('=' * 90)
print('13. WORST STOCK/REVENUE RATIO')
print('=' * 90)
sku_return['stock_revenue_ratio'] = sku_return['avg_inv_value'] / (sku_return['total_fulfilled'] * sku_return['sales_price']).replace(0, np.nan)
print('  Worst 10 — highest inventory/revenue ratio:')
for _, r in sku_return.sort_values('stock_revenue_ratio', ascending=False).head(10).iterrows():
    total_rev = r['total_fulfilled'] * r['sales_price']
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | estq: R$ {r["avg_inv_value"]:>6.2f} | receita: R$ {total_rev:>7.2f} | ratio: {r["stock_revenue_ratio"]:>5.2f} | margem: R$ {r["unit_margin"]:>5.2f}')

summary['worst_ratio'] = sku_return.sort_values('stock_revenue_ratio', ascending=False).head(3).to_dict('records')

# =====================================================================
# 14. ROI OF THE PROPOSED POLICY
# =====================================================================
print()
print('=' * 90)
print('14. ROI OF THE PROPOSED POLICY vs. ACTUAL')
print('=' * 90)
# Compare simulated vs actual
total_sim_inv = sim['simulated_inventory_value'].mean()
total_actual_inv = sim['actual_inventory_value'].mean()
total_sim_orders = sim['ordering_cost'].sum()
# Actual ordering cost: count DELIVERY events from original data
total_sim_lost = (sim['lost_sales_units'] * sim['sales_price']).sum()
# For actual, we can approximate lost sales
total_actual_lost = 0
actual_orders = 0

# Capital freed/reduction
capital_diff = total_actual_inv - total_sim_inv
print(f'  Simulated avg inventory: R$ {total_sim_inv:.2f}')
print(f'  Actual avg inventory: R$ {total_actual_inv:.2f}')
print(f'  Capital change: R$ {capital_diff:+.2f}')
print()
print(f'  Simulated ordering cost: R$ {total_sim_orders:.2f}')
print(f'  Simulated lost sales revenue: R$ {total_sim_lost:.2f}')
print(f'  Simulated total cost: R$ {total_sim_orders + total_sim_lost:.2f}')

# Simple ROI: value of lost sales avoided + ordering cost change / capital invested
# Without actual stockout data, use counterfactual
print()
print('  NOTE: Without the actual store policy (baseline) data, we cannot compute')
print('  a precise ROI vs "do nothing". The simulation already performs at 99.9% SL.')

summary['roi_policy'] = {
    'sim_avg_inv': total_sim_inv,
    'actual_avg_inv': total_actual_inv,
    'capital_diff': capital_diff,
    'sim_ordering_cost': total_sim_orders,
    'sim_lost_revenue': total_sim_lost
}

# =====================================================================
# 15. MARGINAL COST OF INCREASING SERVICE LEVEL
# =====================================================================
print()
print('=' * 90)
print('15. MARGINAL COST OF INCREASING SERVICE LEVEL (z value sensitivity)')
print('=' * 90)
# From the grid search
try:
    tune = pd.read_csv('stock_policy_product_output/tuning_search.csv')
    tune = tune.sort_values('z_value')
    print(f'  Grid search: {len(tune)} points')
    print(f'  {"z":>6s} {"review":>8s} {"SL":>6s} {"Inv":>8s} {"Custo":>8s} {"InvDelta/z":>10s}')
    tune = tune.sort_values(['review_days', 'z_value'])
    for rd in sorted(tune['review_days'].unique()):
        subset = tune[tune['review_days'] == rd].sort_values('z_value')
        print(f'  --- review_days={rd} ---')
        prev_inv = None
        for _, r in subset.iterrows():
            inv = r['avg_inventory_value']
            if prev_inv is not None:
                marginal = inv - prev_inv
            else:
                marginal = 0
            prev_inv = inv
            print(f'  {r["z_value"]:>6.2f} {int(r["review_days"]):>8d} {r["service_level"]:>5.1%} {inv:>8.2f} {r["total_ordering_cost"]:>8.0f} {marginal:>+10.2f}')
except FileNotFoundError:
    print('  Tuning search not available.')

summary['marginal_cost_sl'] = tune.to_dict('records') if 'tune' in dir() else []

# =====================================================================
# 16. EXCESS CAPITAL — how much money is stuck?
# =====================================================================
print()
print('=' * 90)
print('16. EXCESS CAPITAL — money stuck in unnecessary inventory')
print('=' * 90)
# Compare simulated vs actual for each SKU-store
sim_inv_by_sku = sim.groupby(['product', 'product_name', 'location']).agg(
    sim_avg_value=('simulated_inventory_value', 'mean'),
    actual_avg_value=('actual_inventory_value', 'mean'),
    purchase_price=('purchase_price', 'first'),
    sim_avg_units=('ending_inventory', 'mean'),
    actual_avg_units=('actual_balance', 'mean'),
).reset_index()
sim_inv_by_sku['delta_value'] = sim_inv_by_sku['sim_avg_value'] - sim_inv_by_sku['actual_avg_value']
total_excess = sim_inv_by_sku[sim_inv_by_sku['delta_value'] > 0]['delta_value'].sum()
total_deficit = sim_inv_by_sku[sim_inv_by_sku['delta_value'] < 0]['delta_value'].sum()

print(f'  Total excess capital (sim > actual): R$ {total_excess:.2f}')
print(f'  Total reduction (sim < actual): R$ {abs(total_deficit):.2f}')
print(f'  Net change: R$ {total_excess + total_deficit:.2f}')
print()
print('  SKUs with most excess capital:')
for _, r in sim_inv_by_sku.sort_values('delta_value', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | sim: R$ {r["sim_avg_value"]:>7.2f} | actual: R$ {r["actual_avg_value"]:>7.2f} | delta: R$ {r["delta_value"]:>+8.2f} | sim: {r["sim_avg_units"]:>5.1f}un | actual: {r["actual_avg_units"]:>5.1f}un')

print()
print('  SKUs that freed capital (sim < actual):')
for _, r in sim_inv_by_sku.sort_values('delta_value').head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | sim: R$ {r["sim_avg_value"]:>7.2f} | actual: R$ {r["actual_avg_value"]:>7.2f} | delta: R$ {r["delta_value"]:>+8.2f}')

summary['excess_capital'] = {
    'total_excess': total_excess,
    'total_reduction': abs(total_deficit),
    'net_change': total_excess + total_deficit
}

# =====================================================================
# FINAL SUMMARY
# =====================================================================
print()
print('=' * 90)
print('VALIDATION SUMMARY')
print('=' * 90)
for key, val in summary.items():
    print(f'  {key}: {val}')
