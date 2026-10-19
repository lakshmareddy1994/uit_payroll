import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv 
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
STATIC_DIR = BASE_DIR / "static"

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")
CATALOG = os.getenv("CATALOG", "payroll_demo")
SCHEMA = os.getenv("SCHEMA", "reporting")  # the app only reads the aggregated schema

app = FastAPI(title="Payroll Dashboard")
_client = None

FLOAT_TYPES = {"DECIMAL", "DOUBLE", "FLOAT"}
INT_TYPES = {"BYTE", "SHORT", "INT", "LONG"}


def get_client() -> WorkspaceClient:
    """In Databricks Apps this uses the app's service principal;
    locally it uses your CLI profile (DATABRICKS_CONFIG_PROFILE)."""
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def tbl(name: str) -> str:
    return f"`{CATALOG}`.`{SCHEMA}`.`{name}`"


def _convert(value, col):
    # The Statement API returns every value as a string, so convert by column type.
    if value is None:
        return None
    t = getattr(col.type_name, "value", str(col.type_name)) if col.type_name else "STRING"
    if t in FLOAT_TYPES:
        return float(value)
    if t in INT_TYPES:
        return int(value)
    return value


def run_query(sql: str) -> list[dict]:
    if not WAREHOUSE_ID:
        raise HTTPException(500, "DATABRICKS_WAREHOUSE_ID is not set")
    resp = get_client().statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=sql, wait_timeout="30s"
    )
    if resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status.error else str(resp.status.state)
        raise HTTPException(500, f"Query failed: {msg}")
    cols = resp.manifest.schema.columns
    rows = (resp.result.data_array if resp.result else None) or []
    return [{c.name: _convert(v, c) for c, v in zip(cols, r)} for r in rows]


# ---------- API ----------
api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok", "service": "payroll-dashboard"}


@api.get("/payroll/summary")
def payroll_summary():
    """KPIs for the latest pay period, with % change vs the previous period."""
    rows = run_query(
        f"SELECT pay_period, headcount, gross_total, bonus_total, net_total "
        f"FROM {tbl('v_payroll_monthly')} ORDER BY pay_period DESC LIMIT 2"
    )
    if not rows:
        raise HTTPException(404, "No payroll data found. Did you run sql/01_setup_payroll_demo.sql?")
    cur, prev = rows[0], (rows[1] if len(rows) > 1 else None)

    def metric(key):
        change = None
        if prev and prev[key]:
            change = round((cur[key] - prev[key]) / prev[key] * 100, 1)
        return {"value": cur[key], "change_pct": change}

    return {
        "period": cur["pay_period"],
        "metrics": {k: metric(k) for k in ("headcount", "gross_total", "bonus_total", "net_total")},
    }


@api.get("/payroll/monthly")
def payroll_monthly():
    return {
        "rows": run_query(
            f"SELECT pay_period, headcount, gross_total, bonus_total, tax_total, net_total "
            f"FROM {tbl('v_payroll_monthly')} ORDER BY pay_period"
        )
    }


@api.get("/payroll/by-department")
def payroll_by_department():
    """Department breakdown for the latest pay period."""
    return {
        "rows": run_query(
            f"SELECT department, headcount, gross_total, net_total, avg_gross "
            f"FROM {tbl('v_payroll_by_department')} "
            f"WHERE pay_period = (SELECT max(pay_period) FROM {tbl('v_payroll_monthly')}) "
            f"ORDER BY gross_total DESC"
        )
    }


app.include_router(api)

# ---------- Serve React build ----------
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend not built yet. Run: npm run build"}


if __name__ == "__main__":
    port = int(os.getenv("DATABRICKS_APP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
