import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import uvicorn
from databricks import sql as databricks_sql
from databricks.sdk.core import Config
from databricks.sql.exc import Error as DatabricksSqlError
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
STATIC_DIR = BASE_DIR / "static"

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")
CATALOG = os.getenv("CATALOG", "payroll_demo")
SCHEMA = os.getenv("SCHEMA", "reporting")  # the app only reads the aggregated schema

app = FastAPI(title="Payroll Dashboard")

def _hostname(host: str) -> str:
    return host.removeprefix("https://").removeprefix("http://").strip("/")


def connect(request: Request):
    """Open a SQL connector session as the signed-in user.

    Databricks Apps forwards that user's token in x-forwarded-access-token.
    Passing it as access_token keeps the app service principal from being used.
    Locally, with no app credentials in the environment, this uses the CLI user.
    """
    if not WAREHOUSE_ID:
        raise HTTPException(500, "DATABRICKS_WAREHOUSE_ID is not set")
    http_path = f"/sql/1.0/warehouses/{WAREHOUSE_ID}"
    token = request.headers.get("x-forwarded-access-token")
    if token:
        host = os.getenv("DATABRICKS_HOST")
        if not host:
            raise HTTPException(500, "DATABRICKS_HOST is not set")
        return databricks_sql.connect(
            server_hostname=_hostname(host),
            http_path=http_path,
            access_token=token,
        )
    if os.getenv("DATABRICKS_CLIENT_ID") or os.getenv("DATABRICKS_CLIENT_SECRET"):
        raise HTTPException(401, "User access token was not forwarded")
    try:
        cfg = Config()
    except Exception as exc:
        raise HTTPException(500, f"Databricks CLI auth is not configured: {exc}") from exc
    if not cfg.host:
        raise HTTPException(500, "Databricks host is not configured")
    return databricks_sql.connect(
        server_hostname=_hostname(cfg.host),
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
    )


def tbl(name: str) -> str:
    return f"`{CATALOG}`.`{SCHEMA}`.`{name}`"


def _json_value(value):
    # The connector returns Decimal and date objects. The dashboard expects JSON numbers and YYYY-MM-DD.
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if type(value).__module__.startswith("numpy"):
        return _json_value(value.item())
    return value


def run_query(request: Request, statement: str) -> list[dict]:
    try:
        with connect(request) as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)
                columns = [col[0] for col in (cursor.description or [])]
                fetched = cursor.fetchall()
    except DatabricksSqlError as exc:
        raise HTTPException(500, f"Query failed: {exc}") from exc
    return [
        {name: _json_value(value) for name, value in zip(columns, row)}
        for row in fetched
    ]


# ---------- API ----------
api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok", "service": "payroll-dashboard"}


@api.get("/payroll/summary")
def payroll_summary(request: Request):
    """KPIs for the latest pay period, with % change vs the previous period."""
    rows = run_query(
        request,
        f"SELECT pay_period, headcount, gross_total, bonus_total, net_total "
        f"FROM {tbl('v_payroll_monthly')} ORDER BY pay_period DESC LIMIT 2",
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
def payroll_monthly(request: Request):
    return {
        "rows": run_query(
            request,
            f"SELECT pay_period, headcount, gross_total, bonus_total, tax_total, net_total "
            f"FROM {tbl('v_payroll_monthly')} ORDER BY pay_period",
        )
    }


@api.get("/payroll/by-department")
def payroll_by_department(request: Request):
    """Department breakdown for the latest pay period."""
    return {
        "rows": run_query(
            request,
            f"SELECT department, headcount, gross_total, net_total, avg_gross "
            f"FROM {tbl('v_payroll_by_department')} "
            f"WHERE pay_period = (SELECT max(pay_period) FROM {tbl('v_payroll_monthly')}) "
            f"ORDER BY gross_total DESC",
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
