# Power BI – Analytical Dashboard Setup Guide
**Dashboard:** Delivery Performance Overview  
**Source files:** `final_X.csv` + `final_y_class.csv` + `analytics_orders.csv`

> `analytics_orders.csv` is a pre-built enriched table (96,462 delivered orders) that adds
> `review_score`, `days_late`, `delivery_status`, and `payment_type` — columns excluded from
> the model to prevent leakage but valuable for the analytical dashboard.
> It is a **separate table** in Power BI; no join to `final_X` is needed.

---

## Overview of steps

1. [Import the data](#1-import-the-data)
2. [Merge the two files in Power Query](#2-merge-the-two-files-in-power-query)
3. [Fix column types in Power Query](#3-fix-column-types-in-power-query)
4. [Create a Category column in Power Query](#4-create-a-category-column-in-power-query)
5. [Create bucket columns in Power Query](#5-create-bucket-columns-in-power-query)
6. [Create DAX measures](#6-create-dax-measures)
7. [Build the visuals — Page 1: Operational](#7-build-the-visuals)
8. [Build the visuals — Page 2: Customer Impact](#8-page-2-customer-impact-visuals)
9. [Page 2 DAX measures](#9-page-2-dax-measures)

---

## 1. Import the data

1. Open Power BI Desktop → **Home → Get Data → Text/CSV**
2. Select `final_X.csv` → **Load**
3. Repeat for `final_y_class.csv` → **Load**

You now have two tables. Rename them clearly:
- `final_X.csv` → **`Orders`**
- `final_y_class.csv` → **`Labels`**

---

## 2. Merge the two files in Power Query

Both files have the same 109,273 rows in the same order. You need to add an index to each, then merge on that index so `is_late` lands as a column in `Orders`.

1. **Home → Transform Data** (opens Power Query Editor)

**In the `Orders` query:**
- **Add Column → Index Column → From 0**
- This creates a column called `Index`

**In the `Labels` query:**
- **Add Column → Index Column → From 0**
- This also creates `Index`

**Back in `Orders` query:**
- **Home → Merge Queries (as new)** → select `Orders` and `Labels`, match on `Index` in both → Join Kind: **Left Outer** → OK
- Expand the merged `Labels` column: tick only `is_late`, untick "Use original column name as prefix" → OK
- Delete the `Index` column from `Orders` (right-click → Remove)

> You now have one table called `Orders` with 26 columns: all 25 original features + `is_late`.

---

## 3. Fix column types in Power Query

Power BI may misread some columns. Set these manually by clicking the column header icon:

| Column | Correct Type |
|---|---|
| `same_state` | Whole Number |
| `is_late` | Whole Number |
| `order_item_id` | Decimal Number |
| `price` | Decimal Number |
| `freight_value` | Decimal Number |
| `product_weight_g` | Decimal Number |
| `approval_lag_hrs` | Decimal Number |
| `seller_prep_days` | Decimal Number |
| `estimated_window_days` | Whole Number |
| All `product_category_grouped_*` columns | True/False (Logical) |

---

## 4. Create a Category column in Power Query

The category is currently spread across 9 boolean dummy columns. You need to collapse them into one readable text column.

In the **Orders** query:
1. **Add Column → Custom Column**
2. Name it `product_category`
3. Paste this formula exactly:

```
if [product_category_grouped_health_beauty] = true then "Health Beauty"
else if [product_category_grouped_electronics] = true then "Electronics"
else if [product_category_grouped_furniture] = true then "Furniture"
else if [product_category_grouped_home_comfort] = true then "Home Comfort"
else if [product_category_grouped_leisure_media] = true then "Leisure Media"
else if [product_category_grouped_food_drink] = true then "Food & Drink"
else if [product_category_grouped_fashion] = true then "Fashion"
else if [product_category_grouped_home_appliances] = true then "Home Appliances"
else "Others"
```

4. Set column type to **Text**

> This gives you a single `product_category` column you can use directly in charts.

---

## 5. Create bucket columns in Power Query

### 5a. Seller Prep Time Bucket

Used for: **"Late Rate by Seller Preparation Time"** bar chart

1. **Add Column → Custom Column**
2. Name: `seller_prep_bucket`
3. Formula:

```
if [seller_prep_days] <= 1 then "0–1 day"
else if [seller_prep_days] <= 2 then "1–2 days"
else if [seller_prep_days] <= 3 then "2–3 days"
else if [seller_prep_days] <= 5 then "3–5 days"
else "5+ days"
```

4. Set column type to **Text**

**Add a sort column so buckets display in order (not alphabetically):**
1. **Add Column → Custom Column**
2. Name: `seller_prep_bucket_sort`
3. Formula:

```
if [seller_prep_days] <= 1 then 1
else if [seller_prep_days] <= 2 then 2
else if [seller_prep_days] <= 3 then 3
else if [seller_prep_days] <= 5 then 4
else 5
```

4. Set type to **Whole Number**

---

### 5b. Estimated Delivery Window Bucket

Used for: **"Late Rate by Promised Delivery Window"** bar chart

1. **Add Column → Custom Column**
2. Name: `window_bucket`
3. Formula:

```
if [estimated_window_days] < 10 then "< 10 days"
else if [estimated_window_days] < 20 then "10–20 days"
else if [estimated_window_days] < 30 then "20–30 days"
else "30+ days"
```

4. Set column type to **Text**

**Sort column:**
1. **Add Column → Custom Column**
2. Name: `window_bucket_sort`
3. Formula:

```
if [estimated_window_days] < 10 then 1
else if [estimated_window_days] < 20 then 2
else if [estimated_window_days] < 30 then 3
else 4
```

4. Set type to **Whole Number**

---

**Click Home → Close & Apply** to load all changes back into Power BI.

---

### Sort buckets by their sort columns (do this after Close & Apply)

For each bucket column, go to **Data view** → click the `seller_prep_bucket` column → **Column Tools → Sort by Column → seller_prep_bucket_sort**. Repeat for `window_bucket` / `window_bucket_sort`.

---

## 6. Create DAX measures

Go to **Report view → select the `Orders` table in the Fields pane → Home → New Measure** and enter each of the following.

---

### Core measures

```dax
Total Orders = COUNTROWS(Orders)
```

```dax
Late Orders = CALCULATE(COUNTROWS(Orders), Orders[is_late] = 1)
```

```dax
Late Rate % = DIVIDE([Late Orders], [Total Orders], 0) * 100
```

---

### KPI card measures

```dax
Avg Seller Prep (Late) =
CALCULATE(AVERAGE(Orders[seller_prep_days]), Orders[is_late] = 1)
```

```dax
Avg Seller Prep (OnTime) =
CALCULATE(AVERAGE(Orders[seller_prep_days]), Orders[is_late] = 0)
```

```dax
Avg Approval Lag (Late) =
CALCULATE(AVERAGE(Orders[approval_lag_hrs]), Orders[is_late] = 1)
```

```dax
Avg Approval Lag (OnTime) =
CALCULATE(AVERAGE(Orders[approval_lag_hrs]), Orders[is_late] = 0)
```

```dax
Avg Window (Late) =
CALCULATE(AVERAGE(Orders[estimated_window_days]), Orders[is_late] = 1)
```

```dax
Avg Window (OnTime) =
CALCULATE(AVERAGE(Orders[estimated_window_days]), Orders[is_late] = 0)
```

---

### Comparison measures (used as reference lines or tooltips)

```dax
Seller Prep Difference % =
DIVIDE(
    [Avg Seller Prep (Late)] - [Avg Seller Prep (OnTime)],
    [Avg Seller Prep (OnTime)],
    0
) * 100
```

---

## 7. Build the visuals

---

### Visual 1 — KPI Cards (top row, ×4)

Insert 4 **Card** visuals.

| Card | Field (Value) | Format |
|---|---|---|
| Late Delivery Rate | `Late Rate %` | 1 decimal, suffix "%" |
| Avg Seller Prep – Late | `Avg Seller Prep (Late)` | 1 decimal, suffix " days" |
| Avg Approval Lag – Late | `Avg Approval Lag (Late)` | 1 decimal, suffix " hrs" |
| Avg Delivery Window – Late | `Avg Window (Late)` | 1 decimal, suffix " days" |

**Optional:** Add a reference label under each card showing the on-time equivalent (e.g. "vs 2.1 days on-time") using a second small Card or the card's subtitle field.

---

### Visual 2 — Late Rate by Seller Prep Time (Bar Chart)

| Setting | Value |
|---|---|
| Visual type | Clustered Bar Chart |
| X-axis | `seller_prep_bucket` (sorted by `seller_prep_bucket_sort`) |
| Y-axis | `Late Rate %` measure |
| Legend | None |
| Data labels | On |

**Conditional formatting on bars:**
- Go to Format → Data Colors → **fx (conditional formatting)**
- Rule: if value < 8 → green, 8–12 → amber, > 12 → red

---

### Visual 3 — Late Rate by Promised Delivery Window (Bar Chart)

| Setting | Value |
|---|---|
| Visual type | Clustered Bar Chart |
| X-axis | `window_bucket` (sorted by `window_bucket_sort`) |
| Y-axis | `Late Rate %` measure |
| Legend | None |
| Data labels | On |

Same conditional color rules as Visual 2.

---

### Visual 4 — Late Rate by Product Category (Horizontal Bar)

| Setting | Value |
|---|---|
| Visual type | Clustered Bar Chart |
| Y-axis | `product_category` |
| X-axis | `Late Rate %` measure |
| Sort | Sort descending by `Late Rate %` |
| Data labels | On |

**To make it horizontal:** In Format pane, set the chart orientation, or use a **Bar Chart** (not Column Chart) — Power BI uses "Bar" for horizontal and "Column" for vertical.

---

### Visual 5 — Key Takeaways (Text Box)

Insert a **Text Box** and type your three insight statements directly. No measure needed — this is a static annotation panel.

---

## Final checklist before presenting

- [ ] All four KPI cards show correct values matching the reference numbers below
- [ ] Bucket columns are sorting correctly (not alphabetically)
- [ ] Category column is showing 9 readable names (not `TRUE`/`FALSE`)
- [ ] Conditional colors are applied to bar charts
- [ ] No filters are accidentally active on any visual

---

## Reference numbers (verify your visuals match these)

| Metric | Value |
|---|---|
| Total orders | 109,273 |
| Late orders | 8,610 |
| Overall late rate | 7.9% |
| Avg seller prep — late orders | 4.9 days |
| Avg seller prep — on-time orders | 2.1 days |
| Avg approval lag — late orders | 12.8 hrs |
| Avg approval lag — on-time orders | 10.3 hrs |
| Avg estimated window — late orders | 21.6 days |
| Avg estimated window — on-time orders | 23.6 days |
| Late rate for sellers with 5+ day prep | 20.5% |
| Late rate for sellers with 0–1 day prep | 6.4% |
| Late rate for < 10-day window | 14.5% |
| Late rate for 30+ day window | 5.0% |

---

## 8. Page 2 — Customer Impact Visuals

> **Source table for this page: `AnalyticsOrders`** (imported from `analytics_orders.csv`)  
> This table is independent — no relationship to `Orders` is needed.

### Import `analytics_orders.csv`

1. **Home → Get Data → Text/CSV** → select `analytics_orders.csv` → **Load**
2. Rename the table to **`AnalyticsOrders`**
3. In Power Query, set these column types:

| Column | Type |
|---|---|
| `is_late` | Whole Number |
| `days_late` | Decimal Number |
| `review_score` | Decimal Number |
| `seller_prep_days` | Decimal Number |
| `approval_lag_hrs` | Decimal Number |
| `estimated_window_days` | Whole Number |
| `same_state` | Whole Number |
| `delivery_status_sort` | Whole Number |
| `delivery_status` | Text |
| `payment_type` | Text |
| `product_category_grouped` | Text |
| `order_month` | Text |

4. **Sort column:** click `delivery_status` column → **Column Tools → Sort by Column → delivery_status_sort**

---

## 9. Page 2 DAX measures

Create these measures in the **`AnalyticsOrders`** table.

```dax
AO Total Orders = COUNTROWS(AnalyticsOrders)
```

```dax
AO Late Orders = CALCULATE(COUNTROWS(AnalyticsOrders), AnalyticsOrders[is_late] = 1)
```

```dax
AO Avg Review Score =
AVERAGEX(
    FILTER(AnalyticsOrders, NOT(ISBLANK(AnalyticsOrders[review_score]))),
    AnalyticsOrders[review_score]
)
```

```dax
AO 1-Star Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(AnalyticsOrders),
        AnalyticsOrders[review_score] = 1,
        NOT(ISBLANK(AnalyticsOrders[review_score]))),
    CALCULATE(COUNTROWS(AnalyticsOrders),
        NOT(ISBLANK(AnalyticsOrders[review_score]))),
    0
) * 100
```

```dax
AO 1-Star Rate Late % =
CALCULATE([AO 1-Star Rate %], AnalyticsOrders[is_late] = 1)
```

```dax
AO 1-Star Rate OnTime % =
CALCULATE([AO 1-Star Rate %], AnalyticsOrders[is_late] = 0)
```

```dax
AO 5-Star Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(AnalyticsOrders),
        AnalyticsOrders[review_score] = 5,
        NOT(ISBLANK(AnalyticsOrders[review_score]))),
    CALCULATE(COUNTROWS(AnalyticsOrders),
        NOT(ISBLANK(AnalyticsOrders[review_score]))),
    0
) * 100
```

```dax
AO Avg Days Late =
CALCULATE(
    AVERAGE(AnalyticsOrders[days_late]),
    AnalyticsOrders[is_late] = 1
)
```

---

### Visual P2-1 — KPI Cards (top row, ×3)

| Card | Measure | Expected value |
|---|---|---|
| 1-Star Rate (Late Orders) | `AO 1-Star Rate Late %` | 45.2% |
| 1-Star Rate (On-Time Orders) | `AO 1-Star Rate OnTime %` | 6.5% |
| Avg Days Late (when late) | `AO Avg Days Late` | 9.9 days |

Use the same HTML Content visual approach as Page 1 for styled cards with badges, or use native Card visuals.

**HTML Content measure for the most impactful card:**

```dax
Card_1Star_HTML =
VAR late_rate  = [AO 1-Star Rate Late %]
VAR ontime_rate = [AO 1-Star Rate OnTime %]
VAR multiplier = FORMAT(ROUND(late_rate / ontime_rate, 0), "0") & "× worse"
RETURN
"<div style='font-family:Segoe UI,Arial,sans-serif;padding:18px 20px;'>
  <p style='font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.6px;margin:0 0 8px 0;'>1-STAR RATE — LATE ORDERS</p>
  <p style='margin:0 0 6px 0;'>
    <span style='font-size:34px;font-weight:700;color:#ef4444;'>" & FORMAT(late_rate, "0.0") & "</span>
    <span style='font-size:16px;color:#9ca3af;margin-left:2px;'>%</span>
  </p>
  <p style='font-size:12px;color:#6b7280;margin:0 0 10px 0;'>vs " & FORMAT(ontime_rate, "0.0") & "% for on-time orders</p>
  <span style='background:#fee2e2;color:#b91c1c;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;'>" & multiplier & "</span>
</div>"
```

---

### Visual P2-2 — Avg Review Score by Delivery Status (Column Chart)

This is the most powerful visual on Page 2 — it shows the cliff-edge drop from On Time (4.22) to Very Late (1.74).

| Setting | Value |
|---|---|
| Visual type | Clustered Column Chart |
| X-axis | `delivery_status` (sorted by `delivery_status_sort`) |
| Y-axis | `AO Avg Review Score` measure |
| Data labels | On, show 1 decimal |
| Y-axis range | 1 to 5 (set manually so the drop is visually dramatic) |

**Conditional color by delivery status:**  
Format → Data Colors → fx:
- `Very Late (7d+)` → `#ef4444` (red)
- `Late (1-7d)` → `#f59e0b` (amber)
- `On Time` → `#3b82f6` (blue)
- `Early` → `#10b981` (green)

To apply per-bar colors: use **Field value** formatting, or add a calculated column in Power Query:

```
// Power Query custom column: review_score_color
if [delivery_status] = "Very Late (7d+)" then "#ef4444"
else if [delivery_status] = "Late (1-7d)" then "#f59e0b"
else if [delivery_status] = "On Time" then "#3b82f6"
else "#10b981"
```

---

### Visual P2-3 — Days-Late Distribution (Column Chart)

Shows that when deliveries fail, they fail badly — the average is nearly 10 days late.

**Power Query — add this calculated column to `AnalyticsOrders`:**

```
// Custom column: days_late_bucket
if [days_late] = 0 then "On Time"
else if [days_late] <= 3 then "1–3 days"
else if [days_late] <= 7 then "4–7 days"
else if [days_late] <= 14 then "8–14 days"
else if [days_late] <= 30 then "15–30 days"
else "30+ days"
```

Add a sort column:

```
// Custom column: days_late_bucket_sort
if [days_late] = 0 then 0
else if [days_late] <= 3 then 1
else if [days_late] <= 7 then 2
else if [days_late] <= 14 then 3
else if [days_late] <= 30 then 4
else 5
```

Sort `days_late_bucket` by `days_late_bucket_sort`.

| Setting | Value |
|---|---|
| Visual type | Clustered Column Chart |
| X-axis | `days_late_bucket` (sorted by `days_late_bucket_sort`) |
| Y-axis | Count of rows (`AO Total Orders`) |
| Filter | Add a visual-level filter: `is_late = 1` (late orders only) |
| Data labels | On |

---

### Visual P2-4 — Review Score Distribution (Stacked Bar or Donut, ×2)

Two side-by-side visuals comparing review score breakdown for late vs on-time orders.

**Option A — Two Donut Charts (simplest):**
- Donut 1: Filter `is_late = 0` → field: `review_score` (Count), legend: `review_score`
- Donut 2: Filter `is_late = 1` → same setup

**Option B — 100% Stacked Bar (more impactful):**

Add a calculated column in Power Query:
```
// Custom column: review_label
if [review_score] = 1 then "1 Star"
else if [review_score] = 2 then "2 Stars"
else if [review_score] = 3 then "3 Stars"
else if [review_score] = 4 then "4 Stars"
else if [review_score] = 5 then "5 Stars"
else "No Review"
```

| Setting | Value |
|---|---|
| Visual type | 100% Stacked Bar Chart |
| Y-axis | `is_late` (shows two bars: 0 = on-time, 1 = late) |
| Values | Count of `order_id` |
| Legend | `review_label` |
| Colors | 1 Star = red, 5 Stars = green, others = gradient |

This single visual shows the full shift in review distribution — late orders flip from mostly 5-star to mostly 1-star.

---

## Page 2 reference numbers

| Metric | Value |
|---|---|
| Total orders in AnalyticsOrders | 96,462 |
| Very Late orders (7d+) | 3,763 |
| Late orders (1–7d) | 5,524 |
| On Time orders | 20,707 |
| Early orders | 66,461 |
| Avg review — Very Late | 1.74 ★ |
| Avg review — Late (1-7d) | 3.54 ★ |
| Avg review — On Time | 4.22 ★ |
| Avg review — Early | 4.32 ★ |
| 1-star rate — late orders | 45.2% |
| 1-star rate — on-time orders | 6.5% |
| 5-star rate — late orders | 21.8% |
| 5-star rate — on-time orders | 62.1% |
| Avg days late (when late) | 9.9 days |
| Median days late | 6 days |
| Orders 1–3 days late | 2,677 |
| Orders 4–7 days late | 1,823 |
| Orders 8–14 days late | 1,800 |
| Orders 15–30 days late | 1,203 |
| Orders 30+ days late | 362 |
