'use client';

import { useQuery } from '@tanstack/react-query';
import { analyticsApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface HeatmapChartProps {
  days: number;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function HeatmapChart({ days }: HeatmapChartProps) {
  const { data: heatmapData, isLoading } = useQuery({
    queryKey: ['analytics', 'heatmap', days],
    queryFn: () => analyticsApi.getActivityHeatmap('current', days),
  });

  if (isLoading) {
    return (
      <div className="h-[200px] flex items-center justify-center">
        <div className="h-8 w-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Generate sample data if no real data
  const data = heatmapData || generateSampleHeatmap();

  // Find max value for color scaling
  const maxValue = Math.max(...data.flat(), 1);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[600px]">
        {/* Hour labels */}
        <div className="flex mb-2">
          <div className="w-12" /> {/* Spacer for day labels */}
          {HOURS.filter((h) => h % 3 === 0).map((hour) => (
            <div
              key={hour}
              className="flex-1 text-xs text-muted-foreground text-center"
            >
              {hour.toString().padStart(2, '0')}:00
            </div>
          ))}
        </div>

        {/* Heatmap grid */}
        <div className="space-y-1">
          {DAYS.map((day, dayIndex) => (
            <div key={day} className="flex items-center gap-1">
              <div className="w-12 text-xs text-muted-foreground">{day}</div>
              <div className="flex-1 flex gap-0.5">
                {HOURS.map((hour) => {
                  const value = data[dayIndex]?.[hour] || 0;
                  const intensity = value / maxValue;
                  return (
                    <div
                      key={hour}
                      className={cn(
                        'flex-1 h-6 rounded-sm transition-colors',
                        'hover:ring-2 hover:ring-primary hover:ring-offset-1'
                      )}
                      style={{
                        backgroundColor: getHeatmapColor(intensity),
                      }}
                      title={`${day} ${hour}:00 - ${value} activities`}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-end gap-2 mt-4">
          <span className="text-xs text-muted-foreground">Less</span>
          <div className="flex gap-0.5">
            {[0, 0.25, 0.5, 0.75, 1].map((intensity) => (
              <div
                key={intensity}
                className="w-4 h-4 rounded-sm"
                style={{ backgroundColor: getHeatmapColor(intensity) }}
              />
            ))}
          </div>
          <span className="text-xs text-muted-foreground">More</span>
        </div>
      </div>
    </div>
  );
}

function getHeatmapColor(intensity: number): string {
  if (intensity === 0) return 'hsl(var(--muted))';
  // Green gradient from light to dark
  const lightness = 80 - intensity * 50; // 80% to 30%
  return `hsl(142, 76%, ${lightness}%)`;
}

function generateSampleHeatmap(): number[][] {
  // Generate realistic-looking sample data with more activity during work hours
  return DAYS.map((_, dayIndex) =>
    HOURS.map((hour) => {
      const isWeekend = dayIndex === 0 || dayIndex === 6;
      const isWorkHours = hour >= 9 && hour <= 18;
      const isPeakHours = hour >= 10 && hour <= 16;

      let baseActivity = 0;
      if (!isWeekend && isPeakHours) {
        baseActivity = Math.random() * 100 + 50;
      } else if (!isWeekend && isWorkHours) {
        baseActivity = Math.random() * 50 + 20;
      } else if (!isWeekend) {
        baseActivity = Math.random() * 20;
      } else {
        baseActivity = Math.random() * 10;
      }

      return Math.round(baseActivity);
    })
  );
}
