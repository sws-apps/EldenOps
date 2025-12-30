'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LogIn,
  LogOut,
  Coffee,
  Users,
  Clock,
  Calendar,
  Sun,
  Moon,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react';
import { attendanceApi, type AttendanceInsights } from '@/lib/api';
import { useTimezone, formatDateTime, TIMEZONE_CONFIG } from '@/lib/timezone';
import { DateRangePicker, type DateRange } from '@/components/ui/date-range-picker';

// Convert a time string (HH:MM) from UTC to local timezone in 12-hour format
function convertTimeToTimezone(utcTime: string | null | undefined, timezone: 'PT' | 'PHT'): string {
  if (!utcTime) return '--:--';

  const match = utcTime.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return utcTime;

  const [, hours, minutes] = match;
  const utcHour = parseInt(hours, 10);
  const utcMinute = parseInt(minutes, 10);

  // Create a date with UTC time
  const date = new Date();
  date.setUTCHours(utcHour, utcMinute, 0, 0);

  // Convert to local timezone
  const localTime = new Date(date.toLocaleString('en-US', { timeZone: TIMEZONE_CONFIG[timezone].iana }));
  const localHour = localTime.getHours();
  const localMinute = localTime.getMinutes();

  // Format as 12-hour time
  const period = localHour >= 12 ? 'PM' : 'AM';
  const displayHour = localHour === 0 ? 12 : localHour > 12 ? localHour - 12 : localHour;

  return `${displayHour}:${localMinute.toString().padStart(2, '0')} ${period}`;
}

