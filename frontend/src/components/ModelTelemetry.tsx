"use client";

import { useEffect, useState, useCallback } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
  ReferenceLine,
  Legend,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  ShieldAlert,
  ShieldCheck,
  HelpCircle,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { fetchStats, fetchHistory, type HistoryStats, type HistoryEntry } from "@/lib/api";

// ── Mock fallback data ──────────────────────────────────────────────────────
const MOCK_STATS: HistoryStats = {
  total: 142,
  ai_detected: 61,
  human_detected: 68,
  uncertain: 13,
  ai_detection_rate: 42.9,
  avg_confidence: 78.3,
};

function buildMockHistory(): HistoryEntry[] {
  return Array.from({ length: 60 }, (_, i) => ({
    id: i + 1,
    timestamp: new Date(Date.now() - (59 - i) * 3 * 60_000).toISOString(),
    filename: `sample_${i}.wav`,
    verdict: i % 3 === 0 ? "AI-Generated" : i % 5 === 0 ? "UNCERTAIN" : "Human",
    confidence_pct: 40 + Math.random() * 55,
    risk_band: i % 3 === 0 ? "HIGH RISK" : "LOW RISK",
    probability: i % 3 === 0 ? 0.6 + Math.random() * 0.38 : Math.random() * 0.35,
  }));
}

// ── Chart helpers ───────────────────────────────────────────────────────────
function buildConfidenceHistogram(entries: HistoryEntry[]) {
  const buckets = Array.from({ length: 10 }, (_, i) => ({
    range: `${i * 10}–${i * 10 + 10}`,
    count: 0,
  }));
  for (const e of entries) {
    const idx = Math.min(Math.floor(e.confidence_pct / 10), 9);
    buckets[idx].count++;
  }
  return buckets;
}

function buildTrendData(entries: HistoryEntry[]) {
  return [...entries].reverse().slice(-30).map((e, i) => ({
    index: i + 1,
    prob_ai: Math.round(e.probability * 100),
  }));
}

const VERDICT_COLORS = ["#f43f5e", "#f59e0b", "#10b981"];

// ── Custom tooltips ─────────────────────────────────────────────────────────
const CustomBarTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 shadow-xl">
        <p className="font-semibold">{label}%</p>
        <p className="text-indigo-400">{payload[0].value} samples</p>
      </div>
    );
  }
  return null;
};

const CustomLineTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; name: string }[];
  label?: string;
}) => {
  if (active && payload && payload.length) {
    const prob = payload.find((p) => p.name === "prob_ai");
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 shadow-xl">
        <p className="font-semibold mb-1">Sample #{label}</p>
        {prob && (
          <p className={prob.value >= 60 ? "text-rose-400" : "text-emerald-400"}>
            P(AI): {prob.value}%
          </p>
        )}
      </div>
    );
  }
  return null;
};

// ── KPI Card ────────────────────────────────────────────────────────────────
function KpiCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
  delay,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="bg-slate-900/60 rounded-2xl border border-slate-800 p-5 backdrop-blur-sm flex flex-col gap-3"
    >
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
        <p className="text-2xl font-bold text-slate-100 font-mono">{value}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────
export function ModelTelemetry() {
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingMock, setUsingMock] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, h] = await Promise.all([fetchStats(), fetchHistory(30)]);
      setStats(s);
      setHistory(h);
      setUsingMock(false);
    } catch {
      setStats(MOCK_STATS);
      setHistory(buildMockHistory());
      setUsingMock(true);
      setError(
        "API unreachable — showing demo data. Start the FastAPI server to see live metrics."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [load]);

  const verdictData = stats
    ? [
        { name: "AI-Generated", value: stats.ai_detected },
        { name: "Uncertain", value: stats.uncertain },
        { name: "Human", value: stats.human_detected },
      ]
    : [];

  const histogramData = buildConfidenceHistogram(history);
  const trendData = buildTrendData(history);

  return (
    <div className="p-6 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-200">Model Telemetry</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time inference statistics from the VaniGuard ONNX model
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors border border-slate-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Error / mock banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="mb-5 flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm"
          >
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-slate-900/60 rounded-2xl border border-slate-800 h-32 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* KPI Cards */}
      {!loading && stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            icon={Activity}
            label="Total Scans"
            value={stats.total.toLocaleString()}
            sub={usingMock ? "demo data" : "all time"}
            color="bg-indigo-500/20 text-indigo-400"
            delay={0}
          />
          <KpiCard
            icon={ShieldAlert}
            label="AI Detected"
            value={`${stats.ai_detection_rate}%`}
            sub={`${stats.ai_detected} of ${stats.total}`}
            color="bg-rose-500/20 text-rose-400"
            delay={0.07}
          />
          <KpiCard
            icon={ShieldCheck}
            label="Avg Confidence"
            value={`${stats.avg_confidence}%`}
            sub="model certainty"
            color="bg-emerald-500/20 text-emerald-400"
            delay={0.14}
          />
          <KpiCard
            icon={HelpCircle}
            label="Uncertain"
            value={stats.uncertain}
            sub={`${stats.total ? ((stats.uncertain / stats.total) * 100).toFixed(1) : 0}% of scans`}
            color="bg-amber-500/20 text-amber-400"
            delay={0.21}
          />
        </div>
      )}

      {/* Charts */}
      {!loading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Verdict Donut */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.25 }}
            className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm"
          >
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
              Verdict Distribution
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={verdictData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={82}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {verdictData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={VERDICT_COLORS[index]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                    color: "#e2e8f0",
                    fontSize: "12px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-2 mt-3">
              {verdictData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: VERDICT_COLORS[i] }}
                    />
                    <span className="text-slate-400">{d.name}</span>
                  </span>
                  <span className="font-mono text-slate-300">{d.value}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Confidence Histogram */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.32 }}
            className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm"
          >
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
              Confidence Score Distribution
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={histogramData} barSize={16} margin={{ bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis
                  dataKey="range"
                  tick={{ fontSize: 9, fill: "#64748b" }}
                  interval={0}
                  angle={-35}
                  textAnchor="end"
                  height={48}
                />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} width={28} />
                <Tooltip
                  content={<CustomBarTooltip />}
                  cursor={{ fill: "rgba(99,102,241,0.08)" }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </motion.div>

          {/* P(AI) Trend */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.39 }}
            className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm"
          >
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
              P(AI) — Last 30 Samples
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendData} margin={{ right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="index" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: "#64748b" }}
                  unit="%"
                  width={36}
                />
                <Tooltip content={<CustomLineTooltip />} />
                <ReferenceLine
                  y={60}
                  stroke="#f43f5e"
                  strokeDasharray="4 2"
                  strokeOpacity={0.6}
                  label={{
                    value: "Alert",
                    position: "insideTopRight",
                    fontSize: 10,
                    fill: "#f43f5e",
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: "11px", color: "#94a3b8" }}
                  formatter={() => "P(AI-generated)"}
                />
                <Line
                  type="monotone"
                  dataKey="prob_ai"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={(props) => {
                    const { cx, cy, payload } = props;
                    const isHigh = payload.prob_ai >= 60;
                    return (
                      <circle
                        key={`dot-${cx}-${cy}`}
                        cx={cx}
                        cy={cy}
                        r={isHigh ? 4 : 2.5}
                        fill={isHigh ? "#f43f5e" : "#6366f1"}
                        stroke="none"
                      />
                    );
                  }}
                  activeDot={{ r: 5, fill: "#a5b4fc" }}
                  name="prob_ai"
                />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>
        </div>
      )}
    </div>
  );
}
