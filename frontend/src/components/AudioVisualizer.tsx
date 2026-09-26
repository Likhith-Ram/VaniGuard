"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AudioVisualizerProps {
  isRecording: boolean;
  isAnalyzing: boolean;
}

export function AudioVisualizer({ isRecording, isAnalyzing }: AudioVisualizerProps) {
  const [bars, setBars] = useState<number[]>(Array.from({ length: 40 }).map(() => 5));

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRecording || isAnalyzing) {
      interval = setInterval(() => {
        setBars((prev) => prev.map(() => (isAnalyzing ? 10 + Math.random() * 90 : 5 + Math.random() * 60)));
      }, 100);
    } else {
      setBars(Array.from({ length: 40 }).map(() => 5));
    }
    return () => clearInterval(interval);
  }, [isRecording, isAnalyzing]);

  return (
    <div className="w-full h-32 bg-slate-900/50 rounded-xl border border-slate-800 flex items-center justify-center gap-1 p-4 overflow-hidden relative">
      <div className="absolute inset-0 grid grid-cols-[repeat(40,minmax(0,1fr))] gap-1 px-4 items-center">
        {bars.map((height, i) => (
          <motion.div
            key={i}
            className={cn(
              "w-full rounded-full",
              isAnalyzing ? "bg-emerald-500/80" : isRecording ? "bg-amber-500/80" : "bg-slate-700/50"
            )}
            animate={{ height: `${height}%` }}
            transition={{ type: "tween", duration: 0.1 }}
          />
        ))}
      </div>
      
      {isRecording && (
        <div className="absolute top-3 left-4 flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
          </span>
          <span className="text-xs font-mono text-rose-400 uppercase tracking-wider">Live Input</span>
        </div>
      )}
      
      {isAnalyzing && (
        <div className="absolute top-3 right-4 flex items-center gap-2">
          <span className="text-xs font-mono text-emerald-400 uppercase tracking-wider animate-pulse">Processing...</span>
        </div>
      )}
    </div>
  );
}
