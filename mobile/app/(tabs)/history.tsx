/**
 * app/(tabs)/history.tsx — Detection History screen.
 *
 * Shows a paginated list of past detections fetched from the API,
 * with aggregate stats and a clear-all option.
 */

import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { useFocusEffect } from 'expo-router';

import { MetricCard } from '@/components/MetricCard';
import { brand, radius, risk, spacing, surface, text as textColors } from '@/constants/Colors';
import {
  clearHistory,
  getHistory,
  getStats,
  type HistoryEntry,
  type HistoryStats,
} from '@/services/api';

export default function HistoryScreen() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const [historyRes, statsRes] = await Promise.all([
        getHistory(100),
        getStats(),
      ]);
      setEntries(historyRes.entries);
      setTotal(historyRes.total);
      setStats(statsRes.stats);
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load history');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

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

  const handleClear = () => {
    Alert.alert(
      'Clear History',
      'This will permanently delete all detection records. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await clearHistory();
              setEntries([]);
              setTotal(0);
              setStats({
                total: 0,
                ai_detected: 0,
                human_detected: 0,
                uncertain: 0,
                ai_detection_rate: 0,
                avg_confidence: 0,
              });
            } catch (err: any) {
              Alert.alert('Error', err.detail || err.message || 'Failed to clear history');
            }
          },
        },
      ],
    );
  };

  const getVerdictColor = (verdict: string) => {
    if (verdict.includes('AI')) return risk.high.text;
    if (verdict === 'UNCERTAIN') return risk.uncertain.text;
    return risk.low.text;
  };

  const getRiskTheme = (riskBand: string) => {
    if (riskBand.includes('HIGH')) return risk.high;
    if (riskBand.includes('SUSPICIOUS')) return risk.suspicious;
    if (riskBand.includes('UNCERTAIN')) return risk.uncertain;
    return risk.low;
  };

  const renderEntry = useCallback(({ item, index }: { item: HistoryEntry; index: number }) => {
    const riskTheme = getRiskTheme(item.risk_band);
    return (
      <Animated.View
        entering={FadeInUp.delay(index * 30).duration(400)}
        style={styles.entry}
      >
        <View style={styles.entryHeader}>
          <View style={{ flex: 1 }}>
            <Text style={styles.entryFilename} numberOfLines={1}>
              {item.filename}
            </Text>
            <Text style={styles.entryTimestamp}>{item.timestamp}</Text>
          </View>
          <Text style={[styles.entryVerdict, { color: getVerdictColor(item.verdict) }]}>
            {item.verdict}
          </Text>
        </View>
        <View style={styles.entryFooter}>
          <View style={[styles.riskPill, { backgroundColor: riskTheme.bg, borderColor: riskTheme.border }]}>
            <Text style={[styles.riskPillText, { color: riskTheme.text }]}>
              {item.risk_band.split('—')[0].trim()}
            </Text>
          </View>
          <Text style={styles.entryConf}>
            {item.confidence_pct.toFixed(1)}% confidence
          </Text>
        </View>
      </Animated.View>
    );
  }, []);

  if (loading && !refreshing) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={brand.primary} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Stats */}
      {stats && (
        <View style={styles.statsSection}>
          <View style={styles.metricsRow}>
            <MetricCard label="Total" value={stats.total} delay={0} />
            <MetricCard label="AI" value={stats.ai_detected} delay={100} />
            <MetricCard label="Human" value={stats.human_detected} delay={200} />
          </View>
        </View>
      )}

      {/* Error */}
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Clear button */}
      {entries.length > 0 && (
        <View style={styles.clearRow}>
          <Text style={styles.totalText}>{total} record(s)</Text>
          <Pressable
            style={({ pressed }) => [styles.clearBtn, pressed && { opacity: 0.7 }]}
            onPress={handleClear}
          >
            <Text style={styles.clearBtnText}>🗑️ Clear All</Text>
          </Pressable>
        </View>
      )}

      {/* List */}
      {entries.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>📋</Text>
          <Text style={styles.emptyText}>No history yet</Text>
          <Text style={styles.emptyHint}>Analyze some audio files to see results here</Text>
        </View>
      ) : (
        <FlatList
          data={entries}
          renderItem={renderEntry}
          keyExtractor={item => String(item.id)}
          contentContainerStyle={{ paddingHorizontal: spacing.md, paddingBottom: spacing.xl }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={brand.primary}
              colors={[brand.primary]}
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: surface.background },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: surface.background,
  },

  // Stats
  statsSection: { padding: spacing.md, paddingBottom: spacing.xs },
  metricsRow: { flexDirection: 'row', gap: spacing.sm },

  // Clear
  clearRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  totalText: { color: textColors.muted, fontSize: 13 },
  clearBtn: {
    backgroundColor: '#7F1D1D',
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
  },
  clearBtnText: { color: '#FCA5A5', fontSize: 12, fontWeight: '600' },

  // Entries
  entry: {
    backgroundColor: surface.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: surface.cardBorder,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  entryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  entryFilename: {
    color: textColors.primary,
    fontSize: 14,
    fontWeight: '600',
    maxWidth: 200,
  },
  entryTimestamp: {
    color: textColors.muted,
    fontSize: 11,
    marginTop: 2,
  },
  entryVerdict: {
    fontSize: 14,
    fontWeight: '700',
  },
  entryFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  riskPill: {
    borderRadius: radius.lg,
    borderWidth: 1,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 2,
  },
  riskPillText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  entryConf: { color: textColors.secondary, fontSize: 12 },

  // Empty
  empty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  emptyIcon: { fontSize: 48, marginBottom: spacing.md },
  emptyText: { color: textColors.primary, fontSize: 18, fontWeight: '600' },
  emptyHint: { color: textColors.muted, fontSize: 14, marginTop: spacing.xs },

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
