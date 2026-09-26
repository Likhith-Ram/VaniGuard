/**
 * VaniGuard Design System — Color tokens matching the Streamlit dark-glass theme.
 *
 * All colors are defined here as a single source of truth.
 */

// ── Brand Colors ─────────────────────────────────────────────────────────
export const brand = {
  primary: '#7C3AED',       // Vibrant purple — main accent
  primaryLight: '#A78BFA',  // Light purple — hover/active states
  primaryDark: '#5B21B6',   // Deep purple — pressed states
  gradient: ['#7C3AED', '#5B21B6'] as const,
};

// ── Surface Colors ───────────────────────────────────────────────────────
export const surface = {
  background: '#0F0D1A',    // Deepest background
  card: '#1A1826',          // Card/panel background
  cardBorder: '#2D2A45',    // Subtle borders
  elevated: '#1E1B2E',      // Elevated surfaces (metrics)
  input: '#16132A',         // Input fields
};

// ── Text Colors ──────────────────────────────────────────────────────────
export const text = {
  primary: '#E8E8F0',       // Main text
  secondary: '#9CA3AF',     // Muted text
  muted: '#6B7280',         // Very muted
  inverse: '#0F0D1A',       // Text on light backgrounds
};

// ── Risk Band Colors ─────────────────────────────────────────────────────
export const risk = {
  high: {
    bg: '#7F1D1D',
    text: '#FCA5A5',
    border: '#EF4444',
    icon: '#EF4444',
  },
  suspicious: {
    bg: '#431407',
    text: '#FDBA74',
    border: '#F97316',
    icon: '#F97316',
  },
  uncertain: {
    bg: '#713F12',
    text: '#FDE68A',
    border: '#F59E0B',
    icon: '#F59E0B',
  },
  low: {
    bg: '#14532D',
    text: '#86EFAC',
    border: '#22C55E',
    icon: '#22C55E',
  },
};

// ── Verdict Colors ───────────────────────────────────────────────────────
export const verdict = {
  ai: {
    bgStart: '#7F1D1D',
    bgEnd: '#450A0A',
    border: '#EF4444',
    text: '#FCA5A5',
    icon: '🤖',
  },
  human: {
    bgStart: '#14532D',
    bgEnd: '#052E16',
    border: '#22C55E',
    text: '#86EFAC',
    icon: '✅',
  },
  uncertain: {
    bgStart: '#713F12',
    bgEnd: '#422006',
    border: '#F59E0B',
    text: '#FDE68A',
    icon: '⚠️',
  },
};

// ── Status Colors ────────────────────────────────────────────────────────
export const status = {
  success: '#22C55E',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
};

// ── Spacing ──────────────────────────────────────────────────────────────
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// ── Border Radius ────────────────────────────────────────────────────────
export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  full: 9999,
};

// ── Typography ───────────────────────────────────────────────────────────
export const typography = {
  title: {
    fontSize: 28,
    fontWeight: '700' as const,
    color: text.primary,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '600' as const,
    color: text.primary,
  },
  body: {
    fontSize: 15,
    fontWeight: '400' as const,
    color: text.secondary,
    lineHeight: 22,
  },
  caption: {
    fontSize: 12,
    fontWeight: '500' as const,
    color: text.muted,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.8,
  },
  metric: {
    fontSize: 32,
    fontWeight: '700' as const,
    color: text.primary,
  },
};

// ── Tab Bar ──────────────────────────────────────────────────────────────
// Exported in the format the Expo tabs template expects
export default {
  light: {
    text: text.primary,
    background: surface.background,
    tint: brand.primary,
    tabIconDefault: text.muted,
    tabIconSelected: brand.primary,
  },
  dark: {
    text: text.primary,
    background: surface.background,
    tint: brand.primary,
    tabIconDefault: text.muted,
    tabIconSelected: brand.primary,
  },
};
