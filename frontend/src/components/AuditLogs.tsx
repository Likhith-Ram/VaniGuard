"use client";

import { FileAudio, Download, AlertTriangle } from "lucide-react";

const mockLogs = [
  { id: "LOG-094", time: "14:22:05", source: "SIP Gateway", lang: "Hindi", risk: 94, verdict: "CLONED", action: "Terminated" },
  { id: "LOG-093", time: "14:15:30", source: "File Upload", lang: "English", risk: 12, verdict: "AUTHENTIC", action: "Allowed" },
  { id: "LOG-092", time: "13:50:11", source: "Live Mic", lang: "Telugu", risk: 45, verdict: "SUSPICIOUS", action: "Challenged" },
  { id: "LOG-091", time: "12:05:40", source: "SIP Gateway", lang: "Tamil", risk: 8, verdict: "AUTHENTIC", action: "Allowed" },
];

export function AuditLogs() {
  return (
    <div className="p-6 h-full">
      <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl h-full flex flex-col">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-slate-200">Incident & Audit Logs</h2>
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors border border-slate-700">
            <Download className="w-4 h-4" /> Export CSV
          </button>
        </div>
        
        <div className="flex-1 overflow-auto rounded-xl border border-slate-800 bg-slate-950/50">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/80 sticky top-0">
              <tr>
                <th className="px-6 py-4">Timestamp</th>
                <th className="px-6 py-4">Source</th>
                <th className="px-6 py-4">Language</th>
                <th className="px-6 py-4">Risk Score</th>
                <th className="px-6 py-4">Verdict</th>
                <th className="px-6 py-4">Action Taken</th>
                <th className="px-6 py-4 text-right">Audio</th>
              </tr>
            </thead>
            <tbody>
              {mockLogs.map((log, i) => (
                <tr key={log.id} className={`border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors ${i % 2 === 0 ? 'bg-slate-900/20' : ''}`}>
                  <td className="px-6 py-4 font-mono text-slate-300">{log.time}</td>
                  <td className="px-6 py-4 text-slate-300">{log.source}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 rounded bg-slate-800 text-xs text-slate-400">{log.lang}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className={`font-mono font-bold ${log.risk > 70 ? 'text-rose-400' : log.risk > 30 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {log.risk}%
                      </span>
                      {log.risk > 70 && <AlertTriangle className="w-4 h-4 text-rose-500" />}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-bold uppercase ${log.verdict === 'CLONED' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : log.verdict === 'SUSPICIOUS' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                      {log.verdict}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-400">{log.action}</td>
                  <td className="px-6 py-4 text-right">
                    <button className="p-2 hover:bg-slate-700 rounded-full transition-colors text-slate-400 hover:text-indigo-400">
                      <FileAudio className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
