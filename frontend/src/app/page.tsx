"use client";

import { useState } from "react";
import { LiveDetector } from "@/components/LiveDetector";
import { CallSimulator } from "@/components/CallSimulator";
import { AuditLogs } from "@/components/AuditLogs";
import { Activity, Radio, Phone, History, Cpu } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Home() {
  const [activeTab, setActiveTab] = useState("live");

  const tabs = [
    { id: "live", label: "Live Detector", icon: Radio },
    { id: "telephony", label: "Telephony Gateway", icon: Phone },
    { id: "audit", label: "Audit Logs", icon: History },
    { id: "telemetry", label: "Model Telemetry", icon: Cpu },
  ];

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)]">
      {/* Sub Navigation */}
      <div className="border-b border-slate-800/50 bg-slate-950/30">
        <div className="flex px-6 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors relative whitespace-nowrap ${
                  isActive ? "text-emerald-400" : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {isActive && (
                  <motion.div
                    layoutId="activeTabIndicator"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="h-full"
          >
            {activeTab === "live" && <LiveDetector />}
            {activeTab === "telephony" && <CallSimulator />}
            {activeTab === "audit" && <AuditLogs />}
            {activeTab === "telemetry" && (
              <div className="flex h-full items-center justify-center p-6 text-slate-500 flex-col gap-4">
                <Activity className="w-16 h-16 opacity-20" />
                <p>Model Telemetry visualization module under construction...</p>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
