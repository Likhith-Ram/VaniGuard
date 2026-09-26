import { useState, useRef, useCallback } from "react";

export type StreamResult = {
  window_index: number;
  prob_ai: number;
  verdict: string;
  risk_band: string;
  risk_css: string;
  status_level: string;
  status_confidence: number;
};

export function useAudioStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [latestResult, setLatestResult] = useState<StreamResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);

  const startStream = useCallback(async () => {
    try {
      setError(null);
      // 1. Open WebSocket connection
      wsRef.current = new WebSocket("ws://localhost:8000/stream");
      
      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        setIsStreaming(true);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const result: StreamResult = JSON.parse(event.data);
          setLatestResult(result);
        } catch (e) {
          console.error("Failed to parse websocket message", e);
        }
      };

      wsRef.current.onerror = (e) => {
        console.error("WebSocket error", e);
        setError("WebSocket connection failed. Ensure backend is running.");
        stopStream();
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected");
        stopStream();
      };

      // 2. Get Microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        } 
      });
      mediaStreamRef.current = stream;

      // 3. Setup Web Audio API to capture 16kHz PCM float32
      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      
      // buffer size 4096 (approx 256ms of audio at 16kHz)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      scriptProcessorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0); // Float32Array
          // We need to send raw float32 bytes
          // We can just send the buffer of the Float32Array
          wsRef.current.send(inputData.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

    } catch (err: any) {
      console.error("Failed to start audio stream:", err);
      setError(err.message || "Could not access microphone");
      stopStream();
    }
  }, []);

  const stopStream = useCallback(() => {
    setIsStreaming(false);
    
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  return {
    isStreaming,
    latestResult,
    error,
    startStream,
    stopStream
  };
}
