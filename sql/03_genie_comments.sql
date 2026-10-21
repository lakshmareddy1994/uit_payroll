-- =====================================================================
-- Comments Genie reads when it writes SQL. Run after sql/01_setup_payroll_demo.sql
-- as a user who can alter these views. Safe to re-run.
--
-- Point the Genie agent at these two views only. Leave payroll_demo.raw out
-- so individual names and salaries stay out of the chat.
-- =====================================================================

COMMENT ON VIEW payroll_demo.reporting.v_payroll_monthly IS
  'One row per calendar month of company-wide payroll. Amounts are USD. pay_period is the first day of that month.';

COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.pay_period IS
  'First day of the pay month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.headcount IS
  'Number of employees paid in the month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.gross_total IS
  'Sum of gross pay in USD, including bonuses.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.bonus_total IS
  'Sum of bonuses in USD. Bonuses are paid in March and December for every third employee.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.tax_total IS
  'Sum of tax in USD. Tax is 18 percent of gross pay.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.deductions_total IS
  'Sum of other deductions in USD. Deductions are 6 percent of gross pay.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_monthly.net_total IS
  'Sum of net pay in USD. Net is gross minus tax minus deductions.';

COMMENT ON VIEW payroll_demo.reporting.v_payroll_by_department IS
  'One row per department per month. Amounts are USD. Departments with fewer than 5 people paid that month are omitted.';

COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.pay_period IS
  'First day of the pay month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.department IS
  'Department name: Engineering, Sales, Finance, HR, Operations, or Marketing.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.headcount IS
  'Number of employees paid in this department for the month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.gross_total IS
  'Sum of gross pay in USD for this department and month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.net_total IS
  'Sum of net pay in USD for this department and month.';
COMMENT ON COLUMN payroll_demo.reporting.v_payroll_by_department.avg_gross IS
  'Average gross pay in USD per employee paid in this department and month.';

-- Paste the block below into the Genie agent's instructions. Add the SQL
-- under example SQL (question + statement). Do not attach payroll_demo.raw.

-- Instructions:
-- Only query payroll_demo.reporting.v_payroll_monthly and
-- payroll_demo.reporting.v_payroll_by_department. Never query payroll_demo.raw.
-- Amounts are USD. pay_period is the first day of the calendar month.
-- "Latest month" and "last month" mean the maximum pay_period, unless the
-- user names a specific month. Headcount is employees paid that month.
-- If a department is missing, it had fewer than 5 people paid that month.
-- Say that explicitly instead of inventing a row.

-- Example: What was gross payroll in the latest month?
-- SELECT pay_period, gross_total, net_total, headcount
-- FROM payroll_demo.reporting.v_payroll_monthly
-- WHERE pay_period = (SELECT MAX(pay_period) FROM payroll_demo.reporting.v_payroll_monthly);

-- Example: Which department had the highest gross pay in the latest month?
-- SELECT department, gross_total, net_total, headcount, avg_gross
-- FROM payroll_demo.reporting.v_payroll_by_department
-- WHERE pay_period = (SELECT MAX(pay_period) FROM payroll_demo.reporting.v_payroll_monthly)
-- ORDER BY gross_total DESC
-- LIMIT 1;

-- Example: How has headcount changed over the last 12 months?
-- SELECT pay_period, headcount, gross_total, net_total
-- FROM payroll_demo.reporting.v_payroll_monthly
-- ORDER BY pay_period;

-- Example: Show bonus totals by month
-- SELECT pay_period, bonus_total
-- FROM payroll_demo.reporting.v_payroll_monthly
-- ORDER BY pay_period;
