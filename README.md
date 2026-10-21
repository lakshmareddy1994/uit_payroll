# Catalog Dashboard (FastAPI + React on Databricks Apps, deployed from Git)

## Local run
pip install -r requirements.txt && python app.py     # API on :8000
npm install && npm run dev                           # UI on :5173 (proxies /api)

## Local production-like check
npm run build && python app.py                       # http://localhost:8000

## Deploy
git push origin main
databricks apps deploy catalog-dashboard --json '{"git_source": {"branch": "main"}}'

Queries and the Genie chat run as the signed-in user. The SQL connector needs
the `sql` scope. `sql:restricted-query` is not enough and the warehouse call
fails with "Error during request to server". Genie needs the `genie` scope.
Set both once (this replaces the whole scope list; it is an app setting, not
a field in app.yaml):

databricks apps create-update catalog-dashboard --json '{"update_mask": "user_api_scopes", "app": {"user_api_scopes": ["sql", "genie"]}}'

Restart the app after changing the scope. On the next open, Databricks asks
the user to allow the app to run SQL as them. A token from before that consent
does not include `sql`.

Then run section A of sql/02_grants.sql as a catalog admin. The owner of the
catalog and warehouse already has access, so no GRANT is required for that user.
Grant another person only when someone who does not own those objects should
open the app.

## Genie chat

The chat on the dashboard calls the Genie agent in this workspace. The agent
is not stored in this repo. Finish the workspace steps below before expecting
answers. Until `GENIE_SPACE_ID` is set, the dashboard still loads and the chat
returns a clear error.

1. Run `sql/03_genie_comments.sql` in the SQL editor after `sql/01_setup_payroll_demo.sql`.
2. In Databricks, create a Genie agent. Add only these tables:
   - `payroll_demo.reporting.v_payroll_monthly`
   - `payroll_demo.reporting.v_payroll_by_department`
   Use the same SQL warehouse as `DATABRICKS_WAREHOUSE_ID`. Paste instructions
   that say: amounts are USD; `pay_period` is the first day of the month;
   "latest month" means `max(pay_period)`; do not query `payroll_demo.raw`;
   a missing department means that group had fewer than 5 people.
   Add a few example question/SQL pairs and benchmark questions, then ask
   those questions in the Databricks Genie page until the SQL looks right.
3. Copy the space ID from the agent Settings tab.
4. Local: add `GENIE_SPACE_ID=<that id>` to `.env` (this file is gitignored).
   `python app.py` uses your Databricks CLI login. `npm run dev` serves the UI.
5. Deployed app: in the app's Resources, add the Genie agent with key
   `genie-space` and permission **Can run**. Uncomment `GENIE_SPACE_ID` in
   `app.yaml`. Share the agent with anyone else who will open the app
   (Can run). They also need the grants in section B of `sql/02_grants.sql`.
   Set the scopes command above, restart the app, and approve the new consent
   prompt. A token from before that consent cannot call Genie.

Each question is `POST /api/genie/ask`, then the UI polls
`GET /api/genie/messages/{conversation_id}/{message_id}` until Genie finishes.
Follow-up questions send the same `conversation_id`. New chat starts a new one.
