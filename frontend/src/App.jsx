import { useEffect, useState } from "react";
import GenieChat from "./GenieChat.jsx";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${r.status} on ${url}`);
  }
  return r.json();
}

const money = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const compact = (n) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
const month = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en", { month: "short", year: "2-digit" });

function Kpi({ label, value, change }) {
  const up = change != null && change >= 0;
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      <div className={`delta ${change == null ? "" : up ? "up" : "down"}`}>
        {change == null ? "–" : `${up ? "▲" : "▼"} ${Math.abs(change)}% vs prev. month`}
      </div>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [monthly, setMonthly] = useState([]);
  const [depts, setDepts] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    getJson("/api/health").then(setHealth).catch((e) => setError(e.message));
    Promise.all([
      getJson("/api/payroll/summary"),
      getJson("/api/payroll/monthly"),
      getJson("/api/payroll/by-department"),
    ])
      .then(([s, m, d]) => {
        setSummary(s);
        setMonthly(m.rows.map((r) => ({ ...r, label: month(r.pay_period) })));
        setDepts(d.rows);
      })
      .catch((e) => setError(e.message));
  }, []);

  const m = summary?.metrics;

  return (
    <div className="page">
      <header>
        <div>
          <h1>Payroll Dashboard</h1>
          <div className="sub">
            {summary ? `Latest pay period: ${month(summary.period)}` : "Loading…"} · dummy data, USD
          </div>
        </div>
        <span className="badge">{health ? "● API healthy" : "○ API checking"}</span>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      {m && (
        <div className="kpis">
          <Kpi label="Employees paid" value={m.headcount.value} change={m.headcount.change_pct} />
          <Kpi label="Gross payroll" value={money(m.gross_total.value)} change={m.gross_total.change_pct} />
          <Kpi label="Net payroll" value={money(m.net_total.value)} change={m.net_total.change_pct} />
          <Kpi label="Bonuses" value={money(m.bonus_total.value)} change={m.bonus_total.change_pct} />
        </div>
      )}

      <div className="charts">
        <div className="card">
          <h2>Monthly payroll trend</h2>
          <div className="chart">
            <ResponsiveContainer>
              <LineChart data={monthly}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="label" />
                <YAxis tickFormatter={compact} />
                <Tooltip formatter={(v) => money(v)} />
                <Legend />
                <Line type="monotone" dataKey="gross_total" name="Gross" stroke="#2563eb" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="net_total" name="Net" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h2>Gross payroll by department (latest month)</h2>
          <div className="chart">
            <ResponsiveContainer>
              <BarChart data={depts}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="department" />
                <YAxis tickFormatter={compact} />
                <Tooltip formatter={(v) => money(v)} />
                <Bar dataKey="gross_total" name="Gross" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <GenieChat />

      <div className="card">
        <h2>Department breakdown</h2>
        <table>
          <thead>
            <tr><th>Department</th><th>Headcount</th><th>Gross</th><th>Net</th><th>Avg gross / person</th></tr>
          </thead>
          <tbody>
            {depts.map((d) => (
              <tr key={d.department}>
                <td>{d.department}</td><td>{d.headcount}</td>
                <td>{money(d.gross_total)}</td><td>{money(d.net_total)}</td><td>{money(d.avg_gross)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
