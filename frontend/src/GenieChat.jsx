import { useRef, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";

const STARTERS = [
  "What was gross payroll in the latest month?",
  "Which department had the highest gross pay in the latest month?",
  "How has headcount changed over the last 12 months?",
  "Show bonus totals by month",
];

const STATUS_LABEL = {
  FETCHING_METADATA: "Genie is reading the tables…",
  FILTERING_CONTEXT: "Genie is choosing the right context…",
  ASKING_AI: "Genie is writing the answer…",
  SUBMITTED: "Genie received the question…",
  IN_PROGRESS: "Genie is working…",
  PENDING_WAREHOUSE: "Waiting for the SQL warehouse…",
  EXECUTING_QUERY: "Running the query…",
};

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return body;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function chartModel(columns, rows) {
  if (!columns || columns.length < 2 || rows.length < 2 || rows.length > 24) return null;
  const labelKey = columns[0];
  const valueKey = columns.slice(1).find((column) =>
    rows.every((row) => row[column] == null || row[column] === "" || !Number.isNaN(Number(row[column])))
  );
  if (!valueKey) return null;
  const data = rows.map((row) => ({
    label: row[labelKey] == null ? "" : String(row[labelKey]),
    value: row[valueKey] == null || row[valueKey] === "" ? 0 : Number(row[valueKey]),
  }));
  if (data.every((point) => Number.isNaN(point.value))) return null;
  return { labelKey, valueKey, data };
}

function ResultTable({ columns, rows }) {
  if (!columns?.length || !rows?.length) return null;
  return (
    <div className="result-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column}>{row[column] == null ? "" : String(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function GenieChat() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(null);
  const requestId = useRef(0);

  function reset() {
    requestId.current += 1;
    conversationId.current = null;
    setMessages([]);
    setBusy(false);
    setDraft("");
  }

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    const turn = requestId.current + 1;
    requestId.current = turn;
    setDraft("");
    setBusy(true);
    setMessages((current) => [
      ...current,
      { role: "user", text: question },
      { role: "genie", pending: true, status: "SUBMITTED" },
    ]);

    try {
      const started = await requestJson("/api/genie/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: question,
          conversation_id: conversationId.current,
        }),
      });
      if (requestId.current !== turn) return;
      conversationId.current = started.conversation_id;

      let delay = 1000;
      const deadline = Date.now() + 10 * 60 * 1000;
      let view = null;
      while (Date.now() < deadline) {
        view = await requestJson(
          `/api/genie/messages/${started.conversation_id}/${started.message_id}`,
        );
        if (requestId.current !== turn) return;
        if (!view.pending) break;
        setMessages((current) => {
          const next = current.slice();
          next[next.length - 1] = { role: "genie", pending: true, status: view.status };
          return next;
        });
        await sleep(delay);
        delay = Math.min(Math.round(delay * 1.4), 5000);
      }
      if (!view || view.pending) {
        throw new Error("Genie did not finish within 10 minutes. Try a narrower question.");
      }
      if (requestId.current !== turn) return;
      setMessages((current) => {
        const next = current.slice();
        next[next.length - 1] = { role: "genie", ...view };
        return next;
      });
    } catch (error) {
      if (requestId.current !== turn) return;
      setMessages((current) => {
        const next = current.slice();
        next[next.length - 1] = { role: "genie", error: error.message };
        return next;
      });
    } finally {
      if (requestId.current === turn) setBusy(false);
    }
  }

  const last = messages[messages.length - 1];
  const suggestions = last?.role === "genie" && !last.pending ? last.suggested_questions || [] : [];
  const showStarters = messages.length === 0;

  return (
    <section className="card chat">
      <div className="chat-head">
        <div>
          <h2>Ask payroll data</h2>
          <div className="sub">Questions run through the same Genie agent as Databricks. Follow-ups stay in this chat.</div>
        </div>
        <button type="button" className="ghost" onClick={reset} disabled={messages.length === 0 && !busy}>
          New chat
        </button>
      </div>

      <div className="thread" aria-live="polite">
        {showStarters && (
          <div className="chips">
            {STARTERS.map((question) => (
              <button key={question} type="button" className="chip" onClick={() => send(question)}>
                {question}
              </button>
            ))}
          </div>
        )}
        {messages.map((message, index) => (
          <article key={index} className={`bubble ${message.role}`}>
            {message.role === "user" && <p>{message.text}</p>}
            {message.role === "genie" && message.pending && (
              <p className="pending">{STATUS_LABEL[message.status] || "Genie is working…"}</p>
            )}
            {message.role === "genie" && !message.pending && (
              <>
                {message.error && <p className="bubble-error">{message.error}</p>}
                {message.answer && <p>{message.answer}</p>}
                {message.follow_up && <p>{message.follow_up}</p>}
                {message.result_note && <p className="sub">{message.result_note}</p>}
                {message.sql && (
                  <details>
                    <summary>{message.sql_title || "SQL Genie ran"}</summary>
                    {message.sql_description && <p className="sub">{message.sql_description}</p>}
                    <pre className="sql">{message.sql}</pre>
                  </details>
                )}
                <ResultChart columns={message.columns} rows={message.rows} />
                <ResultTable columns={message.columns} rows={message.rows} />
                {message.truncated && (
                  <p className="sub">
                    {message.row_count != null
                      ? `Result has ${message.row_count} rows. The table above is truncated.`
                      : "The table above is truncated."}
                  </p>
                )}
              </>
            )}
          </article>
        ))}
      </div>

      {suggestions.length > 0 && (
        <div className="chips">
          {suggestions.map((question) => (
            <button key={question} type="button" className="chip" disabled={busy} onClick={() => send(question)}>
              {question}
            </button>
          ))}
        </div>
      )}

      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about payroll, headcount, or departments"
          aria-label="Question for Genie"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
    </section>
  );
}

function ResultChart({ columns, rows }) {
  const model = chartModel(columns, rows);
  if (!model) return null;
  return (
    <div className="chart result-chart">
      <ResponsiveContainer>
        <BarChart data={model.data}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="label" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="value" name={model.valueKey} fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
