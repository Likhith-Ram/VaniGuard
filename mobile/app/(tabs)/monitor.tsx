/**
 * app/(tabs)/monitor.tsx — Live Monitor screen.
 *
 * Continuously records 3-second audio chunks from the microphone
 * and sends each to the API for analysis. Displays a scrolling
 * feed of real-time verdicts — the SIH demo killer feature.
 *
 * Usage: Put a phone call on speaker, start monitoring.
 */

import React, { useCallback, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, {
  FadeIn,
  FadeInRight,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { Audio } from 'expo-av';

import { StatusDot } from '@/components/StatusDot';
import { brand, radius, risk, spacing, status, surface, text as textColors } from '@/constants/Colors';
import { detectAudio, type DetectionResult } from '@/services/api';

// Duration of each recording chunk in milliseconds
const CHUNK_DURATION_MS = 3000;

interface MonitorEntry {
  id: string;
  timestamp: string;
  result: DetectionResult;
}

export default function MonitorScreen() {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [entries, setEntries] = useState<MonitorEntry[]>([]);
  const [chunksAnalyzed, setChunksAnalyzed] = useState(0);
  const [aiDetected, setAiDetected] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const isMonitoringRef = useRef(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  // Pulse animation
  const pulseOpacity = useSharedValue(1);
  const pulseStyle = useAnimatedStyle(() => ({
    opacity: pulseOpacity.value,
  }));

  const startMonitoring = async () => {
    try {
      setError(null);
      setEntries([]);
      setChunksAnalyzed(0);
      setAiDetected(0);

      // Request mic permission
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Permission Required',
          'Microphone access is needed for live monitoring.',
        );
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      setIsMonitoring(true);
      isMonitoringRef.current = true;

      // Start pulse
      pulseOpacity.value = withRepeat(
        withTiming(0.3, { duration: 600 }),
        -1,
        true,
      );

      // Start the recording loop
      recordLoop();
    } catch (err: any) {
      setError('Failed to start monitoring: ' + (err.message || err));
    }
  };

  const recordLoop = async () => {
    while (isMonitoringRef.current) {
      try {
        // Record a chunk
        const { recording } = await Audio.Recording.createAsync(
          Audio.RecordingOptionsPresets.HIGH_QUALITY,
        );
        recordingRef.current = recording;

        // Wait for chunk duration
        await new Promise(resolve => setTimeout(resolve, CHUNK_DURATION_MS));

        // Check if still monitoring (user might have stopped during sleep)
        if (!isMonitoringRef.current) {
          try {
            await recording.stopAndUnloadAsync();
          } catch { /* ignore */ }
          break;
        }

        // Stop and get URI
        await recording.stopAndUnloadAsync();
        const uri = recording.getURI();
        recordingRef.current = null;

        if (!uri) continue;

        // Analyze (don't await — fire and forget for speed)
        analyzeChunk(uri);
      } catch (err: any) {
        // If recording fails, wait and retry
        if (isMonitoringRef.current) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
    }
  };

  const analyzeChunk = async (uri: string) => {
    try {
      const result = await detectAudio(uri, 'monitor_chunk.m4a', 'audio/m4a');

      setChunksAnalyzed(c => c + 1);
      if (result.is_ai) {
        setAiDetected(a => a + 1);
      }

      const entry: MonitorEntry = {
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString(),
        result,
      };

      setEntries(prev => [entry, ...prev].slice(0, 50)); // Keep last 50
    } catch {
      // Silently skip failed chunks
    }
  };

  const stopMonitoring = async () => {
    isMonitoringRef.current = false;
    setIsMonitoring(false);
    pulseOpacity.value = 1;

    // Stop any active recording
    if (recordingRef.current) {
      try {
        await recordingRef.current.stopAndUnloadAsync();
      } catch { /* ignore */ }
      recordingRef.current = null;
    }

    await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
  };

  const getRiskColors = (riskLevel: string) => {
    switch (riskLevel) {
      case 'high': return risk.high;
      case 'suspicious': return risk.suspicious;
      case 'uncertain': return risk.uncertain;
      default: return risk.low;
    }
  };

  const renderEntry = useCallback(({ item, index }: { item: MonitorEntry; index: number }) => {
    const riskTheme = getRiskColors(item.result.risk_level);
    return (
      <Animated.View
        entering={FadeInRight.delay(index * 50).duration(300)}
        style={[styles.entry, { borderLeftColor: riskTheme.border }]}
      >
        <View style={styles.entryHeader}>
          <Text style={styles.entryTime}>{item.timestamp}</Text>
          <View style={[styles.entryBadge, { backgroundColor: riskTheme.bg }]}>
            <Text style={[styles.entryBadgeText, { color: riskTheme.text }]}>
              {item.result.verdict}
            </Text>
          </View>
        </View>
        <View style={styles.entryMetrics}>
          <Text style={styles.entryMetric}>
            AI: {(item.result.probability * 100).toFixed(1)}%
          </Text>
          <Text style={styles.entryMetric}>
            Conf: {item.result.confidence_pct.toFixed(1)}%
          </Text>
        </View>
      </Animated.View>
    );
  }, []);

  return (
    <View style={styles.container}>
      {/* Header Info */}
      <View style={styles.header}>
        <Text style={styles.heading}>🛡️ Live Monitor</Text>
        <Text style={styles.subtitle}>
          Continuously records 3-second chunks and analyzes each for AI-generated voice.
          Put a call on speaker to monitor in real time.
        </Text>
      </View>

      {/* Controls */}
      <View style={styles.controls}>
        {!isMonitoring ? (
          <Pressable
            style={({ pressed }) => [
              styles.startButton,
              pressed && { opacity: 0.8, transform: [{ scale: 0.97 }] },
            ]}
            onPress={startMonitoring}
          >
            <Text style={styles.startIcon}>🎤</Text>
            <Text style={styles.startText}>Start Monitoring</Text>
          </Pressable>
        ) : (
          <View style={styles.monitoringHeader}>
            <Animated.View style={[styles.liveDot, pulseStyle]} />
            <Text style={styles.liveText}>LIVE MONITORING</Text>
            <Pressable
              style={({ pressed }) => [
                styles.stopBtn,
                pressed && { opacity: 0.8 },
              ]}
              onPress={stopMonitoring}
            >
              <Text style={styles.stopBtnText}>■ Stop</Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* Stats Bar */}
      {(isMonitoring || entries.length > 0) && (
        <View style={styles.statsBar}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{chunksAnalyzed}</Text>
            <Text style={styles.statLabel}>Chunks</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, aiDetected > 0 && { color: risk.high.text }]}>
              {aiDetected}
            </Text>
            <Text style={styles.statLabel}>AI Alerts</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {chunksAnalyzed > 0 ? `${((aiDetected / chunksAnalyzed) * 100).toFixed(0)}%` : '—'}
            </Text>
            <Text style={styles.statLabel}>AI Rate</Text>
          </View>
        </View>
      )}

      {/* Error */}
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Feed */}
      {entries.length > 0 ? (
        <FlatList
          data={entries}
          renderItem={renderEntry}
          keyExtractor={item => item.id}
          contentContainerStyle={{ padding: spacing.md, paddingTop: 0 }}
          showsVerticalScrollIndicator={false}
        />
      ) : isMonitoring ? (
        <View style={styles.waiting}>
          <ActivityIndicator size="small" color={brand.primary} />
          <Text style={styles.waitingText}>Recording first chunk…</Text>
        </View>
      ) : (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>🛡️</Text>
          <Text style={styles.emptyText}>
            Tap "Start Monitoring" to begin real-time voice analysis
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: surface.background },
  header: { padding: spacing.md, paddingBottom: 0 },
  heading: {
    fontSize: 24,
    fontWeight: '700',
    color: textColors.primary,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 13,
    color: textColors.secondary,
    marginTop: spacing.xs,
    lineHeight: 19,
  },

  // Controls
  controls: { padding: spacing.md },
  startButton: {
    backgroundColor: brand.primary,
    borderRadius: radius.md,
    padding: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  startIcon: { fontSize: 24 },
  startText: { color: '#fff', fontSize: 18, fontWeight: '700' },

  monitoringHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: status.error,
    padding: spacing.md,
    gap: spacing.sm,
  },
  liveDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: status.error,
  },
  liveText: {
    flex: 1,
    color: status.error,
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 1,
  },
  stopBtn: {
    backgroundColor: status.error,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  stopBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // Stats
  statsBar: {
    flexDirection: 'row',
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.md,
    gap: spacing.sm,
  },
  stat: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 22, fontWeight: '700', color: textColors.primary },
  statLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: textColors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: 2,
  },

  // Feed entries
  entry: {
    backgroundColor: surface.card,
    borderRadius: radius.sm,
    borderLeftWidth: 3,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  entryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  entryTime: { color: textColors.muted, fontSize: 12 },
  entryBadge: {
    borderRadius: radius.lg,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 2,
  },
  entryBadgeText: { fontSize: 11, fontWeight: '700' },
  entryMetrics: { flexDirection: 'row', gap: spacing.md },
  entryMetric: { color: textColors.secondary, fontSize: 13 },

  // Empty / waiting
  waiting: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  waitingText: { color: textColors.muted, fontSize: 14 },

  empty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  emptyIcon: { fontSize: 64, marginBottom: spacing.md },
  emptyText: {
    color: textColors.muted,
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
  },

  // Error
  errorBanner: {
    backgroundColor: '#431407',
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: '#F97316',
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  errorText: { color: '#FDBA74', fontSize: 13, textAlign: 'center' },
});
