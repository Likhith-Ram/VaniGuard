/**
 * components/VerdictBanner.tsx — Large verdict display after detection.
 *
 * Shows a gradient banner with the AI/Human verdict, confidence,
 * and risk badge — the hero visual of the results screen.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { brand, radius, risk, spacing, surface, text as textColors, verdict as verdictColors } from '@/constants/Colors';
import type { DetectionResult } from '@/services/api';

interface Props {
  result: DetectionResult;
}

export function VerdictBanner({ result }: Props) {
  const theme = result.is_ai
    ? verdictColors.ai
    : result.verdict === 'UNCERTAIN'
      ? verdictColors.uncertain
      : verdictColors.human;

  const riskTheme =
    result.risk_level === 'high' ? risk.high
    : result.risk_level === 'suspicious' ? risk.suspicious
    : result.risk_level === 'uncertain' ? risk.uncertain
    : risk.low;

  return (
    <Animated.View entering={FadeInDown.duration(600).springify()}>
      {/* Verdict Card */}
      <View style={[styles.banner, { backgroundColor: theme.bgStart, borderColor: theme.border }]}>
        <Text style={styles.icon}>
          {result.is_ai ? '🤖' : result.verdict === 'UNCERTAIN' ? '⚠️' : '✅'}
        </Text>
        <Text style={[styles.title, { color: theme.text }]}>
          {result.is_ai ? 'AI-Generated Voice Detected' : result.verdict === 'UNCERTAIN' ? 'Uncertain Result' : 'Human Voice Verified'}
        </Text>
        <Text style={styles.subtitle}>
          {result.is_ai
            ? 'This clip has characteristics consistent with synthetic speech.'
            : result.verdict === 'UNCERTAIN'
              ? 'Manual review is advised for this audio clip.'
              : 'This clip appears to be authentic human speech.'}
        </Text>
      </View>

      {/* Metrics Row */}
      <View style={styles.metricsRow}>
        <MetricCard label="AI Probability" value={`${(result.probability * 100).toFixed(1)}%`} />
        <MetricCard label="Confidence" value={`${result.confidence_pct.toFixed(1)}%`} />
        <MetricCard label="Duration" value={`${result.duration_s.toFixed(1)}s`} />
      </View>

      {/* Risk Badge */}
      <View style={[styles.riskBadge, { backgroundColor: riskTheme.bg, borderColor: riskTheme.border }]}>
        <Text style={[styles.riskText, { color: riskTheme.text }]}>
          {result.risk_band}
        </Text>
      </View>

      {/* Confidence Bar */}
      <View style={styles.progressOuter}>
        <Animated.View
          style={[
            styles.progressInner,
            {
              width: `${result.confidence_pct}%`,
              backgroundColor: riskTheme.border,
            },
          ]}
        />
      </View>
      <Text style={styles.progressLabel}>
        Confidence: {result.confidence_pct.toFixed(1)}%
      </Text>

      {/* Model Warning */}
      {!result.model_loaded && (
        <View style={styles.warning}>
          <Text style={styles.warningText}>
            ⚠️ Model not loaded — this result is a random placeholder
          </Text>
        </View>
      )}
    </Animated.View>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  icon: {
    fontSize: 48,
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
  subtitle: {
    fontSize: 14,
    color: textColors.secondary,
    textAlign: 'center',
    marginTop: spacing.xs,
    lineHeight: 20,
  },
  metricsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  metric: {
    flex: 1,
    backgroundColor: surface.elevated,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.md,
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: textColors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 20,
    fontWeight: '700',
    color: textColors.primary,
  },
  riskBadge: {
    alignSelf: 'flex-start',
    borderRadius: radius.lg,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    marginBottom: spacing.md,
  },
  riskText: {
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  progressOuter: {
    height: 6,
    backgroundColor: surface.cardBorder,
    borderRadius: radius.full,
    overflow: 'hidden',
    marginBottom: spacing.xs,
  },
  progressInner: {
    height: '100%',
    borderRadius: radius.full,
  },
  progressLabel: {
    fontSize: 12,
    color: textColors.muted,
    textAlign: 'right',
    marginBottom: spacing.md,
  },
  warning: {
    backgroundColor: '#431407',
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: '#F97316',
    padding: spacing.md,
  },
  warningText: {
    fontSize: 13,
    color: '#FDBA74',
    textAlign: 'center',
  },
});
