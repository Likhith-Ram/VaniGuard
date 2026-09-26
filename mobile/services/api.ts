/**
 * services/api.ts — VaniGuard API client.
 *
 * All communication with the FastAPI backend goes through this module.
 * The mobile app should never make raw fetch() calls directly.
 */

// ── Configuration ────────────────────────────────────────────────────────
// Change this to your deployed server URL when not running locally.
// For local development with Expo Go:
//   - Android emulator: use 10.0.2.2 (maps to host's localhost)
//   - Physical device: use your computer's LAN IP (e.g. 192.168.1.x)
//   - iOS simulator: use localhost
import { Platform } from 'react-native';

const getBaseUrl = (): string => {
  // When running on web, use localhost directly
  if (Platform.OS === 'web') return 'http://localhost:8000';
  // Android emulator maps 10.0.2.2 to host localhost
  if (Platform.OS === 'android') return 'http://10.0.2.2:8000';
  // iOS simulator can use localhost
  return 'http://localhost:8000';
};

// You can override this with your deployed server URL
export const API_BASE_URL = getBaseUrl();

// ── Types ────────────────────────────────────────────────────────────────

export interface DetectionResult {
  filename: string;
  verdict: string;
  probability: number;
  confidence_pct: number;
  risk_band: string;
  risk_level: 'high' | 'suspicious' | 'uncertain' | 'low';
  duration_s: number;
  is_ai: boolean;
  model_loaded: boolean;
}

export interface HistoryEntry {
  id: number;
  timestamp: string;
  filename: string;
  verdict: string;
  confidence_pct: number;
  risk_band: string;
  probability: number;
}

export interface HistoryResponse {
  total: number;
  entries: HistoryEntry[];
}

export interface HistoryStats {
  total: number;
  ai_detected: number;
  human_detected: number;
  uncertain: number;
  ai_detection_rate: number;
  avg_confidence: number;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  model_loaded: boolean;
  model_error: string | null;
  version: string;
  uptime_s: number;
}

// ── API Error ────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public statusCode: number,
    public detail: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

// ── Helper ───────────────────────────────────────────────────────────────

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // response body isn't JSON
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

// ── API Functions ────────────────────────────────────────────────────────

/**
 * Upload an audio file for AI voice detection.
 */
export async function detectAudio(
  fileUri: string,
  filename: string,
  mimeType: string = 'audio/wav',
): Promise<DetectionResult> {
  const formData = new FormData();

  // React Native FormData expects this shape for file uploads
  formData.append('file', {
    uri: fileUri,
    name: filename,
    type: mimeType,
  } as any);

  const response = await fetch(`${API_BASE_URL}/api/detect`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — fetch will add multipart boundary automatically
  });

  return handleResponse<DetectionResult>(response);
}

/**
 * Get detection history (paginated, newest first).
 */
export async function getHistory(
  limit: number = 50,
  offset: number = 0,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`${API_BASE_URL}/api/history?${params}`);
  return handleResponse<HistoryResponse>(response);
}

/**
 * Get aggregate detection statistics.
 */
export async function getStats(): Promise<{ stats: HistoryStats }> {
  const response = await fetch(`${API_BASE_URL}/api/stats`);
  return handleResponse<{ stats: HistoryStats }>(response);
}

/**
 * Clear all detection history.
 */
export async function clearHistory(): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/history`, { method: 'DELETE' });
  return handleResponse<{ message: string }>(response);
}

/**
 * Health check — verify the server and model are running.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  return handleResponse<HealthResponse>(response);
}
