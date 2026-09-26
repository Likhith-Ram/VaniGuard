/**
 * app/(tabs)/analyze.tsx — Analyze screen.
 *
 * Two modes:
 *   1. Upload an audio file from device storage
 *   2. Record audio from the microphone
 *
 * After recording/uploading, sends audio to the API and displays results.
 */

import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, {
  FadeIn,
  FadeInDown,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { Audio } from 'expo-av';
import * as DocumentPicker from 'expo-document-picker';

import { VerdictBanner } from '@/components/VerdictBanner';
import { brand, radius, spacing, status, surface, text as textColors } from '@/constants/Colors';
import { detectAudio, type DetectionResult } from '@/services/api';

type Mode = 'idle' | 'recording' | 'uploading' | 'analyzing';

export default function AnalyzeScreen() {
  const [mode, setMode] = useState<Mode>('idle');
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Pulse animation for recording indicator
  const pulseOpacity = useSharedValue(1);
  const pulseStyle = useAnimatedStyle(() => ({
    opacity: pulseOpacity.value,
  }));

  const resetState = () => {
    setResult(null);
    setError(null);
    setMode('idle');
    setRecordingDuration(0);
  };

  // ── File Upload ──────────────────────────────────────────────────────

  const handleUpload = async () => {
    try {
      resetState();
      const pickerResult = await DocumentPicker.getDocumentAsync({
        type: ['audio/*'],
        copyToCacheDirectory: true,
      });

      if (pickerResult.canceled) return;

      const file = pickerResult.assets[0];
      if (!file) return;

      // Validate size (50 MB)
      if (file.size && file.size > 50 * 1024 * 1024) {
        setError('File too large. Maximum size is 50 MB.');
        return;
      }

      setMode('analyzing');
      const detection = await detectAudio(
        file.uri,
        file.name || 'audio.wav',
        file.mimeType || 'audio/wav',
      );
      setResult(detection);
      setMode('idle');
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to analyze audio');
      setMode('idle');
    }
  };

  // ── Microphone Recording ─────────────────────────────────────────────

  const startRecording = async () => {
    try {
      resetState();

      // Request permissions
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Permission Required',
          'Microphone access is needed to record audio for analysis.',
        );
        return;
      }

      // Configure audio
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Start recording in WAV format for best compatibility
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );
      recordingRef.current = recording;
      setMode('recording');

      // Start pulse animation
      pulseOpacity.value = withRepeat(
        withTiming(0.3, { duration: 800 }),
        -1,
        true,
      );

      // Duration timer
      setRecordingDuration(0);
      timerRef.current = setInterval(() => {
        setRecordingDuration(d => d + 1);
      }, 1000);
    } catch (err: any) {
      setError('Failed to start recording: ' + (err.message || err));
      setMode('idle');
    }
  };

  const stopRecording = async () => {
    try {
      // Stop timer
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // Stop pulse
      pulseOpacity.value = 1;

      const recording = recordingRef.current;
      if (!recording) return;

      setMode('analyzing');
      await recording.stopAndUnloadAsync();
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

      const uri = recording.getURI();
      recordingRef.current = null;

      if (!uri) {
        setError('Recording failed — no audio file created.');
        setMode('idle');
        return;
      }

      // Send to API
      const detection = await detectAudio(uri, 'recording.m4a', 'audio/m4a');
      setResult(detection);
      setMode('idle');
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to analyze recording');
      setMode('idle');
    }
  };

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.heading}>Analyze Audio</Text>
      <Text style={styles.subtitle}>
        Upload a file or record from the microphone to detect AI-generated voice.
      </Text>

      {/* Action Buttons */}
      {mode === 'idle' && !result && (
        <Animated.View entering={FadeInDown.duration(500)} style={styles.actions}>
          {/* Upload Button */}
          <Pressable
            style={({ pressed }) => [
              styles.actionCard,
              pressed && styles.actionPressed,
            ]}
            onPress={handleUpload}
          >
            <Text style={styles.actionIcon}>📁</Text>
            <Text style={styles.actionTitle}>Upload File</Text>
            <Text style={styles.actionDesc}>
              WAV, MP3, OGG, FLAC, M4A{'\n'}Max 50 MB
            </Text>
          </Pressable>

          {/* Record Button */}
          <Pressable
            style={({ pressed }) => [
              styles.actionCard,
              pressed && styles.actionPressed,
            ]}
            onPress={startRecording}
          >
            <Text style={styles.actionIcon}>🎤</Text>
            <Text style={styles.actionTitle}>Record Audio</Text>
            <Text style={styles.actionDesc}>
              Record from mic{'\n'}Minimum 0.5 seconds
            </Text>
          </Pressable>
        </Animated.View>
      )}

      {/* Recording State */}
      {mode === 'recording' && (
        <Animated.View entering={FadeIn.duration(400)} style={styles.recordingContainer}>
          <Animated.View style={[styles.recordingDot, pulseStyle]} />
          <Text style={styles.recordingLabel}>Recording…</Text>
          <Text style={styles.recordingTimer}>{formatDuration(recordingDuration)}</Text>
          <Text style={styles.recordingHint}>
            Record at least 0.5 seconds. Longer clips give better accuracy.
          </Text>
          <Pressable
            style={({ pressed }) => [
              styles.stopButton,
              pressed && { opacity: 0.8 },
            ]}
            onPress={stopRecording}
          >
            <View style={styles.stopIcon} />
            <Text style={styles.stopText}>Stop & Analyze</Text>
          </Pressable>
        </Animated.View>
      )}

      {/* Analyzing State */}
      {(mode === 'analyzing' || mode === 'uploading') && (
        <View style={styles.analyzingContainer}>
          <ActivityIndicator size="large" color={brand.primary} />
          <Text style={styles.analyzingText}>Analyzing audio…</Text>
          <Text style={styles.analyzingHint}>
            Decoding → Feature extraction → AI inference
          </Text>
        </View>
      )}

      {/* Error */}
      {error && (
        <Animated.View entering={FadeIn.duration(300)} style={styles.errorBanner}>
          <Text style={styles.errorText}>❌ {error}</Text>
          <Pressable style={styles.retryButton} onPress={resetState}>
            <Text style={styles.retryText}>Try Again</Text>
          </Pressable>
        </Animated.View>
      )}

      {/* Results */}
      {result && (
        <>
          <VerdictBanner result={result} />
          <Pressable
            style={({ pressed }) => [
              styles.newAnalysisButton,
              pressed && { opacity: 0.8 },
            ]}
            onPress={resetState}
          >
            <Text style={styles.newAnalysisText}>🔄 New Analysis</Text>
          </Pressable>
        </>
      )}

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: surface.background },
  content: { padding: spacing.md },

  heading: {
    fontSize: 28,
    fontWeight: '700',
    color: textColors.primary,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 14,
    color: textColors.secondary,
    marginTop: spacing.xs,
    marginBottom: spacing.lg,
    lineHeight: 20,
  },

  // Action cards
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  actionCard: {
    flex: 1,
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.lg,
    alignItems: 'center',
  },
  actionPressed: {
    backgroundColor: surface.elevated,
    transform: [{ scale: 0.97 }],
  },
  actionIcon: { fontSize: 40, marginBottom: spacing.sm },
  actionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: textColors.primary,
    marginBottom: spacing.xs,
  },
  actionDesc: {
    fontSize: 12,
    color: textColors.muted,
    textAlign: 'center',
    lineHeight: 18,
  },

  // Recording
  recordingContainer: {
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: status.error,
    padding: spacing.xl,
    alignItems: 'center',
  },
  recordingDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: status.error,
    marginBottom: spacing.md,
  },
  recordingLabel: {
    fontSize: 18,
    fontWeight: '700',
    color: status.error,
    marginBottom: spacing.xs,
  },
  recordingTimer: {
    fontSize: 48,
    fontWeight: '700',
    color: textColors.primary,
    fontVariant: ['tabular-nums'],
    marginBottom: spacing.sm,
  },
  recordingHint: {
    fontSize: 13,
    color: textColors.muted,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  stopButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: status.error,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  stopIcon: {
    width: 16,
    height: 16,
    borderRadius: 3,
    backgroundColor: '#fff',
  },
  stopText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },

  // Analyzing
  analyzingContainer: {
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: brand.primary,
    padding: spacing.xl,
    alignItems: 'center',
  },
  analyzingText: {
    fontSize: 18,
    fontWeight: '600',
    color: textColors.primary,
    marginTop: spacing.md,
  },
  analyzingHint: {
    fontSize: 13,
    color: textColors.muted,
    marginTop: spacing.xs,
  },

  // Error
  errorBanner: {
    backgroundColor: '#431407',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: '#F97316',
    padding: spacing.lg,
    alignItems: 'center',
  },
  errorText: {
    color: '#FDBA74',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  retryButton: {
    backgroundColor: '#F97316',
    borderRadius: radius.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  retryText: { color: '#fff', fontWeight: '700', fontSize: 14 },

  // New analysis
  newAnalysisButton: {
    backgroundColor: brand.primary,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  newAnalysisText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
