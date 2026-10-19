# Catalog Dashboard (FastAPI + React on Databricks Apps, deployed from Git)

## Local run
pip install -r requirements.txt && python app.py     # API on :8000
npm install && npm run dev                           # UI on :5173 (proxies /api)

## Local production-like check
npm run build && python app.py                       # http://localhost:8000

## Deploy
git push origin main
databricks apps deploy catalog-dashboard --json '{"git_source": {"branch": "main"}}'
