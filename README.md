# Catalog Dashboard (FastAPI + React on Databricks Apps, deployed from Git)

## Local run
pip install -r requirements.txt && python app.py     # API on :8000
npm install && npm run dev                           # UI on :5173 (proxies /api)

## Local production-like check
npm run build && python app.py                       # http://localhost:8000

## Deploy
git push origin main
databricks apps deploy catalog-dashboard --json '{"git_source": {"branch": "main"}}'

Queries run as the signed-in user. Set the app's user-authorization scope once
(read-only SQL). This is an app setting, not a field in app.yaml:

databricks apps create-update catalog-dashboard --json '{"update_mask": "user_api_scopes", "app": {"user_api_scopes": ["sql:restricted-query"]}}'

Then run sql/02_grants.sql as a catalog admin. Add each viewer to `payroll-viewers`
and grant that group Can use on the SQL warehouse. On first open, Databricks asks
the user to allow the app to run SQL as them.
