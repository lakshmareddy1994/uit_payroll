-- =====================================================================
-- Access setup. Run as the catalog owner/admin.
--
-- Dashboard queries run as the signed-in user, not the app service principal.
--
-- The owner of the catalog and the SQL warehouse already has full access.
-- Do not GRANT to that owner. GRANT is only for someone else who will open
-- the app and does not own these objects.
-- =====================================================================

-- A) Take reporting access away from the app service principal.
--    The owner's own access is unchanged.
REVOKE USE CATALOG ON CATALOG payroll_demo           FROM 'app-58y9i8 catalog-dashboard';
REVOKE USE SCHEMA  ON SCHEMA  payroll_demo.reporting FROM 'app-58y9i8 catalog-dashboard';
REVOKE SELECT      ON SCHEMA  payroll_demo.reporting FROM 'app-58y9i8 catalog-dashboard';

-- B) Another person, later. Replace the email. Skip this while only the owner uses the app.
-- GRANT USE CATALOG ON CATALOG payroll_demo TO `someone@company.com`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA payroll_demo.reporting TO `someone@company.com`;
-- GRANT USAGE ON WAREHOUSE <WAREHOUSE_NAME> TO `someone@company.com`;

-- C) Verify. The app service principal must not appear on either schema.
SHOW GRANTS ON SCHEMA payroll_demo.reporting;
SHOW GRANTS ON SCHEMA payroll_demo.raw;
