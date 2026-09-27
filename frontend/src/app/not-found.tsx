import Link from "next/link";
import { ShieldX } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-24 text-center">
      <ShieldX className="w-20 h-20 text-rose-500/40 mb-6" />
      <h1 className="text-8xl font-black bg-gradient-to-br from-rose-400 to-rose-600 bg-clip-text text-transparent mb-4">
        404
      </h1>
      <p className="text-slate-400 text-lg max-w-md mb-8">
        This page doesn&apos;t exist — but our AI voice detection engine is
        still on guard.
      </p>
      <Link
        href="/"
        aria-label="Go back to the VaniGuard dashboard"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold hover:bg-emerald-500/20 transition-colors"
      >
        ← Back to Dashboard
      </Link>
    </div>
  );
}
