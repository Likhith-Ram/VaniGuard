/**
 * app/(tabs)/_layout.tsx — Tab navigation with VaniGuard branding.
 *
 * 4 tabs: Home, Analyze, Monitor, History
 */

import { SymbolView } from 'expo-symbols';
import { Tabs } from 'expo-router';
import { Platform } from 'react-native';

import { brand, surface, text as textColors } from '@/constants/Colors';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: brand.primary,
        tabBarInactiveTintColor: textColors.muted,
        tabBarStyle: {
          backgroundColor: surface.card,
          borderTopColor: surface.cardBorder,
          borderTopWidth: 1,
          height: Platform.OS === 'android' ? 64 : 88,
          paddingBottom: Platform.OS === 'android' ? 8 : 28,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          letterSpacing: 0.3,
        },
        headerStyle: {
          backgroundColor: surface.background,
          elevation: 0,
          shadowOpacity: 0,
          borderBottomWidth: 1,
          borderBottomColor: surface.cardBorder,
        },
        headerTintColor: textColors.primary,
        headerTitleStyle: {
          fontWeight: '700',
          fontSize: 18,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          headerTitle: '🎙️ VaniGuard',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{ ios: 'house.fill', android: 'home', web: 'home' }}
              tintColor={color}
              size={24}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="analyze"
        options={{
          title: 'Analyze',
          headerTitle: 'Analyze Audio',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{ ios: 'waveform.circle.fill', android: 'graphic_eq', web: 'graphic_eq' }}
              tintColor={color}
              size={24}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="monitor"
        options={{
          title: 'Monitor',
          headerTitle: 'Live Monitor',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{ ios: 'shield.checkered', android: 'shield', web: 'shield' }}
              tintColor={color}
              size={24}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          headerTitle: 'Detection History',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{ ios: 'clock.fill', android: 'schedule', web: 'schedule' }}
              tintColor={color}
              size={24}
            />
          ),
        }}
      />
    </Tabs>
  );
}
