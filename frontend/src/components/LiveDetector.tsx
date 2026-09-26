"use client";

import { useState, useEffect } from "react";
import { Mic, Upload, Download, ShieldAlert, Shield, PhoneCall } from "lucide-react";
import { AudioVisualizer } from "./AudioVisualizer";
import { RiskGauge } from "./RiskGauge";
import { analyzeAudio, type DetectionResult } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { useAudioStream } from "@/hooks/useAudioStream";

export function LiveDetector() {
  const [isAnalyzingFile, setIsAnalyzingFile] = useState(false);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [language, setLanguage] = useState("English");
  
  const { isStreaming, latestResult, error, startStream, stopStream } = useAudioStream();
  
  // Sync streaming result to the static result state so UI updates uniformly
  useEffect(() => {
    if (latestResult) {
      // Map StreamResult to DetectionResult interface
      let mappedVerdict: 'AUTHENTIC' | 'SUSPICIOUS' | 'CLONED' = 'AUTHENTIC';
      if (latestResult.verdict.includes("AI-Generated") || latestResult.verdict === "SYNTHETIC CLONE DETECTED") {
        mappedVerdict = 'CLONED';
      } else if (latestResult.verdict === "UNCERTAIN") {
        mappedVerdict = 'SUSPICIOUS';
      }

      setResult({
        score: latestResult.prob_ai * 100,
        verdict: mappedVerdict,
        details: {
          spectralJitter: latestResult.status_confidence * 100, // Using confidence for demo mapping
          harmonicArtifacts: latestResult.prob_ai * 80, 
          phonemeConsistency: 100 - (latestResult.prob_ai * 60),
          neuralSynthesisMarkers: latestResult.prob_ai * 100,
        },
        duration: (latestResult.window_index * 4096) / 16000, // Approx seconds if buffer is 4096@16kHz
        language: language,
      });
    }
  }, [latestResult, language]);

  const handleRecordToggle = async () => {
    if (isStreaming) {
      stopStream();
    } else {
      setResult(null); // Clear previous results
      await startStream();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      if (isStreaming) stopStream();
      setIsAnalyzingFile(true);
      setResult(null);
      const res = await analyzeAudio(e.target.files[0], language);
      setResult(res);
      setIsAnalyzingFile(false);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-full p-6">
      {/* Left Column: Audio Ingestion */}
      <div className="flex-1 flex flex-col gap-6">
        <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex flex-col">
          <h2 className="text-xl font-semibold mb-4 text-slate-200">Audio Ingestion</h2>
          
          <div className="flex items-center gap-2 mb-6">
            <span className="text-sm text-slate-400">Target Language Model:</span>
            <div className="flex gap-2">
              {["English", "Hindi", "Telugu", "Tamil"].map(lang => (
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    language === lang 
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/50" 
                    : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
                  }`}
                >
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
            <button
              onClick={handleRecordToggle}
              className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all ${
                isStreaming 
                ? "bg-rose-500/20 text-rose-400 border border-rose-500/50 hover:bg-rose-500/30 shadow-[0_0_15px_rgba(239,68,68,0.2)]" 
                : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.1)]"
              }`}
            >
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

        {/* Detailed Metrics Panel */}
        <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl">
          <div className="flex justify-between items-center mb-4">
             <h2 className="text-xl font-semibold text-slate-200">Acoustic Analysis</h2>
             {isStreaming && latestResult && (
                <span className={`text-xs font-mono px-2 py-1 rounded ${latestResult.status_level === 'CRITICAL' ? 'bg-rose-500/20 text-rose-400' : 'bg-slate-800 text-slate-400'}`}>
                   Status: {latestResult.status_level}
                </span>
             )}
          </div>
          
          {result ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
              <MetricRow label="Spectral Jitter" value={result.details.spectralJitter} isHigh={result.details.spectralJitter > 60} />
              <MetricRow label="Harmonic Artifacts" value={result.details.harmonicArtifacts} isHigh={result.details.harmonicArtifacts > 60} />
              <MetricRow label="Phoneme Consistency" value={result.details.phonemeConsistency} isHigh={result.details.phonemeConsistency < 40} />
              <MetricRow label="Neural Synthesis Markers" value={result.details.neuralSynthesisMarkers} isHigh={result.details.neuralSynthesisMarkers > 50} />
            </motion.div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500">
              Awaiting audio input to begin analysis...
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Real-Time Risk Scorecard */}
      <div className="w-full lg:w-96 flex flex-col gap-6">
        <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex-1 flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <Shield className="w-32 h-32" />
          </div>
          
          <RiskGauge 
            score={result?.score || 0} 
            verdict={result?.verdict || (isAnalyzingFile ? "IDLE" : "IDLE")} 
          />

          <AnimatePresence>
            {result && result.score > 70 && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-10 w-full space-y-3"
              >
                <h3 className="text-sm font-semibold text-rose-400 uppercase tracking-wider mb-2">Preventive Actions Available</h3>
                <button className="w-full py-2 px-4 rounded-lg bg-rose-500 hover:bg-rose-600 text-white font-medium flex items-center gap-2 justify-center transition-colors">
                  <ShieldAlert className="w-4 h-4" /> Trigger OTP Verification
                </button>
                <button className="w-full py-2 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium flex items-center gap-2 justify-center transition-colors border border-slate-700">
                  <PhoneCall className="w-4 h-4" /> Alert Trusted Circle
                </button>
                <button className="w-full py-2 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium flex items-center gap-2 justify-center transition-colors border border-slate-700">
                  <Download className="w-4 h-4" /> Download Forensic Packet
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value, isHigh }: { label: string; value: number; isHigh: boolean }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-300">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
        <motion.div 
          className={`h-full rounded-full ${isHigh ? 'bg-rose-500' : 'bg-emerald-500'}`}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
