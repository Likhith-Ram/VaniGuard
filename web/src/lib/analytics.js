/**
 * analytics.js — Lightweight, privacy-respecting analytics stub for VaniGuard.
 *
 * Usage: import { trackEvent } from '../lib/analytics';
 *        trackEvent('audio_analyzed', { verdict: 'AI-Generated', duration_s: 4.2 });
 *
 * Swap the `_send` function body with your analytics provider
 * (e.g. Plausible, PostHog, or a custom endpoint).
 *
 * By default events are only sent if the user accepted cookies
 * (checked via the 'vg_cookie_consent' key in localStorage).
 */

const CONSENT_KEY = 'vg_cookie_consent';

function hasConsent() {
  try {
    return localStorage.getItem(CONSENT_KEY) === 'accepted';
  } catch {
    return false;
  }
}

/**
 * Internal send — replace body with your real provider.
 * @param {string} name
 * @param {Record<string, unknown>} props
 */
function _send(name, props) {
  // --- Plausible example ---
  // if (typeof window.plausible === 'function') {
  //   window.plausible(name, { props });
  // }

  // --- PostHog example ---
  // if (typeof window.posthog !== 'undefined') {
  //   window.posthog.capture(name, props);
  // }

  // Development: log to console only
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.debug('[Analytics]', name, props);
  }
}

/**
 * Track a custom event.
 * @param {string} name - Event name (snake_case).
 * @param {Record<string, unknown>} [props] - Optional properties.
 */
export function trackEvent(name, props = {}) {
  if (!hasConsent()) return;
  _send(name, { ...props, timestamp: new Date().toISOString() });
}

/**
 * Track a page view. Call on route changes.
 * @param {string} path - The current URL path.
 */
export function trackPageView(path) {
  trackEvent('page_view', { path });
}
