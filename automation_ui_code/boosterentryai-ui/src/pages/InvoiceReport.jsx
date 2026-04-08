// src/pages/InvoiceReport.jsx
import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  CheckCircle,
  UserCheck,
  XCircle,
  Copy,
  Calendar,
  Building2,
  BarChart3,
  TrendingUp,
  Filter,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE || "";

/* ─── colour palette (light theme) ─── */
const COLORS = {
  total:         { bg: "from-indigo-500 to-indigo-600",   icon: "bg-indigo-100",   iconText: "text-indigo-600",  value: "text-indigo-700",  label: "text-indigo-600",  sub: "text-indigo-400",  border: "border-indigo-200",  card: "bg-indigo-50"  },
  completed:     { bg: "from-emerald-500 to-emerald-600", icon: "bg-emerald-100", iconText: "text-emerald-600", value: "text-emerald-700", label: "text-emerald-600", sub: "text-emerald-400", border: "border-emerald-200", card: "bg-emerald-50" },
  completed_ahr: { bg: "from-amber-500  to-amber-600",   icon: "bg-amber-100",   iconText: "text-amber-600",   value: "text-amber-700",   label: "text-amber-600",   sub: "text-amber-400",   border: "border-amber-200",   card: "bg-amber-50"   },
  failed:        { bg: "from-rose-500   to-rose-600",    icon: "bg-rose-100",    iconText: "text-rose-600",    value: "text-rose-700",    label: "text-rose-600",    sub: "text-rose-400",    border: "border-rose-200",    card: "bg-rose-50"    },
  duplicate:     { bg: "from-amber-100  to-amber-200",   icon: "bg-amber-100",   iconText: "text-amber-700",   value: "text-amber-800",   label: "text-amber-700",   sub: "text-amber-500",   border: "border-amber-200",   card: "bg-amber-50"   },
};

/* ─── bar width helper ─── */
const pct = (part, whole) => (whole > 0 ? Math.round((part / whole) * 100) : 0);