export default function AnalyticsPage() {
  const { timezone } = useTimezone();
  const [dateRange, setDateRange] = useState<DateRange>('30d');

  const days = {
    '7d': 7,
    '14d': 14,
    '30d': 30,
    '90d': 90,
  }[dateRange];

  // Fetch behavioral insights
  const { data: insights, isLoading } = useQuery({
    queryKey: ['attendance', 'insights', days],
    queryFn: () => attendanceApi.getInsights(days),
  });

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Attendance Insights</h1>
            <p className="text-muted-foreground mt-1">
              Behavioral patterns and team analytics
            </p>
          </div>
          <DateRangePicker value={dateRange} onChange={setDateRange} />
        </div>
        <div className="h-[400px] flex items-center justify-center">
          <div className="h-8 w-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!insights?.has_data) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Attendance Insights</h1>
            <p className="text-muted-foreground mt-1">
              Behavioral patterns and team analytics
            </p>
          </div>
          <DateRangePicker value={dateRange} onChange={setDateRange} />
        </div>
        <div className="rounded-lg border border-dashed bg-muted/50 p-12 text-center">
          <Calendar className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Attendance Data Yet</h3>
          <p className="text-muted-foreground max-w-md mx-auto">
            Start tracking attendance by posting check-in messages in your Discord
            #checkin-status channel. Insights will appear once there&apos;s enough data.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Attendance Insights</h1>
          <p className="text-muted-foreground mt-1">
            Behavioral patterns and team analytics
          </p>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {/* Key timing insights */}
      <div className="grid gap-4 md:grid-cols-3">
        <InsightCard
          title="Typical Check-in Time"
          value={convertTimeToTimezone(insights.checkin_patterns?.average_time, timezone)}
          icon={LogIn}
          subtitle={insights.checkin_patterns?.peak_hours?.[0]
            ? `Peak hour: ${convertTimeToTimezone(insights.checkin_patterns.peak_hours[0].time, timezone)}`
            : 'No peak detected'}
          color="text-green-500"
        />
        <InsightCard
          title="Typical Check-out Time"
          value={convertTimeToTimezone(insights.checkout_patterns?.average_time, timezone)}
          icon={LogOut}
          subtitle={insights.checkout_patterns?.peak_hours?.[0]
            ? `Peak hour: ${convertTimeToTimezone(insights.checkout_patterns.peak_hours[0].time, timezone)}`
            : 'No peak detected'}
          color="text-blue-500"
        />
        <InsightCard
          title="Typical Break Time"
          value={convertTimeToTimezone(insights.break_patterns?.average_time, timezone)}
          icon={Coffee}
          subtitle={insights.break_patterns?.peak_hours?.[0]
            ? `Peak hour: ${convertTimeToTimezone(insights.break_patterns.peak_hours[0].time, timezone)}`
            : 'No peak detected'}
          color="text-yellow-500"
        />
      </div>

      {/* Team behavior cards */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Early Birds */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Sun className="h-5 w-5 text-yellow-500" />
            Early Birds
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Team members who typically check in earliest
          </p>
          {insights.team_insights?.early_birds?.length ? (
            <div className="space-y-3">
              {insights.team_insights.early_birds.map((user, idx) => (
                <div key={user.username} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-yellow-500/10 flex items-center justify-center text-sm font-medium text-yellow-600">
                      {idx + 1}
                    </div>
                    <span className="font-medium">{user.username}</span>
                  </div>
                  <span className="text-muted-foreground">
                    ~{convertTimeToTimezone(user.avg_checkin_time, timezone)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Not enough data</p>
          )}
        </div>

        {/* Night Owls */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Moon className="h-5 w-5 text-indigo-500" />
            Night Owls
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Team members who typically check out latest
          </p>
          {insights.team_insights?.night_owls?.length ? (
            <div className="space-y-3">
              {insights.team_insights.night_owls.map((user, idx) => (
                <div key={user.username} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-indigo-500/10 flex items-center justify-center text-sm font-medium text-indigo-600">
                      {idx + 1}
                    </div>
                    <span className="font-medium">{user.username}</span>
                  </div>
                  <span className="text-muted-foreground">
                    ~{convertTimeToTimezone(user.avg_checkout_time, timezone)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Not enough data</p>
          )}
        </div>
      </div>

      {/* Break Analysis */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Break Reasons */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Coffee className="h-5 w-5 text-yellow-500" />
            Break Reasons
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Why team members take breaks
          </p>
          {insights.break_patterns?.reasons?.length ? (
            <div className="space-y-3">
              {insights.break_patterns.reasons.map((item) => (
                <div key={item.reason} className="flex items-center justify-between">
                  <span className="capitalize">{item.reason}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-yellow-500 rounded-full"
                        style={{
                          width: `${Math.min(100, (item.count / (insights.break_patterns?.reasons?.[0]?.count || 1)) * 100)}%`
                        }}
                      />
                    </div>
                    <span className="text-sm text-muted-foreground w-8 text-right">
                      {item.count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No break reasons recorded</p>
          )}
        </div>

        {/* Most Breaks */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Break Frequency
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Who takes the most breaks
          </p>
          {insights.team_insights?.most_breaks?.length ? (
            <div className="space-y-3">
              {insights.team_insights.most_breaks.map((user, idx) => (
                <div key={user.username} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
                      {idx + 1}
                    </div>
                    <span className="font-medium">{user.username}</span>
                  </div>
                  <span className="text-muted-foreground">
                    {user.break_count} breaks
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Not enough data</p>
          )}
        </div>
      </div>

      {/* Long Breaks */}
      {insights.break_patterns?.long_breaks?.length ? (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-500" />
            Extended Breaks (30+ minutes)
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Recent breaks that exceeded 30 minutes
          </p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Team Member</th>
                  <th className="pb-3 font-medium">Duration</th>
                  <th className="pb-3 font-medium">Reason</th>
                  <th className="pb-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {insights.break_patterns.long_breaks.map((brk, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-3 font-medium">{brk.username}</td>
                    <td className="py-3">
                      <span className="text-orange-500 font-medium">
                        {brk.duration_minutes} min
                      </span>
                    </td>
                    <td className="py-3 text-muted-foreground">{brk.reason}</td>
                    <td className="py-3 text-muted-foreground text-sm">
                      {formatDateTime(brk.time, timezone)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Hour Distribution */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Activity by Hour
        </h3>
        <p className="text-sm text-muted-foreground mb-6">
          When does activity typically happen throughout the day
        </p>
        <div className="space-y-6">
          <HourDistribution
            label="Check-ins"
            data={insights.checkin_patterns?.hour_distribution || {}}
            color="bg-green-500"
            timezone={timezone}
          />
          <HourDistribution
            label="Check-outs"
            data={insights.checkout_patterns?.hour_distribution || {}}
            color="bg-blue-500"
            timezone={timezone}
          />
          <HourDistribution
            label="Breaks"
            data={insights.break_patterns?.hour_distribution || {}}
            color="bg-yellow-500"
            timezone={timezone}
          />
        </div>
      </div>
    </div>
  );
}

function InsightCard({
  title,
  value,
  icon: Icon,
  subtitle,
  color,
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  subtitle: string;
  color: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-muted">
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
        <span className="text-sm font-medium text-muted-foreground">{title}</span>
      </div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function HourDistribution({
  label,
  data,
  color,
  timezone,
}: {
  label: string;
  data: Record<string, number>;
  color: string;
  timezone: 'PT' | 'PHT';
}) {
  // Convert UTC hours to local timezone hours
  const convertHourToTimezone = (utcHour: number): number => {
    const date = new Date();
    date.setUTCHours(utcHour, 0, 0, 0);
    const localTime = new Date(date.toLocaleString('en-US', { timeZone: TIMEZONE_CONFIG[timezone].iana }));
    return localTime.getHours();
  };

  // Format hour for display
  const formatHourLabel = (hour: number): string => {
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${displayHour}${period}`;
  };

  // Remap data from UTC to local timezone
  const localData: Record<number, number> = {};
  Object.entries(data).forEach(([utcHourStr, count]) => {
    const utcHour = parseInt(utcHourStr.split(':')[0], 10);
    const localHour = convertHourToTimezone(utcHour);
    localData[localHour] = (localData[localHour] || 0) + count;
  });

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxValue = Math.max(...Object.values(localData), 1);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{TIMEZONE_CONFIG[timezone].shortLabel()}</span>
      </div>
      <div className="flex gap-0.5 h-12">
        {hours.map((hour) => {
          const value = localData[hour] || 0;
          const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
          return (
            <div
              key={hour}
              className="flex-1 flex flex-col justify-end group relative"
              title={`${formatHourLabel(hour)}: ${value}`}
            >
              <div
                className={`${color} rounded-t transition-all hover:opacity-80`}
                style={{ height: `${Math.max(height, value > 0 ? 10 : 0)}%` }}
              />
              {/* Tooltip on hover */}
              <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
                <div className="bg-popover text-popover-foreground text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap">
                  {formatHourLabel(hour)}: {value}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground mt-1">
        <span>12AM</span>
        <span>6AM</span>
        <span>12PM</span>
        <span>6PM</span>
        <span>11PM</span>
      </div>
    </div>
  );
}
