# Catalog Dashboard (FastAPI + React on Databricks Apps, deployed from Git)

## Local run
pip install -r requirements.txt && python app.py     # API on :8000
npm install && npm run dev                           # UI on :5173 (proxies /api)

## Local production-like check
npm run build && python app.py                       # http://localhost:8000

## Deploy
git push origin main
databricks apps deploy catalog-dashboard --json '{"git_source": {"branch": "main"}}'

Queries run as the signed-in user through the SQL connector. That connector
needs the `sql` scope. `sql:restricted-query` is not enough and the warehouse
call fails with "Error during request to server". Set the scope once
(this is an app setting, not a field in app.yaml):

databricks apps create-update catalog-dashboard --json '{"update_mask": "user_api_scopes", "app": {"user_api_scopes": ["sql"]}}'

Restart the app after changing the scope. On the next open, Databricks asks
the user to allow the app to run SQL as them. A token from before that consent
does not include `sql`.

Then run section A of sql/02_grants.sql as a catalog admin. The owner of the
catalog and warehouse already has access, so no GRANT is required for that user.
Grant another person only when someone who does not own those objects should
open the app.
