-- =====================================================================
-- Access setup. Replace the placeholders, then run as the catalog owner/admin.
--
-- <APP_SP>  = your app's service principal. In the Databricks UI open
--             Compute -> Apps -> <your app> and copy the service principal's
--             application (client) ID. Keep the backticks.
-- =====================================================================

-- A) The APP: read-only access to the reporting schema ONLY.
--    (Views run with the owner's rights, so the app does NOT need access to `raw`.)
GRANT USE CATALOG ON CATALOG payroll_demo           TO 'app-58y9i8 catalog-dashboard';
GRANT USE SCHEMA  ON SCHEMA  payroll_demo.reporting TO 'app-58y9i8 catalog-dashboard';
GRANT SELECT      ON SCHEMA  payroll_demo.reporting TO 'app-58y9i8 catalog-dashboard';

-- B) Humans (optional, use groups, not individual users):
-- Payroll/HR team: full access to raw data
-- GRANT USE CATALOG ON CATALOG payroll_demo TO `hr-payroll-admins`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA payroll_demo.raw TO `hr-payroll-admins`;
-- Managers/analysts: dashboards only
-- GRANT USE CATALOG ON CATALOG payroll_demo TO `payroll-viewers`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA payroll_demo.reporting TO `payroll-viewers`;

-- C) Verify
SHOW GRANTS ON SCHEMA payroll_demo.reporting;
SHOW GRANTS ON SCHEMA payroll_demo.raw;   -- the app SP must NOT appear here
