"use client";

import { useState } from "react";
import { Phone, User, Activity, ShieldCheck, ShieldAlert, XCircle, ArrowRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskGauge } from "./RiskGauge";

export function CallSimulator() {
  const [activeCall, setActiveCall] = useState<null | 'genuine' | 'scam'>(null);

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-full p-6">
      {/* Left Column: Active Call Widget */}
      <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex flex-col">
        <h2 className="text-xl font-semibold mb-6 text-slate-200">Protected Telephony Stream</h2>
        
        <div className="mb-6 flex gap-3">
          <button 
            onClick={() => setActiveCall('genuine')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeCall === 'genuine' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
          >
            Simulate Genuine Call
          </button>
          <button 
            onClick={() => setActiveCall('scam')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeCall === 'scam' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
          >
            Simulate AI Scam Call
          </button>
          <button 
            onClick={() => setActiveCall(null)}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 ml-auto"
          >
            End Call
          </button>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-slate-700 rounded-xl bg-slate-800/30 p-8">
          {activeCall ? (
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center">
              <div className="w-24 h-24 rounded-full bg-slate-700 flex items-center justify-center mb-4 relative">
                <User className="w-10 h-10 text-slate-400" />
                <span className="absolute bottom-0 right-0 w-6 h-6 bg-emerald-500 rounded-full border-4 border-slate-900"></span>
              </div>
              <h3 className="text-2xl font-bold text-white mb-1">
                {activeCall === 'genuine' ? 'Rahul Kumar' : 'Unknown Caller'}
              </h3>
              <p className="text-slate-400 mb-6">
                {activeCall === 'genuine' ? 'Claimed: Axis Bank Manager' : 'Claimed: Family Member'}
              </p>
              
              <div className="flex items-center gap-4 bg-slate-900 px-6 py-3 rounded-full border border-slate-700 w-64 justify-center">
                <div className="flex gap-1 items-center h-4">
                  {[1,2,3,4,5].map(i => (
                    <motion.div 
                      key={i}
                      className="w-1 bg-emerald-400 rounded-full"
                      animate={{ height: ['20%', '100%', '40%'] }}
                      transition={{ repeat: Infinity, duration: 0.5 + Math.random(), ease: "easeInOut" }}
                    />
                  ))}
                </div>
                <span className="text-sm font-mono text-emerald-400">00:14</span>
              </div>
            </motion.div>
          ) : (
             <div className="text-slate-500 flex flex-col items-center gap-4">
               <Phone className="w-12 h-12 opacity-50" />
               <p>Awaiting incoming SIP stream...</p>
             </div>
          )}
        </div>
      </div>

      {/* Right Column: Decision Flow */}
      <div className="w-full lg:w-[500px] bg-slate-900/50 rounded-2xl border border-slate-800 p-6 backdrop-blur-sm shadow-xl flex flex-col">
        <h2 className="text-xl font-semibold mb-6 text-slate-200">Real-Time Decision Engine</h2>
        
        <div className="flex-1 flex flex-col justify-center space-y-6">
          <FlowStep 
            title="Audio Ingestion" 
            desc="Capturing 16kHz WebRTC stream"
            active={!!activeCall}
          />
          <ArrowRight className={`mx-auto w-6 h-6 ${activeCall ? 'text-indigo-500' : 'text-slate-700'}`} />
          
          <FlowStep 
            title="ONNX Inference" 
            desc="Extracting Mel-Spectrogram features"
            active={!!activeCall}
          />
          <ArrowRight className={`mx-auto w-6 h-6 ${activeCall ? 'text-indigo-500' : 'text-slate-700'}`} />
          
          <div className={`p-4 rounded-xl border ${activeCall === 'scam' ? 'bg-rose-500/10 border-rose-500/30' : activeCall === 'genuine' ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-slate-800/50 border-slate-700'}`}>
            <h4 className="font-semibold text-slate-200 flex items-center justify-between">
              Risk Assessment
              {activeCall === 'scam' && <ShieldAlert className="w-5 h-5 text-rose-500" />}
              {activeCall === 'genuine' && <ShieldCheck className="w-5 h-5 text-emerald-500" />}
            </h4>
            <div className="mt-4 flex justify-center scale-75 origin-top">
               <RiskGauge score={activeCall === 'scam' ? 92 : 12} verdict={activeCall === 'scam' ? 'CLONED' : activeCall === 'genuine' ? 'AUTHENTIC' : 'IDLE'} />
            </div>
          </div>
          
          <ArrowRight className={`mx-auto w-6 h-6 ${activeCall ? 'text-indigo-500' : 'text-slate-700'}`} />
          
          <div className="grid grid-cols-3 gap-2">
            <div className={`p-3 rounded-lg text-center text-xs font-bold border transition-colors ${activeCall === 'genuine' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50' : 'bg-slate-800/50 text-slate-500 border-slate-700'}`}>ALLOW</div>
            <div className={`p-3 rounded-lg text-center text-xs font-bold border transition-colors ${activeCall === 'scam' ? 'bg-amber-500/20 text-amber-400 border-amber-500/50' : 'bg-slate-800/50 text-slate-500 border-slate-700'}`}>CHALLENGE</div>
            <div className={`p-3 rounded-lg text-center text-xs font-bold border transition-colors ${activeCall === 'scam' ? 'bg-rose-500/20 text-rose-400 border-rose-500/50' : 'bg-slate-800/50 text-slate-500 border-slate-700'}`}>TERMINATE</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FlowStep({ title, desc, active }: { title: string, desc: string, active: boolean }) {
  return (
    <div className={`p-4 rounded-xl border flex items-center gap-4 transition-colors duration-500 ${active ? 'bg-indigo-900/20 border-indigo-500/30' : 'bg-slate-800/50 border-slate-700'}`}>
      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${active ? 'bg-indigo-500/20 text-indigo-400' : 'bg-slate-700 text-slate-500'}`}>
        <Activity className="w-5 h-5" />
      </div>
      <div>
        <h4 className={`font-semibold ${active ? 'text-indigo-100' : 'text-slate-400'}`}>{title}</h4>
        <p className={`text-sm ${active ? 'text-indigo-300' : 'text-slate-600'}`}>{desc}</p>
      </div>
    </div>
  )
}
