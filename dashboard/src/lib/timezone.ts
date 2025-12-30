import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type TimezoneOption = 'PT' | 'PHT';

interface TimezoneState {
  timezone: TimezoneOption;
  setTimezone: (tz: TimezoneOption) => void;
}

// Check if Pacific Time is currently in Daylight Saving Time
function isPacificDST(): boolean {
  const now = new Date();
  const jan = new Date(now.getFullYear(), 0, 1);
  const jul = new Date(now.getFullYear(), 6, 1);

  // Get offsets for LA timezone
  const janOffset = new Date(jan.toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })).getTimezoneOffset();
  const julOffset = new Date(jul.toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })).getTimezoneOffset();
  const nowOffset = new Date(now.toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })).getTimezoneOffset();

  // If current offset matches summer offset, it's DST
  return nowOffset === Math.min(janOffset, julOffset);
}

// Get the current Pacific timezone label (PST or PDT)
export function getPacificLabel(): string {
  return isPacificDST() ? 'PDT' : 'PST';
}

export const TIMEZONE_CONFIG: Record<TimezoneOption, { label: string; shortLabel: () => string; iana: string }> = {
  PT: {
    label: 'Pacific Time',
    shortLabel: () => isPacificDST() ? 'PDT' : 'PST',
    iana: 'America/Los_Angeles',
  },
  PHT: {
    label: 'Philippine Time',
    shortLabel: () => 'PHT',
    iana: 'Asia/Manila',
  },
};

export const useTimezone = create<TimezoneState>()(
  persist(
    (set) => ({
      timezone: 'PT', // Default to Pacific Time (auto PST/PDT)
      setTimezone: (timezone) => set({ timezone }),
    }),
    {
      name: 'eldenops-timezone',
    }
  )
);

// Utility functions for formatting dates in the selected timezone
export function formatTime(dateString: string, timezone: TimezoneOption): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: TIMEZONE_CONFIG[timezone].iana,
  });
}

export function formatDateTime(dateString: string, timezone: TimezoneOption): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: TIMEZONE_CONFIG[timezone].iana,
  });
}

export function formatDate(dateString: string, timezone: TimezoneOption): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: TIMEZONE_CONFIG[timezone].iana,
  });
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function formatHour(hour: string, timezone: TimezoneOption): string {
  // hour comes as "HH:00" format, parse and convert
  const hourNum = parseInt(hour.split(':')[0], 10);
  const date = new Date();
  date.setUTCHours(hourNum, 0, 0, 0);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    hour12: true,
    timeZone: TIMEZONE_CONFIG[timezone].iana,
  });
}

// Get current time in the selected timezone
export function getCurrentTime(timezone: TimezoneOption): string {
  return new Date().toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: TIMEZONE_CONFIG[timezone].iana,
  });
}
