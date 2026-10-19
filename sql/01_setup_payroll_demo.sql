-- =====================================================================
-- Payroll demo data for Unity Catalog
-- Run in: Databricks SQL Editor (attached to your SQL warehouse) or a SQL notebook
--
-- Layout:   payroll_demo (catalog)
--             ├── raw        -> sensitive, row-level data (HR/Payroll team only)
--             └── reporting  -> aggregated views (what the app reads)
--
-- If CREATE CATALOG is not allowed in your workspace, ask an admin, or use an
-- existing catalog: find/replace "payroll_demo" with its name and delete line 1 below.
-- =====================================================================

CREATE CATALOG IF NOT EXISTS payroll_demo;
CREATE SCHEMA  IF NOT EXISTS payroll_demo.raw;
CREATE SCHEMA  IF NOT EXISTS payroll_demo.reporting;

-- ---------- 1. employees (120 dummy people) ----------
CREATE OR REPLACE TABLE payroll_demo.raw.employees AS
SELECT
  id                                                                     AS employee_id,
  concat('Employee ', lpad(CAST(id AS STRING), 3, '0'))                  AS full_name,
  element_at(array('Engineering','Sales','Finance','HR','Operations','Marketing'),
             id % 6 + 1)                                                 AS department,
  element_at(array('Analyst','Associate','Senior','Manager','Lead'),
             id % 5 + 1)                                                 AS job_title,
  element_at(array('India','USA','UK','Germany','Singapore'),
             id % 5 + 1)                                                 AS country,
  date_add(add_months(current_date(), -30), CAST((id * 37) % 1000 AS INT)) AS hire_date,
  CAST(40000 + ((id * 7919) % 60000) + ((id % 6) * 6000) AS DECIMAL(12,2)) AS base_salary_annual
FROM (SELECT explode(sequence(1, 120)) AS id);

-- ---------- 2. payroll_runs (monthly, last 12 months) ----------
CREATE OR REPLACE TABLE payroll_demo.raw.payroll_runs AS
WITH months AS (
  SELECT explode(sequence(add_months(trunc(current_date(), 'MM'), -11),
                          trunc(current_date(), 'MM'),
                          INTERVAL 1 MONTH)) AS pay_period
),
base AS (
  SELECT
    e.employee_id,
    m.pay_period,
    ROUND(e.base_salary_annual / 12, 2) AS base_pay,
    CASE WHEN month(m.pay_period) IN (3, 12) AND e.employee_id % 3 = 0
         THEN ROUND(e.base_salary_annual / 12 * 0.5, 2)
         ELSE CAST(0 AS DECIMAL(12,2)) END AS bonus
  FROM payroll_demo.raw.employees e
  JOIN months m ON e.hire_date <= last_day(m.pay_period)   -- only pay people already hired
)
SELECT
  ROW_NUMBER() OVER (ORDER BY pay_period, employee_id)        AS payroll_id,
  employee_id,
  pay_period,
  base_pay,
  bonus,
  base_pay + bonus                                            AS gross_pay,
  ROUND((base_pay + bonus) * 0.18, 2)                         AS tax,
  ROUND((base_pay + bonus) * 0.06, 2)                         AS deductions,
  (base_pay + bonus) - ROUND((base_pay + bonus) * 0.18, 2)
                     - ROUND((base_pay + bonus) * 0.06, 2)    AS net_pay
FROM base;

-- ---------- 3. Reporting views: aggregates only, no names or individual salaries ----------
CREATE OR REPLACE VIEW payroll_demo.reporting.v_payroll_monthly AS
SELECT
  pay_period,
  COUNT(DISTINCT employee_id) AS headcount,
  SUM(gross_pay)              AS gross_total,
  SUM(bonus)                  AS bonus_total,
  SUM(tax)                    AS tax_total,
  SUM(deductions)             AS deductions_total,
  SUM(net_pay)                AS net_total
FROM payroll_demo.raw.payroll_runs
GROUP BY pay_period;

CREATE OR REPLACE VIEW payroll_demo.reporting.v_payroll_by_department AS
SELECT
  p.pay_period,
  e.department,
  COUNT(DISTINCT p.employee_id) AS headcount,
  SUM(p.gross_pay)              AS gross_total,
  SUM(p.net_pay)                AS net_total,
  ROUND(AVG(p.gross_pay), 2)    AS avg_gross
FROM payroll_demo.raw.payroll_runs p
JOIN payroll_demo.raw.employees e ON p.employee_id = e.employee_id
GROUP BY p.pay_period, e.department
HAVING COUNT(DISTINCT p.employee_id) >= 5;   -- small groups could reveal an individual's pay

-- ---------- 4. Sanity checks ----------
SELECT COUNT(*) AS employees FROM payroll_demo.raw.employees;
SELECT * FROM payroll_demo.reporting.v_payroll_monthly ORDER BY pay_period;
SELECT * FROM payroll_demo.reporting.v_payroll_by_department
WHERE pay_period = (SELECT max(pay_period) FROM payroll_demo.reporting.v_payroll_monthly)
ORDER BY gross_total DESC;
