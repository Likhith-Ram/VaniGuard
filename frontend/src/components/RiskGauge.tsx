"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface RiskGaugeProps {
  score: number; // 0 to 100
  verdict: "AUTHENTIC" | "SUSPICIOUS" | "CLONED" | "IDLE";
}

export function RiskGauge({ score, verdict }: RiskGaugeProps) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getVerdictColor = () => {
    switch (verdict) {
      case "AUTHENTIC": return "text-emerald-500 stroke-emerald-500";
      case "SUSPICIOUS": return "text-amber-500 stroke-amber-500";
      case "CLONED": return "text-rose-500 stroke-rose-500";
      default: return "text-slate-600 stroke-slate-700";
    }
  };

  const getGlow = () => {
    switch (verdict) {
      case "AUTHENTIC": return "drop-shadow-[0_0_12px_rgba(16,185,129,0.5)]";
      case "SUSPICIOUS": return "drop-shadow-[0_0_12px_rgba(245,158,11,0.5)]";
      case "CLONED": return "drop-shadow-[0_0_12px_rgba(239,68,68,0.8)]";
      default: return "";
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center">
      <div className="relative flex items-center justify-center h-48 w-48">
        <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 160 160">
          <circle
            className="stroke-slate-800 transition-all duration-300 ease-in-out"
            strokeWidth="12"
            fill="transparent"
            r={radius}
            cx="80"
            cy="80"
          />
          <motion.circle
            className={cn("transition-all duration-1000 ease-out", getVerdictColor(), getGlow())}
            strokeWidth="12"
            strokeLinecap="round"
            fill="transparent"
            r={radius}
            cx="80"
            cy="80"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: verdict === "IDLE" ? circumference : strokeDashoffset }}
            strokeDasharray={circumference}
          />
        </svg>

        <div className="absolute flex flex-col items-center justify-center">
          <motion.span 
            key={score}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn("text-5xl font-bold tabular-nums tracking-tighter", getVerdictColor().split(" ")[0])}
          >
            {verdict === "IDLE" ? "--" : Math.round(score)}
            <span className="text-xl ml-1">%</span>
          </motion.span>
          <span className="text-xs text-slate-400 font-medium tracking-wider uppercase mt-1">
            Risk Score
          </span>
        </div>
      </div>
      
      {verdict !== "IDLE" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "mt-4 px-6 py-2 rounded-full font-bold tracking-widest text-sm uppercase border",
            verdict === "AUTHENTIC" && "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
            verdict === "SUSPICIOUS" && "bg-amber-500/10 border-amber-500/20 text-amber-400",
            verdict === "CLONED" && "bg-rose-500/10 border-rose-500/20 text-rose-400 shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse"
          )}
        >
          {verdict === "AUTHENTIC" && "AUTHENTIC VOICE - High Confidence"}
          {verdict === "SUSPICIOUS" && "SUSPICIOUS - Potential Artifacts"}
          {verdict === "CLONED" && "SYNTHETIC CLONE DETECTED"}
        </motion.div>
      )}
    </div>
  );
}
