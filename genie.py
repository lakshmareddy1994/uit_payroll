"""Proxy Databricks Genie as the signed-in user.

The chat UI calls this app. This module calls the Genie Conversation API
with that user's token (x-forwarded-access-token on Databricks Apps, the
Databricks CLI user locally). Genie then runs SQL as the same user, so
Unity Catalog grants stay in force. The browser never sees the token.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from databricks.sdk.core import Config
from fastapi import HTTPException, Request

GENIE_SPACE_ID = "GENIE_SPACE_ID"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}
_MAX_ROWS = 200
_TIMEOUT_SECONDS = 60


def configured() -> bool:
    return bool(os.getenv(GENIE_SPACE_ID, "").strip())


def ask(request: Request, content: str, conversation_id: str | None) -> dict:
    question = (content or "").strip()
    if not question:
        raise HTTPException(400, "Enter a question")
    if len(question) > 8000:
        raise HTTPException(400, "Question is too long")

    space_id = _space_id()
    host, authorization = _authorization(request)
    thread_id = (conversation_id or "").strip() or None
    if thread_id:
        _check_id(thread_id, "conversation_id")
        payload = _api(
            "POST",
            f"/api/2.0/genie/spaces/{urllib.parse.quote(space_id)}/conversations/{thread_id}/messages",
            host,
            authorization,
            {"content": question},
        )
    else:
        payload = _api(
            "POST",
            f"/api/2.0/genie/spaces/{urllib.parse.quote(space_id)}/start-conversation",
            host,
            authorization,
            {"content": question},
        )
        thread_id, _ = _ids(payload)

    found_conversation, message_id = _ids(payload, thread_id)
    if not found_conversation or not message_id:
        raise HTTPException(502, "Genie did not return a conversation")
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    return {
        "conversation_id": found_conversation,
        "message_id": message_id,
        "status": (message or {}).get("status") or "SUBMITTED",
    }


def message_view(request: Request, conversation_id: str, message_id: str) -> dict:
    _check_id(conversation_id, "conversation_id")
    _check_id(message_id, "message_id")
    space_id = _space_id()
    host, authorization = _authorization(request)
    payload = _api(
        "GET",
        "/api/2.0/genie/spaces/"
        f"{urllib.parse.quote(space_id)}/conversations/{conversation_id}/messages/{message_id}",
        host,
        authorization,
    )
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    return present_message(
        message,
        host=host,
        authorization=authorization,
        space_id=space_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )


def present_message(
    message: dict,
    *,
    host: str,
    authorization: str,
    space_id: str,
    conversation_id: str,
    message_id: str,
) -> dict:
    """Turn a Genie message into the fields the chat renders."""
    status = (message or {}).get("status") or "SUBMITTED"
    answer, follow_up, sql, sql_title, sql_description, attachment_id, suggestions = _attachments(
        (message or {}).get("attachments") or []
    )
    error = _error_text(message)

    columns: list[str] = []
    rows: list[dict] = []
    row_count = None
    truncated = False
    result_note = None

    # Fetch rows only once Genie has finished the query. If the warehouse is
    # still running, report EXECUTING_QUERY so the chat keeps polling.
    # External cloud links are ignored inside rows_from_statement.
    if attachment_id and status in {"COMPLETED", "QUERY_RESULT_EXPIRED"}:
        try:
            result = _api(
                "GET",
                "/api/2.0/genie/spaces/"
                f"{urllib.parse.quote(space_id)}/conversations/{conversation_id}"
                f"/messages/{message_id}/attachments/{urllib.parse.quote(attachment_id)}/query-result",
                host,
                authorization,
            )
        except HTTPException as exc:
            result_note = str(exc.detail)
            result = None
        if result is not None:
            statement = result.get("statement_response") or {}
            state = ((statement.get("status") or {}).get("state") or "").upper()
            if state in {"PENDING", "RUNNING"}:
                status = "EXECUTING_QUERY"
            else:
                columns, rows, row_count, truncated, inline_note = rows_from_statement(statement)
                result_note = inline_note or result_note
                if state == "FAILED":
                    statement_error = ((statement.get("status") or {}).get("error") or {}).get("message")
                    error = error or statement_error or "The SQL query failed"

    if status == "FAILED" and not error:
        error = "Genie could not answer that question"
    if status == "CANCELLED" and not error:
        error = "The question was cancelled"
    if status == "QUERY_RESULT_EXPIRED" and not rows and not result_note:
        result_note = "The query result expired. Ask the question again."
    if status == "COMPLETED" and not answer and not follow_up and not error and not rows and not result_note:
        answer = "Genie finished without a written answer."

    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "status": status,
        "pending": status not in _TERMINAL,
        "answer": answer,
        "follow_up": follow_up,
        "sql": sql,
        "sql_title": sql_title,
        "sql_description": sql_description,
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "truncated": truncated,
        "result_note": result_note,
        "suggested_questions": suggestions,
        "error": error,
    }


def rows_from_statement(statement: dict) -> tuple[list[str], list[dict], int | None, bool, str | None]:
    """Read inline statement rows. External cloud links are not followed.

    Databricks Apps often cannot reach those short-lived storage URLs, and the
    URLs carry temporary credentials that should not be sent to the browser.
    """
    manifest = statement.get("manifest") or {}
    schema = manifest.get("schema") or {}
    columns = [col.get("name") or f"col_{i}" for i, col in enumerate(schema.get("columns") or [])]
    result = statement.get("result") or {}
    data_array = result.get("data_array")
    note = None
    if data_array is None:
        if result.get("external_links"):
            note = "Genie ran the query, but the rows are too large to show here. Ask for a smaller result."
        return columns, [], manifest.get("total_row_count"), bool(manifest.get("truncated")), note

    rows = []
    for record in data_array[:_MAX_ROWS]:
        values = list(record or [])
        if not columns:
            columns = [f"col_{i}" for i in range(len(values))]
        rows.append(
            {columns[i] if i < len(columns) else f"col_{i}": values[i] for i in range(len(values))}
        )
    truncated = bool(manifest.get("truncated")) or len(data_array) > _MAX_ROWS
    return columns, rows, manifest.get("total_row_count"), truncated, None


def _attachments(attachments: list) -> tuple:
    answer = None
    follow_up = None
    sql = None
    sql_title = None
    sql_description = None
    attachment_id = None
    suggestions: list[str] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        text = attachment.get("text") or {}
        content = text.get("content")
        if content:
            if text.get("purpose") == "FOLLOW_UP_QUESTION":
                follow_up = content
            elif text.get("purpose") == "TEXT_ATTACHMENT_PURPOSE_ANSWER" or answer is None:
                answer = content
        query = attachment.get("query") or {}
        if query.get("query") and sql is None:
            sql = query.get("query")
            sql_title = query.get("title")
            sql_description = query.get("description")
            attachment_id = attachment.get("attachment_id") or query.get("attachment_id") or query.get("id")
        for question in (attachment.get("suggested_questions") or {}).get("questions") or []:
            if question and question not in suggestions:
                suggestions.append(question)
    return answer, follow_up, sql, sql_title, sql_description, attachment_id, suggestions


def _error_text(message: dict | None) -> str | None:
    error = (message or {}).get("error") or {}
    if isinstance(error, dict):
        text = error.get("error") or error.get("message")
        return str(text) if text else None
    return str(error) if error else None


def _ids(payload: dict, conversation_id: str | None = None) -> tuple[str | None, str | None]:
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    conversation = payload.get("conversation") if isinstance(payload.get("conversation"), dict) else {}
    found_conversation = (
        payload.get("conversation_id")
        or (message or {}).get("conversation_id")
        or conversation.get("conversation_id")
        or conversation.get("id")
        or conversation_id
    )
    found_message = payload.get("message_id") or (message or {}).get("message_id") or (message or {}).get("id")
    return found_conversation, found_message


def _space_id() -> str:
    space_id = os.getenv(GENIE_SPACE_ID, "").strip()
    if not space_id:
        raise HTTPException(
            500,
            "GENIE_SPACE_ID is not set. Create a Genie agent, then set this variable. See README.",
        )
    _check_id(space_id, "GENIE_SPACE_ID")
    return space_id


def _check_id(value: str, name: str) -> None:
    if not _ID.fullmatch(value or ""):
        raise HTTPException(400, f"Invalid {name}")


def _authorization(request: Request) -> tuple[str, str]:
    """Return (host, Authorization header) for the signed-in user.

    Matches the SQL connector: the forwarded app token when Databricks Apps
    supplies one, otherwise the local Databricks CLI user.
    """
    token = (request.headers.get("x-forwarded-access-token") or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token:
        host = os.getenv("DATABRICKS_HOST")
        if not host:
            raise HTTPException(500, "DATABRICKS_HOST is not set")
        return host, f"Bearer {token}"
    if os.getenv("DATABRICKS_CLIENT_ID") or os.getenv("DATABRICKS_CLIENT_SECRET"):
        raise HTTPException(401, "User access token was not forwarded")
    try:
        cfg = Config()
    except Exception as exc:
        raise HTTPException(500, f"Databricks CLI auth is not configured: {exc}") from exc
    if not cfg.host:
        raise HTTPException(500, "Databricks host is not configured")
    try:
        headers = cfg.authenticate()
    except Exception as exc:
        raise HTTPException(500, f"Databricks CLI auth failed: {exc}") from exc
    authorization = headers.get("Authorization") or headers.get("authorization")
    if not authorization:
        raise HTTPException(500, "Databricks CLI did not return an access token")
    return cfg.host, authorization


def _hostname(host: str) -> str:
    return host.removeprefix("https://").removeprefix("http://").strip("/")


def _api(method: str, path: str, host: str, authorization: str, body: dict | None = None) -> dict:
    url = f"https://{_hostname(host)}{path}"
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": authorization, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        detail = raw
        try:
            parsed = json.loads(raw)
            detail = parsed.get("message") or parsed.get("detail") or raw
        except json.JSONDecodeError:
            pass
        detail = str(detail).strip() or f"HTTP {exc.code}"
        if len(detail) > 500:
            detail = detail[:500] + "..."
        if exc.code == 403:
            detail += (
                " Confirm the app scopes include genie and sql, restart the app, "
                "and approve the new consent prompt."
            )
        if exc.code == 401:
            detail += " Open the app again and approve access."
        raise HTTPException(exc.code if 400 <= exc.code < 600 else 502, f"Genie API failed: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"Genie API unreachable: {exc.reason}") from exc
