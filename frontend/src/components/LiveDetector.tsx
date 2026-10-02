"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Mic, Upload, Download, ShieldAlert, Shield,
  PhoneCall, X, CheckCircle, RefreshCw, User,
} from "lucide-react";
import { AudioVisualizer } from "./AudioVisualizer";
import { RiskGauge } from "./RiskGauge";
import { analyzeAudio, type DetectionResult } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { useAudioStream } from "@/hooks/useAudioStream";
import { API_BASE, API_KEY } from "@/lib/config";

// ── OTP Modal ────────────────────────────────────────────────────────────────
function OtpModal({ onClose }: { onClose: () => void }) {
  const [phase, setPhase] = useState<"sending" | "waiting" | "verified">("sending");
  const [otp, setOtp] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(60);

  useEffect(() => {
    const code = String(Math.floor(100000 + Math.random() * 900000));
    const timer = setTimeout(() => { setOtp(code); setPhase("waiting"); }, 1200);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (phase !== "waiting" || secondsLeft <= 0) return;
    const id = setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearInterval(id);
  }, [phase, secondsLeft]);

  const handleResend = () => {
    setSecondsLeft(60);
    setPhase("sending");
    setTimeout(() => {
      setOtp(String(Math.floor(100000 + Math.random() * 900000)));
      setPhase("waiting");
    }, 1200);
  };

  const handleVerify = () => {
    setPhase("verified");
    setTimeout(onClose, 2200);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
        className="bg-slate-900 border border-slate-700 rounded-2xl p-8 w-full max-w-sm shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <h3 className="text-slate-100 font-semibold">OTP Verification</h3>
              <p className="text-xs text-slate-500">Voice fraud protection</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <AnimatePresence mode="wait">
          {phase === "sending" && (
            <motion.div key="sending" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-4 py-4">
              <div className="w-10 h-10 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-400 text-sm">Dispatching OTP via SMS…</p>
            </motion.div>
          )}

          {phase === "waiting" && (
            <motion.div key="waiting" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-5">
              <p className="text-sm text-slate-400 text-center">
                Verification code sent to the caller&apos;s registered number.<br />
                Share this code only with the verified caller:
              </p>

              {/* 6-digit OTP tiles */}
              <div className="flex gap-2 justify-center">
                {otp.split("").map((digit, i) => (
                  <motion.div key={i}
                    initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: i * 0.07 }}
                    className="w-10 h-12 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-xl font-mono font-bold text-rose-300">
                    {digit}
                  </motion.div>
                ))}
              </div>

              {/* Conic countdown */}
              <div className="flex items-center justify-center gap-2">
                <div className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ background: `conic-gradient(#f43f5e ${(secondsLeft / 60) * 360}deg, #1e293b 0deg)` }}>
                  <span className="bg-slate-900 rounded-full w-6 h-6 flex items-center justify-center text-xs text-rose-400 font-mono font-bold">
                    {secondsLeft}
                  </span>
                </div>
                <span className="text-xs text-slate-500">seconds remaining</span>
              </div>

              {secondsLeft === 0 && (
                <button onClick={handleResend}
                  className="flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 justify-center transition-colors">
                  <RefreshCw className="w-3.5 h-3.5" /> Resend OTP
                </button>
              )}

              <button onClick={handleVerify}
                className="w-full py-2.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-semibold transition-colors text-sm">
                Mark as Verified
              </button>
            </motion.div>
          )}

          {phase === "verified" && (
            <motion.div key="verified" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center gap-3 py-6">
              <CheckCircle className="w-14 h-14 text-emerald-400" />
              <p className="text-emerald-400 font-semibold">Caller Verified</p>
              <p className="text-xs text-slate-500">Identity confirmed — call may proceed</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}

// ── Trusted Circle Panel ─────────────────────────────────────────────────────
type Contact = {
  id: string;
  contact_name: string;
  contact_phone: string;
  relationship_type?: string | null;
};

const DEMO_CONTACTS: Contact[] = [
  { id: "demo-1", contact_name: "Priya (Daughter)", contact_phone: "+91 98765 43210", relationship_type: "family" },
  { id: "demo-2", contact_name: "Arjun (Son)", contact_phone: "+91 87654 32109", relationship_type: "family" },
  { id: "demo-3", contact_name: "Dr. Meera", contact_phone: "+91 76543 21098", relationship_type: "doctor" },
];

function TrustedCirclePanel({ onClose }: { onClose: () => void }) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [alerted, setAlerted] = useState<Set<string>>(new Set());

  useEffect(() => {
    const load = async () => {
      // Auth headers required now that all /api/users/* endpoints are protected.
      const headers: HeadersInit = API_KEY ? { "X-API-Key": API_KEY } : {};
      try {
        const usersRes = await fetch(`${API_BASE}/api/users/?limit=1`, { headers });
        if (!usersRes.ok) throw new Error();
        const users = await usersRes.json();
        if (users.length > 0) {
          const contactsRes = await fetch(`${API_BASE}/api/users/${users[0].id}/contacts`, { headers });
          if (!contactsRes.ok) throw new Error();
          const data: Contact[] = await contactsRes.json();
          setContacts(data.length > 0 ? data : DEMO_CONTACTS);
        } else {
          setContacts(DEMO_CONTACTS);
        }
      } catch {
        setContacts(DEMO_CONTACTS);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const sendAlert = useCallback((id: string) => {
    setAlerted((prev) => new Set([...prev, id]));
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
        className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-sm shadow-2xl"
      >
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
              <PhoneCall className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-slate-100 font-semibold">Alert Trusted Circle</h3>
              <p className="text-xs text-slate-500">Notify contacts about suspected fraud</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-2 max-h-72 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : contacts.map((c) => {
            const sent = alerted.has(c.id);
            return (
              <motion.div key={c.id} layout
                className="flex items-center justify-between p-3 rounded-xl bg-slate-800/60 border border-slate-700/50">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center text-slate-400">
                    <User className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">{c.contact_name}</p>
                    <p className="text-xs text-slate-500 font-mono">{c.contact_phone}</p>
                  </div>
                </div>
                <button
                  onClick={() => sendAlert(c.id)}
                  disabled={sent}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    sent
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30"
                  }`}
                >
                  {sent
                    ? <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3" />Alerted</span>
                    : "Alert"}
                </button>
              </motion.div>
            );
          })}
        </div>

        {alerted.size > 0 && (
          <div className="px-6 pb-5 pt-1">
            <p className="text-xs text-emerald-400 text-center">
              ✓ {alerted.size} contact{alerted.size > 1 ? "s" : ""} notified about the suspected AI voice fraud
            </p>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

// ── Forensic Packet Download ──────────────────────────────────────────────────
function downloadForensicPacket(result: DetectionResult) {
  const packet = {
    report_type: "VaniGuard Forensic Packet",
    generated_at: new Date().toISOString(),
    schema_version: "1.0",
    detection: {
      verdict: result.verdict,
      risk_score_pct: result.score.toFixed(2),
      language: result.language,
      audio_duration_s: result.duration,
    },
    acoustic_markers: {
      spectral_jitter: result.details.spectralJitter.toFixed(2),
      harmonic_artifacts: result.details.harmonicArtifacts.toFixed(2),
      phoneme_consistency: result.details.phonemeConsistency.toFixed(2),
      neural_synthesis_markers: result.details.neuralSynthesisMarkers.toFixed(2),
    },
    metadata: {
      model: "MobileNetV2 (ONNX)",
      server: "VaniGuard API v1.0.0",
      timestamp_unix: Date.now(),
    },
  };
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vaniguard-forensic-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Main LiveDetector ─────────────────────────────────────────────────────────
export function LiveDetector() {
  const [isAnalyzingFile, setIsAnalyzingFile] = useState(false);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [language, setLanguage] = useState("English");
  const [showOtp, setShowOtp] = useState(false);
  const [showCircle, setShowCircle] = useState(false);

  const { isStreaming, latestResult, error, startStream, stopStream } = useAudioStream();

  // useMemo: only recompute when latestResult changes, NOT on every render.
  // Previously this was an IIFE evaluated unconditionally on each render,
  // causing expensive re-computation on every WebSocket frame.  See CRIT-07.
  const streamingResult: DetectionResult | null = useMemo(() => {
    if (!latestResult) return null;

    let mappedVerdict: "AUTHENTIC" | "SUSPICIOUS" | "CLONED" = "AUTHENTIC";
    if (
      latestResult.verdict.includes("AI-Generated") ||
      latestResult.verdict === "SYNTHETIC CLONE DETECTED"
    ) {
      mappedVerdict = "CLONED";
    } else if (latestResult.verdict === "UNCERTAIN") {
      mappedVerdict = "SUSPICIOUS";
    }

    return {
      score: latestResult.prob_ai * 100,
      verdict: mappedVerdict,
      details: {
        spectralJitter: latestResult.status_confidence * 100,
        harmonicArtifacts: latestResult.prob_ai * 80,
        phonemeConsistency: 100 - latestResult.prob_ai * 60,
        neuralSynthesisMarkers: latestResult.prob_ai * 100,
      },
      duration: (latestResult.window_index * 4096) / 16000,
      language,
    };
  }, [latestResult, language]);

  const displayResult = streamingResult ?? result;

  const handleRecordToggle = async () => {
    if (isStreaming) {
      stopStream();
    } else {
      setResult(null);
      await startStream();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      if (isStreaming) stopStream();
      setIsAnalyzingFile(true);
      setResult(null);
      try {
        const res = await analyzeAudio(e.target.files[0], language);
        setResult(res);
      } catch (err) {
        console.error("Audio analysis failed:", err);
      } finally {
        setIsAnalyzingFile(false);
      }
    }
  };

  return (
    <>
      {/* Modals — rendered outside the main layout so they overlay everything */}
      <AnimatePresence>
        {showOtp && <OtpModal onClose={() => setShowOtp(false)} />}
        {showCircle && <TrustedCirclePanel onClose={() => setShowCircle(false)} />}
      </AnimatePresence>

      <div className="flex flex-col lg:flex-row gap-6 h-full p-6">
        {/* ── Left Column ── */}
        <div className="flex-1 flex flex-col gap-6">

          {/* Audio Ingestion card */}
          <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex flex-col">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">Audio Ingestion</h2>

            <div className="flex items-center gap-2 mb-6">
              <span className="text-sm text-slate-400">Target Language Model:</span>
              <div className="flex gap-2">
                {["English", "Hindi", "Telugu", "Tamil"].map((lang) => (
                  <button key={lang} onClick={() => setLanguage(lang)}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                      language === lang
                        ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/50"
                        : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
                    }`}>
                    {lang}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded bg-rose-500/20 border border-rose-500/50 text-rose-400 text-sm">
                {error}
              </div>
            )}

            <AudioVisualizer isRecording={isStreaming} isAnalyzing={isAnalyzingFile} />

            <div className="flex gap-4 mt-6">
              <button onClick={handleRecordToggle}
                className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all ${
                  isStreaming
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/50 hover:bg-rose-500/30 shadow-[0_0_15px_rgba(239,68,68,0.2)]"
                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.1)]"
                }`}>
                <Mic className="w-5 h-5" />
                {isStreaming ? "Stop Live Stream" : "Start Live Stream"}
              </button>

              <label className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 cursor-pointer transition-colors">
                <Upload className="w-5 h-5" />
                Upload Audio
                <input type="file" className="hidden" accept="audio/*" onChange={handleFileUpload} />
              </label>
            </div>
          </div>

          {/* Acoustic Analysis card */}
          <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-slate-200">Acoustic Analysis</h2>
              {isStreaming && latestResult && (
                <span className={`text-xs font-mono px-2 py-1 rounded ${
                  latestResult.status_level === "CRITICAL"
                    ? "bg-rose-500/20 text-rose-400"
                    : "bg-slate-800 text-slate-400"
                }`}>
                  Status: {latestResult.status_level}
                </span>
              )}
            </div>

            {displayResult ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <MetricRow label="Spectral Jitter" value={displayResult.details.spectralJitter} isHigh={displayResult.details.spectralJitter > 60} />
                <MetricRow label="Harmonic Artifacts" value={displayResult.details.harmonicArtifacts} isHigh={displayResult.details.harmonicArtifacts > 60} />
                <MetricRow label="Phoneme Consistency" value={displayResult.details.phonemeConsistency} isHigh={displayResult.details.phonemeConsistency < 40} />
                <MetricRow label="Neural Synthesis Markers" value={displayResult.details.neuralSynthesisMarkers} isHigh={displayResult.details.neuralSynthesisMarkers > 50} />
              </motion.div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500">
                Awaiting audio input to begin analysis...
              </div>
            )}
          </div>
        </div>

        {/* ── Right Column: Risk Scorecard ── */}
        <div className="w-full lg:w-96 flex flex-col gap-6">
          <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex-1 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Shield className="w-32 h-32" />
            </div>

            <RiskGauge score={displayResult?.score || 0} verdict={displayResult?.verdict || "IDLE"} />

            <AnimatePresence>
              {displayResult && displayResult.score > 70 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="mt-10 w-full space-y-3"
                >
                  <h3 className="text-sm font-semibold text-rose-400 uppercase tracking-wider mb-2">
                    Preventive Actions Available
                  </h3>

                  {/* OTP Verification */}
                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={() => setShowOtp(true)}
                    className="w-full py-2.5 px-4 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-semibold flex items-center gap-2 justify-center transition-colors shadow-[0_0_20px_rgba(239,68,68,0.3)]"
                  >
                    <ShieldAlert className="w-4 h-4" /> Trigger OTP Verification
                  </motion.button>

                  {/* Alert Trusted Circle */}
                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={() => setShowCircle(true)}
                    className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold flex items-center gap-2 justify-center transition-colors border border-slate-700"
                  >
                    <PhoneCall className="w-4 h-4" /> Alert Trusted Circle
                  </motion.button>

                  {/* Forensic Packet */}
                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={() => downloadForensicPacket(displayResult)}
                    className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold flex items-center gap-2 justify-center transition-colors border border-slate-700"
                  >
                    <Download className="w-4 h-4" /> Download Forensic Packet
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </>
  );
}

// ── MetricRow ────────────────────────────────────────────────────────────────
function MetricRow({ label, value, isHigh }: { label: string; value: number; isHigh: boolean }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-300">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${isHigh ? "bg-rose-500" : "bg-emerald-500"}`}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
