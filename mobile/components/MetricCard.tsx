/**
 * components/MetricCard.tsx — Reusable stat card for dashboard metrics.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';

import { radius, spacing, surface, text as textColors } from '@/constants/Colors';

interface Props {
  label: string;
  value: string | number;
  delay?: number;
}

export function MetricCard({ label, value, delay = 0 }: Props) {
  return (
    <Animated.View
      entering={FadeInUp.delay(delay).duration(500).springify()}
      style={styles.card}
    >
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: surface.elevated,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.md,
    alignItems: 'center',
    minWidth: 80,
  },
  label: {
    fontSize: 10,
    fontWeight: '600',
    color: textColors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 6,
    textAlign: 'center',
  },
  value: {
    fontSize: 22,
    fontWeight: '700',
    color: textColors.primary,
  },
});
