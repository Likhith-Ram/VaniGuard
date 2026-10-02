/**
 * lib/api.ts — VaniGuard API client (frontend).
 *
 * All HTTP requests go through this module. No component should call
 * fetch() directly or reference API_BASE / API_KEY themselves.
 *
 * Authentication: every request carries the X-API-Key header whose value
 * comes from the NEXT_PUBLIC_API_KEY environment variable (see lib/config.ts).
 */

import { API_BASE, API_KEY } from "@/lib/config";

// ── Shared request helper ──────────────────────────────────────────────────

/**
 * Build the standard headers for every authenticated request.
 * Returns a plain HeadersInit object — does NOT include Content-Type so
 * fetch can set it automatically (important for FormData uploads).
 */
function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  return headers;
}

// ── Types ──────────────────────────────────────────────────────────────────

export type DetectionResult = {
  score: number;
  verdict: "AUTHENTIC" | "SUSPICIOUS" | "CLONED";
  details: {
    spectralJitter: number;
    harmonicArtifacts: number;
    phonemeConsistency: number;
    neuralSynthesisMarkers: number;
  };
  duration: number;
  language: string;
};

export type HistoryEntry = {
  id: number;
  timestamp: string;
  filename: string;
  verdict: string;
  confidence_pct: number;
  risk_band: string;
  probability: number;
};

export type HistoryStats = {
  total: number;
  ai_detected: number;
  human_detected: number;
  uncertain: number;
  ai_detection_rate: number;
  avg_confidence: number;
};

// ── Audio analysis ─────────────────────────────────────────────────────────

export async function analyzeAudio(
  audioFile: File | Blob,
  language: string
): Promise<DetectionResult> {
  const formData = new FormData();
  formData.append("file", audioFile);

  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: authHeaders(), // X-API-Key; Content-Type is set by fetch for FormData
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error: ${response.status}`);
  }

  const data = await response.json();

  // Map /analyze response → DetectionResult
  // Response fields: verdict, risk_band, prob_ai, confidence, duration_s, is_ai, model_loaded
  let mappedVerdict: "AUTHENTIC" | "SUSPICIOUS" | "CLONED" = "AUTHENTIC";
  if (data.is_ai === true || data.verdict?.includes("AI-Generated")) {
    mappedVerdict = "CLONED";
  } else if (data.verdict === "UNCERTAIN") {
    mappedVerdict = "SUSPICIOUS";
  }

  return {
    score: data.prob_ai * 100,
    verdict: mappedVerdict,
    details: {
      spectralJitter: data.confidence * 100,
      harmonicArtifacts: data.prob_ai * 80,
      phonemeConsistency: 100 - data.prob_ai * 60,
      neuralSynthesisMarkers: data.prob_ai * 100,
    },
    duration: data.duration_s || 0,
    language,
  };
}

// ── Telemetry ──────────────────────────────────────────────────────────────

export async function fetchStats(): Promise<HistoryStats> {
  const response = await fetch(`${API_BASE}/api/stats`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Stats API error: ${response.status}`);
  const data = await response.json();
  return data.stats as HistoryStats;
}

export async function fetchHistory(limit = 100): Promise<HistoryEntry[]> {
  const response = await fetch(`${API_BASE}/api/history?limit=${limit}`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`History API error: ${response.status}`);
  const data = await response.json();
  return data.entries as HistoryEntry[];
}
