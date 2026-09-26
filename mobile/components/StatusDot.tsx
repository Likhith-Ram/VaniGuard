/**
 * components/StatusDot.tsx — Animated status indicator for server health.
 */

import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { spacing, status } from '@/constants/Colors';

interface Props {
  isOnline: boolean;
  label?: string;
}

export function StatusDot({ isOnline, label }: Props) {
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (isOnline) {
      opacity.value = withRepeat(
        withTiming(0.3, { duration: 1200 }),
        -1, // infinite
        true, // reverse
      );
    } else {
      opacity.value = 1;
    }
  }, [isOnline]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: isOnline ? opacity.value : 1,
  }));

  return (
    <View style={styles.container}>
      <Animated.View
        style={[
          styles.dot,
          { backgroundColor: isOnline ? status.success : status.error },
          animatedStyle,
        ]}
      />
      {label && (
        <Text style={[styles.label, { color: isOnline ? status.success : status.error }]}>
          {label}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs + 2,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
  },
});
