/**
 * app/(tabs)/index.tsx — Home / Dashboard screen.
 *
 * Shows aggregate detection statistics, server health status,
 * and a quick "How It Works" overview.
 */

import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useFocusEffect } from 'expo-router';

import { MetricCard } from '@/components/MetricCard';
import { StatusDot } from '@/components/StatusDot';
import {
  brand,
  radius,
  risk,
  spacing,
  surface,
  text as textColors,
} from '@/constants/Colors';
import { checkHealth, getStats, type HealthResponse, type HistoryStats } from '@/services/api';

export default function HomeScreen() {
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const [healthRes, statsRes] = await Promise.all([
        checkHealth(),
        getStats(),
      ]);
      setHealth(healthRes);
      setStats(statsRes.stats);
    } catch (err: any) {
      setError(
        err.message?.includes('Network')
          ? 'Cannot reach server. Make sure the API is running.'
          : err.detail || err.message || 'Failed to load data',
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Refresh data whenever the tab is focused
  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchData();
    }, [fetchData]),
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={brand.primary} />
        <Text style={styles.loadingText}>Connecting to server…</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={brand.primary}
          colors={[brand.primary]}
        />
      }
    >
      {/* Hero Header */}
      <Animated.View entering={FadeInDown.duration(600)} style={styles.hero}>
        <Text style={styles.heroTitle}>🎙️ VaniGuard</Text>
        <Text style={styles.heroSubtitle}>
          AI Voice-Clone Detection for Indian Languages
        </Text>
        <View style={styles.healthRow}>
          <StatusDot
            isOnline={health?.model_loaded ?? false}
            label={health?.model_loaded ? 'Model Ready' : 'Model Unavailable'}
          />
          <Text style={styles.versionText}>v{health?.version ?? '1.0.0'}</Text>
        </View>
      </Animated.View>

      {/* Error Banner */}
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Stats Grid */}
      {stats && (
        <>
          <Text style={styles.sectionTitle}>Detection Overview</Text>
          <View style={styles.metricsRow}>
            <MetricCard label="Total Analyzed" value={stats.total} delay={0} />
            <MetricCard label="AI Detected" value={stats.ai_detected} delay={100} />
            <MetricCard label="Human" value={stats.human_detected} delay={200} />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="AI Detection Rate"
              value={`${stats.ai_detection_rate}%`}
              delay={300}
            />
            <MetricCard
              label="Avg Confidence"
              value={`${stats.avg_confidence}%`}
              delay={400}
            />
          </View>
        </>
      )}

      {/* How It Works */}
      <Text style={styles.sectionTitle}>How It Works</Text>
      <View style={styles.card}>
        {PIPELINE_STEPS.map((step, i) => (
          <View key={i} style={styles.step}>
            <View style={styles.stepNum}>
              <Text style={styles.stepNumText}>{i + 1}</Text>
            </View>
            <View style={styles.stepContent}>
              <Text style={styles.stepTitle}>{step.title}</Text>
              <Text style={styles.stepDesc}>{step.desc}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Risk Bands */}
      <Text style={styles.sectionTitle}>Risk Bands</Text>
      <View style={styles.card}>
        {RISK_BANDS.map((band, i) => (
          <View key={i} style={[styles.riskRow, { backgroundColor: band.bg }]}>
            <View style={[styles.riskDot, { backgroundColor: band.border }]} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.riskLabel, { color: band.textColor }]}>{band.label}</Text>
              <Text style={styles.riskDesc}>{band.desc}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Model Info */}
      <Text style={styles.sectionTitle}>Model Info</Text>
      <View style={styles.card}>
        <InfoRow label="Architecture" value="MobileNetV2" />
        <InfoRow label="Format" value="ONNX (CPU)" />
        <InfoRow label="Languages" value="Hindi · Tamil · Telugu" />
        <InfoRow label="Dataset" value="AI4Bharat" />
        <InfoRow label="Input" value="Log-Mel Spectrogram (128 bands)" />
      </View>

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const PIPELINE_STEPS = [
  { title: 'Audio Ingestion', desc: 'File is uploaded and decoded' },
  { title: 'Resampling', desc: 'Audio resampled to 16 kHz mono' },
  { title: 'Trim / Pad', desc: 'Clip trimmed or padded to 3.0 seconds' },
  { title: 'Feature Extraction', desc: 'Log-Mel Spectrogram (128 bands)' },
  { title: 'Normalisation', desc: 'Min-max normalised to [0, 1]' },
  { title: 'Inference', desc: 'MobileNetV2 (ONNX) → P(AI) ∈ [0, 1]' },
  { title: 'Classification', desc: 'Probability → verdict + risk band' },
];

const RISK_BANDS = [
  { label: 'HIGH RISK', desc: 'P(AI) ≥ 0.80', ...risk.high, textColor: risk.high.text },
  { label: 'SUSPICIOUS', desc: 'P(AI) ≥ 0.60', ...risk.suspicious, textColor: risk.suspicious.text },
  { label: 'UNCERTAIN', desc: 'P(AI) ∈ [0.40, 0.60)', ...risk.uncertain, textColor: risk.uncertain.text },
  { label: 'LOW RISK', desc: 'P(AI) < 0.40', ...risk.low, textColor: risk.low.text },
];

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: surface.background },
  content: { padding: spacing.md },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: surface.background,
  },
  loadingText: {
    color: textColors.muted,
    marginTop: spacing.md,
    fontSize: 14,
  },

  // Hero
  hero: {
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    alignItems: 'center',
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: textColors.primary,
    letterSpacing: -0.5,
  },
  heroSubtitle: {
    fontSize: 14,
    color: textColors.secondary,
    marginTop: spacing.xs,
    textAlign: 'center',
  },
  healthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.md,
  },
  versionText: {
    fontSize: 12,
    color: textColors.muted,
  },

  // Error
  errorBanner: {
    backgroundColor: '#431407',
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: '#F97316',
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  errorText: { color: '#FDBA74', fontSize: 13, textAlign: 'center' },

  // Sections
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: textColors.primary,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  metricsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },

  // Card
  card: {
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },

  // Pipeline steps
  step: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm + 2,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: surface.cardBorder,
  },
  stepNum: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: brand.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  stepNumText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  stepContent: { flex: 1 },
  stepTitle: { color: textColors.primary, fontWeight: '600', fontSize: 14 },
  stepDesc: { color: textColors.secondary, fontSize: 13, marginTop: 2 },

  // Risk bands
  riskRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.sm + 2,
    borderRadius: radius.sm,
    marginBottom: spacing.xs,
  },
  riskDot: { width: 10, height: 10, borderRadius: 5 },
  riskLabel: { fontWeight: '600', fontSize: 13 },
  riskDesc: { color: textColors.secondary, fontSize: 12, marginTop: 1 },

  // Info rows
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: surface.cardBorder,
  },
  infoLabel: { color: textColors.secondary, fontSize: 14 },
  infoValue: { color: textColors.primary, fontSize: 14, fontWeight: '600' },
});
