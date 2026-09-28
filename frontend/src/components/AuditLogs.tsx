"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Download,
  AlertTriangle,
  RefreshCw,
  AlertCircle,
  ChevronDown,
  Filter,
} from "lucide-react";

const API_BASE = "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────
type RawScan = {
  id: string;
  language: string | null;
  impersonation_risk_score: number;
  verdict: "genuine" | "suspicious" | "synthetic_clone";
  scanned_at: string;
};

type ScanItem = {
  id: string;
  time: string;
  language: string;
  risk: number;
  verdict: "AUTHENTIC" | "SUSPICIOUS" | "CLONED";
  action: string;
};

// ── Mock fallback ────────────────────────────────────────────────────────────
const MOCK_SCANS: ScanItem[] = [
  { id: "demo-1", time: "14:22:05", language: "Hindi", risk: 94, verdict: "CLONED", action: "Terminated" },
  { id: "demo-2", time: "14:15:30", language: "English", risk: 12, verdict: "AUTHENTIC", action: "Allowed" },
  { id: "demo-3", time: "13:50:11", language: "Telugu", risk: 45, verdict: "SUSPICIOUS", action: "Challenged" },
  { id: "demo-4", time: "12:05:40", language: "Tamil", risk: 8, verdict: "AUTHENTIC", action: "Allowed" },
  { id: "demo-5", time: "11:44:22", language: "Hindi", risk: 87, verdict: "CLONED", action: "Terminated" },
  { id: "demo-6", time: "10:30:00", language: "English", risk: 55, verdict: "SUSPICIOUS", action: "Challenged" },
];

// ── Helpers ──────────────────────────────────────────────────────────────────
function mapScan(raw: RawScan): ScanItem {
  const verdictMap = {
    genuine: "AUTHENTIC" as const,
    suspicious: "SUSPICIOUS" as const,
    synthetic_clone: "CLONED" as const,
  };
  const actionMap = {
    genuine: "Allowed",
    suspicious: "Challenged",
    synthetic_clone: "Terminated",
  };
  const date = new Date(raw.scanned_at);
  return {
    id: raw.id,
    time: isNaN(date.getTime())
      ? raw.scanned_at
      : date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    language: raw.language ?? "Unknown",
    risk: Math.round(raw.impersonation_risk_score),
    verdict: verdictMap[raw.verdict],
    action: actionMap[raw.verdict],
  };
}

