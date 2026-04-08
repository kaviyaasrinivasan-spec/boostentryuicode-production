// src/pages/PodMonitoring.jsx
// POD Upload Monitoring — shows each uploaded PDF with its processing status

import { useEffect, useState, useCallback } from "react";
import api from "../api/axios";

// ── helpers ───────────────────────────────────────────────────────────────────
const getLocalDate = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
};

const fmtDateTime = (ts) => {
    if (!ts) return "—";
    const d = new Date(ts);
    if (isNaN(d)) return ts;
    return d.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });
};

// ── Status badge ───────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
    const s = (status || "").toLowerCase().trim();

    if (s === "completed") {
        return (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
                Completed
            </span>
        );
    }
    if (s === "in progress" || s === "inprogress") {
        return (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700 border border-yellow-200">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 inline-block animate-pulse"></span>
                In Progress
            </span>
        );
    }
    if (s === "duplicate" || s === "already existed") {
        return (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-700 border border-orange-200">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 inline-block"></span>
                {s === "already existed" ? "Already Existed" : "Duplicate"}
            </span>
        );
    }
    if (s === "failed" || s === "error") {
        return (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block"></span>
                Failed
            </span>
        );
    }
    // default / queued / uploaded
    return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-200">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block"></span>
            {status || "—"}
        </span>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function PodMonitoring() {
    const today = getLocalDate(new Date());

    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(false);
    const [fromDate, setFromDate] = useState(today);
    const [toDate, setToDate] = useState(today);
    const [filterStatus, setFilterStatus] = useState("");
    const [quickFilter, setQuickFilter] = useState("today");
    const [lastRefreshed, setLastRefreshed] = useState(null);

    // ── fetch data ───────────────────────────────────────────────────────────
    const fetchData = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const params = new URLSearchParams();
            if (fromDate) params.append("from_date", fromDate);
            if (toDate) params.append("to_date", toDate);
            if (filterStatus) params.append("status", filterStatus);

            const res = await api.get(`/api/pod-monitoring?${params.toString()}`);
            setRows(res.data?.data || []);
            setLastRefreshed(new Date());
        } catch (err) {
            console.error("POD Monitoring fetch error:", err);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [fromDate, toDate, filterStatus]);

    // initial load
    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // auto-refresh every 15 seconds (silent)
    useEffect(() => {
        const id = setInterval(() => fetchData(true), 15000);
        return () => clearInterval(id);
    }, [fetchData]);

    // ── quick filter ────────────────────────────────────────────────────────
    const handleQuickFilter = (value) => {
        setQuickFilter(value);
        const now = new Date();
        switch (value) {
            case "today": {
                const t = getLocalDate(now);
                setFromDate(t); setToDate(t); break;
            }
            case "yesterday": {
                const y = new Date(now); y.setDate(now.getDate() - 1);
                const d = getLocalDate(y);
                setFromDate(d); setToDate(d); break;
            }
            case "last7": {
                const s = new Date(now); s.setDate(now.getDate() - 7);
                setFromDate(getLocalDate(s)); setToDate(getLocalDate(now)); break;
            }
            case "thisMonth": {
                const s = new Date(now.getFullYear(), now.getMonth(), 1);
                setFromDate(getLocalDate(s)); setToDate(getLocalDate(now)); break;
            }
            case "last30": {
                const s = new Date(now); s.setDate(now.getDate() - 30);
                setFromDate(getLocalDate(s)); setToDate(getLocalDate(now)); break;
            }
            default:
                break;
        }
    };

    // ── counts ──────────────────────────────────────────────────────────────
    const counts = {
        total: rows.length,
        inProgress: rows.filter(r => ["in progress", "inprogress"].includes((r.status || "").toLowerCase())).length,
        completed: rows.filter(r => (r.status || "").toLowerCase() === "completed").length,
        failed: rows.filter(r => (r.status || "").toLowerCase() === "failed").length,
        alreadyExisted: rows.filter(r => ["duplicate", "already existed"].includes((r.status || "").toLowerCase())).length,
    };

    return (
        <div className="p-6 w-full overflow-hidden">
            {/* ── Page Title ─────────────────────────────────────────────── */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-semibold text-indigo-700">POD Upload Monitoring</h2>
                    <p className="text-sm text-gray-500 mt-0.5">
                        Track uploaded PDFs and their processing status
                    </p>
                </div>
                <button
                    onClick={() => fetchData()}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-200 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors disabled:opacity-50"
                >
                    <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh
                </button>
            </div>

            {/* ── Summary Cards ──────────────────────────────────────────── */}
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
                {[
                    { label: "Total", value: counts.total, color: "indigo", bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-100" },
                    { label: "In Progress", value: counts.inProgress, color: "yellow", bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-100" },
                    { label: "Completed", value: counts.completed, color: "green", bg: "bg-green-50", text: "text-green-700", border: "border-green-100" },
                    { label: "Failed", value: counts.failed, color: "red", bg: "bg-red-50", text: "text-red-700", border: "border-red-100" },
                    { label: "Already Existed", value: counts.alreadyExisted, color: "orange", bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-100" },
                ].map(c => (
                    <div key={c.label} className={`${c.bg} border ${c.border} rounded-xl p-4`}>
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{c.label}</p>
                        <p className={`text-3xl font-bold mt-1 ${c.text}`}>{c.value}</p>
                    </div>
                ))}
            </div>

            {/* ── Filters ────────────────────────────────────────────────── */}
            <div className="flex flex-wrap gap-4 mb-5 items-end">
                <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Quick Filter</label>
                    <select
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:border-indigo-400 outline-none"
                        value={quickFilter}
                        onChange={(e) => handleQuickFilter(e.target.value)}
                    >
                        <option value="today">Today</option>
                        <option value="yesterday">Yesterday</option>
                        <option value="last7">Last 7 Days</option>
                        <option value="thisMonth">This Month</option>
                        <option value="last30">Last 30 Days</option>
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">From Date</label>
                    <input
                        type="date"
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:border-indigo-400 outline-none"
                        value={fromDate}
                        onChange={(e) => { setFromDate(e.target.value); setQuickFilter(""); }}
                    />
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">To Date</label>
                    <input
                        type="date"
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:border-indigo-400 outline-none"
                        value={toDate}
                        onChange={(e) => { setToDate(e.target.value); setQuickFilter(""); }}
                    />
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
                    <select
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:border-indigo-400 outline-none"
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                    >
                        <option value="">All Status</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Completed">Completed</option>
                        <option value="Duplicate">Duplicate</option>
                        <option value="Failed">Failed</option>
                    </select>
                </div>
            </div>

            {/* last refreshed */}
            {lastRefreshed && (
                <p className="text-xs text-gray-400 mb-3">
                    Last refreshed: {lastRefreshed.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true })}
                    &nbsp;· Auto-refreshes every 15s
                </p>
            )}

            {/* ── Table ──────────────────────────────────────────────────── */}
            {loading ? (
                <p className="text-sm text-indigo-600 animate-pulse">Loading data...</p>
            ) : (
                <div className="overflow-x-auto overflow-y-auto max-h-[580px] bg-white shadow rounded-xl border border-gray-100" style={{ scrollbarWidth: "thin" }}>
                    <table className="w-full border-collapse text-sm">
                        <thead className="sticky top-0 z-10">
                            <tr className="bg-indigo-50 text-gray-700 text-left text-xs uppercase tracking-wide">
                                <th className="p-3 border-b font-semibold w-12">#</th>
                                <th className="p-3 border-b font-semibold w-40">DI No</th>
                                <th className="p-3 border-b font-semibold pl-40">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.length === 0 ? (
                                <tr>
                                    <td colSpan={3} className="text-center py-12 text-gray-400 italic text-sm">
                                        No POD records found for the selected date range.
                                    </td>
                                </tr>
                            ) : (
                                rows.map((row, idx) => (
                                    <tr key={row.id ?? idx} className="hover:bg-gray-50 border-b border-gray-50 transition-colors">
                                        <td className="p-3 text-gray-500 font-medium">{idx + 1}</td>
                                        <td className="p-3 text-gray-800 font-mono font-semibold">{row.di_no || "—"}</td>
                                        <td className="p-3 pl-40">
                                            <StatusBadge status={row.status} />
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