/* ─────────────────────────────────────────────────────────────────
   Stat Card  – white card with coloured top accent bar
───────────────────────────────────────────────────────────────── */
function StatCard({ label, value, icon: Icon, colorKey, sub }) {
  const c = COLORS[colorKey];
  return (
    <div
      className={`rounded-2xl bg-white border ${c.border} shadow-sm
                  overflow-hidden flex flex-col transition-shadow hover:shadow-md`}
    >
      {/* top accent bar */}
      <div className={`h-1.5 w-full bg-gradient-to-r ${c.bg}`} />
      <div className="p-5 flex flex-col gap-3">
        <div className="flex items-start justify-between">
          <div>
            <p className={`text-sm font-medium ${c.label}`}>{label}</p>
            <p className={`text-4xl font-bold ${c.value} mt-1`}>{value}</p>
          </div>
          <div className={`${c.icon} rounded-xl p-2.5`}>
            <Icon size={22} className={c.iconText} />
          </div>
        </div>
        {sub && <p className={`text-xs ${c.sub}`}>{sub}</p>}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Mini bar (branch table row distribution)
───────────────────────────────────────────────────────────────── */
function MiniBar({ completed, ahr, failed, duplicate, total }) {
  const cPct = pct(completed, total);
  const aPct = pct(ahr,       total);
  const fPct = pct(failed,    total);
  const dPct = pct(duplicate, total);
  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-gray-200 w-full">
      <div style={{ width: `${cPct}%` }} className="bg-emerald-500 transition-all" />
      <div style={{ width: `${aPct}%` }} className="bg-amber-400 transition-all"   />
      <div style={{ width: `${fPct}%` }} className="bg-rose-400 transition-all"    />
      <div style={{ width: `${dPct}%` }} className="bg-amber-200 transition-all"    />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   Trend bar chart – simple CSS stacked bars (light version)
───────────────────────────────────────────────────────────────── */
function TrendChart({ trend }) {
  if (!trend || trend.length === 0) return null;
  const maxTotal = Math.max(...trend.map((t) => t.total), 1);

  return (
    <div className="overflow-x-auto">
      <div className="flex items-end gap-3 min-w-max h-48 px-2 pt-4">
        {trend.map((t) => (
          <div key={t.date} className="flex flex-col items-center gap-1 group">
            <div
              className="relative w-10 flex flex-col-reverse rounded-t overflow-hidden cursor-pointer"
              style={{ height: `${Math.max(4, pct(t.total, maxTotal) * 1.6)}px` }}
              title={`${t.date}: Total ${t.total}`}
            >
              <div className="w-full bg-emerald-500 transition-all" style={{ height: `${pct(t.completed, t.total)}%` }}   />
              <div className="w-full bg-amber-400 transition-all"   style={{ height: `${pct(t.completed_ahr, t.total)}%` }} />
              <div className="w-full bg-rose-400 transition-all"    style={{ height: `${pct(t.failed, t.total)}%` }}       />
              <div className="w-full bg-amber-200 transition-all"   style={{ height: `${pct(t.duplicate, t.total)}%` }}     />
              {/* tooltip */}
              <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-10
                              hidden group-hover:flex flex-col items-start bg-gray-800
                              border border-gray-600 rounded-lg shadow-xl p-2 text-xs text-white
                              whitespace-nowrap gap-0.5 pointer-events-none">
                <span className="font-semibold text-gray-100">{t.date}</span>
                <span className="text-emerald-300">✔ Completed: {t.completed}</span>
                <span className="text-amber-300">👤 Human Review: {t.completed_ahr}</span>
                <span className="text-rose-300">✗ Failed: {t.failed}</span>
                <span className="text-amber-100">📋 Duplicate: {t.duplicate}</span>
                <span className="text-gray-300">Total: {t.total}</span>
              </div>
            </div>
            <span className="text-[10px] text-gray-400 -rotate-45 origin-top-left w-10 truncate">
              {t.date.slice(5)}
            </span>
          </div>
        ))}
      </div>
      {/* legend */}
      <div className="flex gap-5 mt-3 px-2 text-xs text-gray-500">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block"/> Completed</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-amber-400 inline-block"/>  With Human Review</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-rose-400 inline-block"/>   Failed</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-amber-200 inline-block"/>  Duplicate</span>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN PAGE
═══════════════════════════════════════════════════════════════ */
export default function InvoiceReport() {
  const [loading,    setLoading]    = useState(false);
  const [data,       setData]       = useState(null);
  const [branches,   setBranches]   = useState([]);
  const [error,      setError]      = useState("");

  const [clientId,  setClientId]  = useState("all");
  const [period,    setPeriod]    = useState("today");
  const [fromDate,  setFromDate]  = useState("");
  const [toDate,    setToDate]    = useState("");
  const [showTrend, setShowTrend] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/report/branches`)
      .then((r) => r.json())
      .then((j) => { if (j.status === "success") setBranches(j.data); })
      .catch(() => {});
  }, []);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ client_id: clientId, period });
      if (period === "custom") {
        if (fromDate) params.set("from_date", fromDate);
        if (toDate)   params.set("to_date",   toDate);
      }
      const res  = await fetch(`${API_BASE}/api/report/invoice-processing?${params}`);
      const json = await res.json();
      if (json.status === "success") setData(json.data);
      else setError(json.message || "Failed to load report");
    } catch {
      setError("Network error – could not reach server");
    } finally {
      setLoading(false);
    }
  }, [clientId, period, fromDate, toDate]);

  useEffect(() => { fetchReport(); }, []);

  const summary    = data?.summary  || { total: 0, completed: 0, completed_ahr: 0, failed: 0, duplicate: 0 };
  const branchRows = data?.branches || [];
  const trend      = data?.trend    || [];
  const filters    = data?.filters  || {};

  const periodLabel = {
    today:      "Today",
    yesterday:  "Yesterday",
    this_week:  "This Week",
    this_month: "This Month",
    custom:     filters.from_date ? `${filters.from_date} → ${filters.to_date || "now"}` : "Custom",
  }[period] || period;

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 px-4 md:px-8 py-6 space-y-6">

      {/* ── Page header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-100 border border-indigo-200 rounded-xl p-2.5">
            <BarChart3 size={24} className="text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Invoice Processing Report</h1>
            <p className="text-sm text-gray-500">Track invoice volumes and statuses by branch and date</p>
          </div>
        </div>

      </div>

      {/* ── Filter bar ── */}
      <div className="bg-white border border-gray-200 rounded-2xl p-4 flex flex-wrap gap-4 items-end shadow-sm">

        {/* Branch */}
        <div className="flex flex-col gap-1 min-w-[180px]">
          <label className="text-xs text-gray-500 font-medium flex items-center gap-1">
            <Building2 size={12} /> Branch
          </label>
          <select
            id="filter-branch"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700
                       focus:outline-none focus:border-indigo-500 transition cursor-pointer"
          >
            <option value="all">All Branches</option>
            {branches.map((b) => (
              <option key={b.client_id} value={b.client_id}>{b.client_name}</option>
            ))}
          </select>
        </div>

        {/* Period */}
        <div className="flex flex-col gap-1 min-w-[180px]">
          <label className="text-xs text-gray-500 font-medium flex items-center gap-1">
            <Calendar size={12} /> Date Range
          </label>
          <select
            id="filter-period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700
                       focus:outline-none focus:border-indigo-500 transition cursor-pointer"
          >
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="this_week">This Week</option>
            <option value="this_month">This Month</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>

        {/* Custom date pickers */}
        {period === "custom" && (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">From</label>
              <input
                id="filter-from-date"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700
                           focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">To</label>
              <input
                id="filter-to-date"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700
                           focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
          </>
        )}

        <button
          id="btn-apply-filters"
          onClick={fetchReport}
          disabled={loading}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50
                     text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-all shadow-sm self-end"
        >
          <Filter size={14} />
          Apply Filters
        </button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-600 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* ── Active filter badges ── */}
      {data && (
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="bg-indigo-50 border border-indigo-200 text-indigo-600 px-3 py-1 rounded-full font-medium">
            📅 {periodLabel}
          </span>
          <span className="bg-indigo-50 border border-indigo-200 text-indigo-600 px-3 py-1 rounded-full font-medium">
            🏢 {clientId === "all" ? "All Branches" : (branches.find(b => String(b.client_id) === String(clientId))?.client_name || clientId)}
          </span>
        </div>
      )}

      {/* ── 4 stat cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Total Invoices Processed"
          value={summary.total}
          icon={FileText}
          colorKey="total"
          sub="All invoices in the selected period"
        />
        <StatCard
          label="Completed (Auto)"
          value={summary.completed}
          icon={CheckCircle}
          colorKey="completed"
          sub="Processed fully by the system"
        />
        <StatCard
          label="Completed with Human Review"
          value={summary.completed_ahr}
          icon={UserCheck}
          colorKey="completed_ahr"
          sub="Required manual intervention"
        />
        <StatCard
          label="Failed"
          value={summary.failed}
          icon={XCircle}
          colorKey="failed"
          sub="Could not be processed"
        />
        <StatCard
          label="Duplicate"
          value={summary.duplicate}
          icon={Copy}
          colorKey="duplicate"
          sub="Invoices already existed"
        />
      </div>

      {/* ── Success rate ── */}
      {summary.total > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl px-5 py-4 flex flex-wrap gap-6 items-center shadow-sm">
          <div className="flex items-center gap-2">
            <TrendingUp size={18} className="text-indigo-500" />
            <span className="text-sm text-gray-700 font-medium">Success Rate</span>
          </div>
          <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden min-w-[120px]">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all"
              style={{ width: `${pct(summary.completed + summary.completed_ahr, summary.total)}%` }}
            />
          </div>
          <span className="text-indigo-700 font-bold text-lg">
            {pct(summary.completed + summary.completed_ahr, summary.total)}%
          </span>
          <span className="text-gray-400 text-sm">
            ({summary.completed + summary.completed_ahr} of {summary.total} invoices)
          </span>
        </div>
      )}

      {/* ── Trend chart ── */}
      {trend.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 size={18} className="text-indigo-500" />
              <h2 className="text-base font-semibold text-gray-800">Daily Trend</h2>
            </div>
            <button
              onClick={() => setShowTrend((v) => !v)}
              className="text-xs text-gray-400 hover:text-gray-600 transition"
            >
              {showTrend ? "Hide" : "Show"}
            </button>
          </div>
          {showTrend && <TrendChart trend={trend} />}
        </div>
      )}

      {/* ── Branch breakdown table ── */}
      {branchRows.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Building2 size={18} className="text-indigo-500" />
            <h2 className="text-base font-semibold text-gray-800">Branch Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs font-semibold uppercase tracking-wide text-gray-500 bg-gray-50 border-b border-gray-100">
                  <th className="text-left px-5 py-3">Branch</th>
                  <th className="text-right px-4 py-3">Total</th>
                  <th className="text-right px-4 py-3 text-emerald-600">Completed</th>
                  <th className="text-right px-4 py-3 text-amber-600">Human Review</th>
                  <th className="text-right px-4 py-3 text-rose-500">Failed</th>
                  <th className="text-right px-4 py-3 text-amber-700">Duplicate</th>
                  <th className="px-5 py-3 text-gray-500">Distribution</th>
                </tr>
              </thead>
              <tbody>
                {branchRows.map((b, i) => (
                  <tr
                    key={b.client_id || i}
                    className="border-b border-gray-50 hover:bg-indigo-50/40 transition-colors"
                  >
                    <td className="px-5 py-3 font-medium text-gray-800">{b.client_name}</td>
                    <td className="text-right px-4 py-3 text-indigo-600 font-semibold">{b.total}</td>
                    <td className="text-right px-4 py-3 text-emerald-600 font-semibold">{b.completed}</td>
                    <td className="text-right px-4 py-3 text-amber-600 font-semibold">{b.completed_ahr}</td>
                    <td className="text-right px-4 py-3 text-rose-500 font-semibold">{b.failed}</td>
                    <td className="text-right px-4 py-3 text-amber-700 font-semibold">{b.duplicate}</td>
                    <td className="px-5 py-3 min-w-[140px]">
                      <MiniBar completed={b.completed} ahr={b.completed_ahr} failed={b.failed} duplicate={b.duplicate} total={b.total} />
                      <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                        <span>{pct(b.completed, b.total)}%</span>
                        <span>{pct(b.completed_ahr, b.total)}%</span>
                        <span>{pct(b.failed, b.total)}%</span>
                        <span>{pct(b.duplicate, b.total)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {!loading && data && branchRows.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl p-12 flex flex-col items-center gap-3 text-gray-400 shadow-sm">
          <FileText size={40} className="opacity-30" />
          <p className="text-base font-medium text-gray-500">No invoices found for the selected filters</p>
          <p className="text-sm">Try changing the date range or branch</p>
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-gray-100 rounded-2xl border border-gray-200" />
          ))}
        </div>
      )}
    </div>
  );
}
