import { ShieldCheck, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

export function TopNav() {
  return (
    <nav className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="flex h-16 items-center px-6 gap-4">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight text-white">
          <ShieldCheck className="h-6 w-6 text-emerald-500" />
          <span>VaniGuard</span>
        </div>
        
        <div className="flex-1" />
        
        <div className="flex items-center gap-4 text-sm font-medium">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            AI Engine: Online
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-700/50 text-slate-300">
            <Activity className="h-4 w-4 text-emerald-400" />
            <span className="tabular-nums">Latency: 320ms</span>
          </div>
        </div>
      </div>
    </nav>
  );
}
