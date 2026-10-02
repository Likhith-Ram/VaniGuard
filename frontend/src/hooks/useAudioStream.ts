/**
 * hooks/useAudioStream.ts — Real-time microphone → WebSocket streaming hook.
 *
 * Architecture notes
 * ------------------
 * 1. Microphone audio is ANALYZED but NEVER routed to the speakers.
 *    The audio graph is:  mic → ScriptProcessor → (PCM to WebSocket)
 *    The ScriptProcessor is intentionally NOT connected to audioCtx.destination.
 *    Connecting it would cause audio feedback (howling).  See MED-12.
 *
 * 2. WebSocket authentication is performed by sending the API key as the
 *    first text message immediately after the connection is accepted.
 *    This avoids putting the key in the URL query string (which is logged
 *    by proxies, load balancers, and browser history).  See HIGH-04.
 *
 * 3. The onclose handler guards against a re-entrant close loop.
 *    stopStream() closes the WebSocket; that triggers onclose; without a
 *    guard, onclose would call stopStream() again → double-close.  See HIGH-26.
 *
 * 4. All URLs come from the central lib/config module — no hardcoded hosts.
 *    See HIGH-02 / HIGH-04.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { WS_BASE, API_KEY } from "@/lib/config";

export type StreamResult = {
  window_index: number;
  prob_ai: number;
  verdict: string;
  risk_band: string;
  risk_css: string;
  status_level: string;
  status_confidence: number;
};

type WebkitWindow = typeof window & { webkitAudioContext?: typeof AudioContext };

export function useAudioStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [latestResult, setLatestResult] = useState<StreamResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  // Guard flag: prevents the onclose handler from calling stopStream() when
  // stopStream() itself was the one that closed the WebSocket.  Without this
  // guard we get a re-entrant loop: stopStream → ws.close → onclose → stopStream.
  // See HIGH-26.
  const isStoppingRef = useRef(false);

  // Stable ref to stopStream so startStream can call it without stale closures.
  const stopStreamRef = useRef<() => void>(() => {});

  const stopStream = useCallback(() => {
    // Set the guard BEFORE closing anything so the onclose handler knows
    // it was triggered intentionally.
    isStoppingRef.current = true;
    setIsStreaming(false);

    // Disconnect and release the ScriptProcessorNode.
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current.onaudioprocess = null;
      scriptProcessorRef.current = null;
    }

    // Disconnect the MediaStreamAudioSourceNode.
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    // Stop all microphone tracks — releases the hardware mic lock.
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Close and release the AudioContext.
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Close the WebSocket if it is still open.
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null; // clear ref BEFORE close to prevent onclose acting on it
      ws.close();
    }

    // Reset the guard only after all cleanup is complete.
    isStoppingRef.current = false;
  }, []);

  // Keep the ref up to date on every render.
  useEffect(() => {
    stopStreamRef.current = stopStream;
  }, [stopStream]);

  const startStream = useCallback(async () => {
    try {
      setError(null);

      // ── 1. Open WebSocket connection ────────────────────────────────────
      const ws = new WebSocket(`${WS_BASE}/stream`);
      wsRef.current = ws;

      ws.onopen = () => {
        // ── 2. Authenticate immediately after connection opens ───────────
        // We send the API key as the first text message — NOT in the URL.
        // URL query params are logged by proxies and visible in browser history.
        if (API_KEY) {
          ws.send(API_KEY);
        } else {
          // If no key is configured, send an empty string; the backend will
          // reject it with close code 4003.  This surfaces the misconfiguration
          // clearly rather than leaving the stream silently unauthenticated.
          ws.send("");
        }
        setIsStreaming(true);
      };

      ws.onmessage = (event) => {
        try {
          const result: StreamResult = JSON.parse(event.data as string);
          setLatestResult(result);
        } catch (e) {
          console.error("Failed to parse WebSocket message", e);
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection failed. Ensure the backend is running.");
        stopStreamRef.current();
      };

      ws.onclose = (event) => {
        // Only call stopStream if the close was external (server-side or network
        // drop) — not when WE initiated the close via stopStream().
        // Without this guard, stopStream() → ws.close() → onclose → stopStream()
        // causes a re-entrant loop.  See HIGH-26.
        if (!isStoppingRef.current) {
          if (event.code === 4003) {
            setError("Authentication failed. Check your NEXT_PUBLIC_API_KEY.");
          }
          stopStreamRef.current();
        }
      };

      // ── 3. Request microphone access ────────────────────────────────────
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // ── 4. Build the audio analysis graph ──────────────────────────────
      const AudioContextClass =
        window.AudioContext || (window as WebkitWindow).webkitAudioContext;
      const audioCtx = new AudioContextClass({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      // Source node: wraps the live microphone MediaStream.
      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessorNode: captures 4096-sample (~256 ms at 16 kHz) PCM
      // buffers and sends them to the WebSocket.
      // Buffer size 4096, 1 input channel, 1 output channel.
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      scriptProcessorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0); // Float32Array
          wsRef.current.send(inputData.buffer);
        }
      };

      // CRITICAL: connect source → processor for PCM capture.
      // Do NOT connect processor → audioCtx.destination.
      // Connecting to destination would feed the microphone back through the
      // speakers, causing audio feedback / howling.  See MED-12.
      source.connect(processor);
      // processor is intentionally left disconnected from destination —
      // the onaudioprocess callback fires regardless of destination connection.

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not access microphone";
      console.error("Failed to start audio stream:", err);
      setError(msg);
      stopStreamRef.current();
    }
  }, []);

  return {
    isStreaming,
    latestResult,
    error,
    startStream,
    stopStream,
  };
}
