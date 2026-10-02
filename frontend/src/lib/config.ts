/**
 * lib/config.ts — Centralised environment configuration for VaniGuard frontend.
 *
 * All API URLs are derived from a single NEXT_PUBLIC_API_BASE environment
 * variable. No component should hard-code "localhost:8000" or any other host.
 *
 * HTTP → WS  derivation is done here so there is exactly one place to update
 * when the backend host changes.
 */

/**
 * The base HTTP URL of the FastAPI backend.
 *
 * Set NEXT_PUBLIC_API_BASE in your .env.local (or deployment env) to the
 * full origin of the backend, e.g.:
 *
 *   NEXT_PUBLIC_API_BASE=https://api.vaniguard.example.com
 *
 * Defaults to http://localhost:8000 for local development only.
 */
export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/**
 * Derive the WebSocket base URL from the HTTP base URL.
 *
 * http://...  →  ws://...
 * https://... →  wss://...
 *
 * This ensures production automatically uses WSS (encrypted) when the API
 * is served over HTTPS, without any manual changes.
 */
export const WS_BASE: string = API_BASE.replace(/^http/, "ws");

/**
 * The API key sent with every authenticated request.
 *
 * Set NEXT_PUBLIC_API_KEY in your environment.
 * For HTTP requests: sent as the X-API-Key header.
 * For WebSocket: sent as the first text message after connection opens.
 *
 * WARNING: NEXT_PUBLIC_* variables are embedded into the client bundle.
 * This is intentional — API keys protect the backend from anonymous abuse,
 * not from users who inspect the page source. For higher security, move
 * API calls to Next.js server-side routes that hold the key server-side.
 */
export const API_KEY: string = process.env.NEXT_PUBLIC_API_KEY ?? "";
