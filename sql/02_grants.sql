-- =====================================================================
-- Access setup. Run as the catalog owner/admin after replacing placeholders.
--
-- Dashboard queries run as the signed-in user, not the app service principal.
-- Put viewers in the `payroll-viewers` group (or replace that name).
-- Each member also needs Can use on the app.
-- Views run with the owner's rights, so this group does not get `raw`.
-- =====================================================================

-- A) Take reporting access away from the app service principal.
REVOKE USE CATALOG ON CATALOG payroll_demo           FROM 'app-58y9i8 catalog-dashboard';
REVOKE USE SCHEMA  ON SCHEMA  payroll_demo.reporting FROM 'app-58y9i8 catalog-dashboard';
REVOKE SELECT      ON SCHEMA  payroll_demo.reporting FROM 'app-58y9i8 catalog-dashboard';

-- B) Viewers: aggregated reporting schema only.
GRANT USE CATALOG ON CATALOG payroll_demo TO `payroll-viewers`;
GRANT USE SCHEMA, SELECT ON SCHEMA payroll_demo.reporting TO `payroll-viewers`;

-- C) The same people must be allowed to run SQL on the warehouse attached to the app.
--    Replace <WAREHOUSE_NAME> with that warehouse's name, then run this statement.
-- GRANT CAN USE ON WAREHOUSE <WAREHOUSE_NAME> TO `payroll-viewers`;

-- D) Payroll/HR team: raw data (optional; not required to open the dashboard)
-- GRANT USE CATALOG ON CATALOG payroll_demo TO `hr-payroll-admins`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA payroll_demo.raw TO `hr-payroll-admins`;

-- E) Verify. The app service principal must not appear on either schema.
SHOW GRANTS ON SCHEMA payroll_demo.reporting;
SHOW GRANTS ON SCHEMA payroll_demo.raw;