function exportCsv(items: ScanItem[]) {
  const header = "ID,Time,Language,Risk %,Verdict,Action";
  const rows = items.map(
    (i) => `${i.id},${i.time},${i.language},${i.risk},${i.verdict},${i.action}`
  );
  const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vaniguard-audit-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Verdict badge ────────────────────────────────────────────────────────────
function VerdictBadge({ verdict }: { verdict: ScanItem["verdict"] }) {
  const styles = {
    CLONED: "bg-rose-500/10 text-rose-400 border border-rose-500/20",
    SUSPICIOUS: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
    AUTHENTIC: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-bold uppercase ${styles[verdict]}`}>
      {verdict}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function AuditLogs() {
  const [items, setItems] = useState<ScanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingMock, setUsingMock] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  // Filters
  const [verdictFilter, setVerdictFilter] = useState<string>("all");
  const [langFilter, setLangFilter] = useState<string>("all");

  const fetchPage = useCallback(
    async (cursor?: string, append = false) => {
      append ? setLoadingMore(true) : setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({ limit: "20" });
        if (cursor) params.set("cursor", cursor);
        if (verdictFilter !== "all") params.set("verdict", verdictFilter);
        if (langFilter !== "all") params.set("language", langFilter);

        const res = await fetch(`${API_BASE}/api/scans/history?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const mapped: ScanItem[] = (data.items ?? []).map(mapScan);
        setItems((prev) => (append ? [...prev, ...mapped] : mapped));
        setNextCursor(data.next_cursor ?? null);
        setUsingMock(false);
      } catch {
        if (!append) {
          // Only fall back on the initial load
          setItems(MOCK_SCANS);
          setUsingMock(true);
          setError(
            "API unreachable — showing demo data. Start the FastAPI server to see live audit logs."
          );
        }
      } finally {
        append ? setLoadingMore(false) : setLoading(false);
      }
    },
    [verdictFilter, langFilter]
  );

  // Re-fetch whenever filters change
  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  const handleLoadMore = () => {
    if (nextCursor) fetchPage(nextCursor, true);
  };

  // Derive unique languages for the filter dropdown
  const languages = ["all", ...Array.from(new Set(items.map((i) => i.language).filter(Boolean)))];

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-200">Incident &amp; Audit Logs</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {usingMock ? "Demo data" : `${items.length} records`}
            {!usingMock && nextCursor ? " (scroll for more)" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Verdict filter */}
          <div className="flex items-center gap-1.5 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <select
              id="verdict-filter"
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="bg-transparent text-slate-300 text-xs outline-none cursor-pointer"
            >
              <option value="all">All Verdicts</option>
              <option value="synthetic_clone">Cloned</option>
              <option value="suspicious">Suspicious</option>
              <option value="genuine">Authentic</option>
            </select>
          </div>

          {/* Language filter */}
          <div className="flex items-center gap-1.5 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300">
            <select
              id="language-filter"
              value={langFilter}
              onChange={(e) => setLangFilter(e.target.value)}
              className="bg-transparent text-slate-300 text-xs outline-none cursor-pointer"
            >
              {languages.map((l) => (
                <option key={l} value={l}>
                  {l === "all" ? "All Languages" : l}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchPage()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition-colors border border-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={() => exportCsv(items)}
            disabled={items.length === 0}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition-colors border border-slate-700 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Error banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm"
          >
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 backdrop-blur-sm shadow-xl flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/80 sticky top-0 z-10">
              <tr>
                <th className="px-5 py-4">Timestamp</th>
                <th className="px-5 py-4">Language</th>
                <th className="px-5 py-4">Risk Score</th>
                <th className="px-5 py-4">Verdict</th>
                <th className="px-5 py-4">Action Taken</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <>
                  {[...Array(6)].map((_, i) => (
                    <tr key={i} className="border-b border-slate-800/50">
                      {[...Array(5)].map((_, j) => (
                        <td key={j} className="px-5 py-4">
                          <div className="h-4 bg-slate-800 rounded animate-pulse w-3/4" />
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              )}

              {!loading &&
                items.map((item, i) => (
                  <motion.tr
                    key={item.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(i * 0.03, 0.3) }}
                    className={`border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors ${
                      i % 2 === 0 ? "bg-slate-900/20" : ""
                    }`}
                  >
                    <td className="px-5 py-4 font-mono text-slate-300 text-xs">{item.time}</td>
                    <td className="px-5 py-4">
                      <span className="px-2 py-1 rounded bg-slate-800 text-xs text-slate-400">
                        {item.language}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono font-bold ${
                            item.risk > 70
                              ? "text-rose-400"
                              : item.risk > 40
                              ? "text-amber-400"
                              : "text-emerald-400"
                          }`}
                        >
                          {item.risk}%
                        </span>
                        {item.risk > 70 && <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <VerdictBadge verdict={item.verdict} />
                    </td>
                    <td className="px-5 py-4 text-slate-400 text-xs">{item.action}</td>
                  </motion.tr>
                ))}

              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-16 text-center text-slate-500">
                    No records found for the selected filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Load More */}
        {!usingMock && nextCursor && !loading && (
          <div className="px-5 py-4 border-t border-slate-800 flex justify-center">
            <button
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="flex items-center gap-2 px-5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors border border-slate-700 disabled:opacity-50"
            >
              <ChevronDown className={`w-4 h-4 ${loadingMore ? "animate-bounce" : ""}`} />
              {loadingMore ? "Loading..." : "Load More"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
