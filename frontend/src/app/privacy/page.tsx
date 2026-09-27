import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How VaniGuard handles your data — what we collect, how we use it, and your rights.",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-slate-500 mb-8">Last updated: 27 September 2026</p>

      {[
        {
          title: "1. What We Collect",
          body: "VaniGuard processes audio files you upload solely to perform AI-voice detection. We do not store raw audio bytes after analysis. We store only the detection result (verdict, confidence score, risk band, timestamp) in a local history log.",
        },
        {
          title: "2. How We Use Your Data",
          body: "Detection history is stored locally on the server and used solely to display past results. We do not share, sell, or transmit your audio or results to any third party.",
        },
        {
          title: "3. Cookies & Analytics",
          body: "VaniGuard uses no third-party tracking cookies. Anonymous usage analytics may be collected by the hosting provider (Streamlit Cloud) subject to their own privacy policy.",
        },
        {
          title: "4. Data Retention",
          body: "Detection history is retained until you choose to clear it. You may delete all records at any time from the History page.",
        },
        {
          title: "5. Contact",
          body: "For privacy questions, contact us at privacy@vaniguard.ai",
        },
      ].map(({ title, body }) => (
        <section
          key={title}
          className="mb-6 p-6 rounded-xl border border-slate-800 bg-slate-900/40"
        >
          <h2 className="text-lg font-semibold mb-3 text-emerald-400">{title}</h2>
          <p className="text-slate-400 leading-relaxed">{body}</p>
        </section>
      ))}
    </div>
  );
}
