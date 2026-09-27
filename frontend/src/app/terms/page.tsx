import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description: "VaniGuard terms of service — acceptable use, no warranty, liability limits, and IP rights.",
};

const TERMS = [
  {
    title: "1. Acceptance of Terms",
    body: "By using VaniGuard, you agree to these Terms & Conditions. If you disagree with any part, please discontinue use immediately.",
  },
  {
    title: "2. Use of the Service",
    body: "VaniGuard is provided as a research and demonstration tool for detecting AI-generated voices. You agree to use it lawfully and not to upload audio belonging to third parties without authorization.",
  },
  {
    title: "3. No Warranty",
    body: 'VaniGuard is provided "as is" without warranty of any kind. Detection results are probabilistic and should not be the sole basis for legal, medical, or security decisions.',
  },
  {
    title: "4. Limitation of Liability",
    body: "To the fullest extent permitted by law, the VaniGuard team shall not be liable for any indirect, incidental, or consequential damages arising from your use of the service.",
  },
  {
    title: "5. Intellectual Property",
    body: "The VaniGuard source code is MIT-licensed. The trained model weights (vaniguard.onnx) are proprietary and may not be redistributed without explicit permission.",
  },
  {
    title: "6. Changes to Terms",
    body: "We reserve the right to update these terms at any time. Continued use of VaniGuard after changes constitutes acceptance.",
  },
];

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold mb-2">Terms &amp; Conditions</h1>
      <p className="text-slate-500 mb-8">Last updated: 27 September 2026</p>
      {TERMS.map(({ title, body }) => (
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
