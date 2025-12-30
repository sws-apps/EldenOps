'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  Plus,
  Calendar,
  Clock,
  ChevronRight,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { reportsApi, type Report } from '@/lib/api';
import { cn } from '@/lib/utils';

type ReportType = 'operations' | 'engineering' | 'executive' | 'weekly';

const REPORT_TYPES: { value: ReportType; label: string; description: string; audience: string }[] = [
  {
    value: 'operations',
    label: 'Operations Report',
    description: 'Attendance, check-ins, breaks, and team availability',
    audience: 'For: Team Lead / Operations Manager',
  },
  {
    value: 'engineering',
    label: 'Engineering Report',
    description: 'Commits, PRs, code velocity, and contributor metrics',
    audience: 'For: CTO / Engineering Manager',
  },
  {
    value: 'executive',
    label: 'Executive Summary',
    description: 'High-level productivity, team health, and key metrics',
    audience: 'For: CEO / Leadership',
  },
  {
    value: 'weekly',
    label: 'Weekly Digest',
    description: 'Comprehensive summary of all team activity',
    audience: 'For: All stakeholders',
  },
];

export default function ReportsPage() {
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const queryClient = useQueryClient();

  // Fetch reports
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list('current', 20, 0),
  });

  // Generate report mutation
  const generateMutation = useMutation({
    mutationFn: ({ reportType, days }: { reportType: string; days: number }) =>
      reportsApi.generate('current', reportType, days),
    onSuccess: (newReport) => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      setSelectedReport(newReport);
      setShowGenerateModal(false);
    },
  });

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Reports</h1>
          <p className="text-muted-foreground mt-1">
            AI-generated team activity reports and insights
          </p>
        </div>
        <button
          onClick={() => setShowGenerateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Generate Report
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Reports list */}
        <div className="lg:col-span-1 rounded-lg border bg-card">
          <div className="p-4 border-b">
            <h3 className="font-semibold">Recent Reports</h3>
          </div>
          <div className="divide-y max-h-[600px] overflow-y-auto">
            {isLoading ? (
              <div className="p-8 flex justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : reports && reports.length > 0 ? (
              reports.map((report) => (
                <ReportListItem
                  key={report.id}
                  report={report}
                  isSelected={selectedReport?.id === report.id}
                  onClick={() => setSelectedReport(report)}
                />
              ))
            ) : (
              <div className="p-8 text-center text-muted-foreground">
                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No reports yet</p>
                <p className="text-sm mt-1">Generate your first report above</p>
              </div>
            )}
          </div>
        </div>

        {/* Report detail */}
        <div className="lg:col-span-2 rounded-lg border bg-card">
          {selectedReport ? (
            <ReportDetail report={selectedReport} />
          ) : (
            <div className="h-full flex items-center justify-center p-8 text-muted-foreground">
              <div className="text-center">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a report to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Generate modal */}
      {showGenerateModal && (
        <GenerateReportModal
          onClose={() => setShowGenerateModal(false)}
          onGenerate={(reportType, days) =>
            generateMutation.mutate({ reportType, days })
          }
          isGenerating={generateMutation.isPending}
        />
      )}
    </div>
  );
}

function ReportListItem({
  report,
  isSelected,
  onClick,
}: {
  report: Report;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full p-4 text-left hover:bg-accent transition-colors flex items-center gap-3',
        isSelected && 'bg-accent'
      )}
    >
      <div className="p-2 rounded-lg bg-muted">
        <FileText className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{report.title}</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
          <Calendar className="h-3 w-3" />
          <span>{format(parseISO(report.generated_at), 'MMM d, yyyy')}</span>
        </div>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
    </button>
  );
}

function ReportDetail({ report }: { report: Report }) {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold">{report.title}</h2>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>{format(parseISO(report.generated_at), 'MMMM d, yyyy')}</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                <span>{format(parseISO(report.generated_at), 'h:mm a')}</span>
              </div>
            </div>
          </div>
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-primary/10 text-primary">
            {report.report_type}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* AI Summary */}
        {report.ai_summary && (
          <div className="mb-6 p-4 rounded-lg bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/20">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold text-primary">AI Summary</span>
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {report.ai_summary}
            </p>
          </div>
        )}

        {/* Report content */}
        {report.content && Object.keys(report.content).length > 0 ? (
          <div className="space-y-6">
            {Object.entries(report.content).map(([section, data]) => (
              <ReportSection key={section} title={section} data={data} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <p>No detailed content available</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportSection({ title, data }: { title: string; data: unknown }) {
  const formattedTitle = title
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());

  return (
    <div>
      <h3 className="font-semibold mb-3">{formattedTitle}</h3>
      <div className="rounded-lg border p-4 bg-muted/30">
        {typeof data === 'object' && data !== null ? (
          <div className="space-y-2">
            {Object.entries(data as Record<string, unknown>).map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-muted-foreground">
                  {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </span>
                <span className="font-medium">
                  {typeof value === 'number' ? value.toLocaleString() : String(value)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm">{String(data)}</p>
        )}
      </div>
    </div>
  );
}

function GenerateReportModal({
  onClose,
  onGenerate,
  isGenerating,
}: {
  onClose: () => void;
  onGenerate: (reportType: string, days: number) => void;
  isGenerating: boolean;
}) {
  const [reportType, setReportType] = useState<ReportType>('weekly');
  const [days, setDays] = useState(7);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border bg-card shadow-lg">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold">Generate Report</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Create an AI-powered report for your team
          </p>
        </div>

        <div className="p-6 space-y-4">
          {/* Report type selection */}
          <div>
            <label className="text-sm font-medium">Report Type</label>
            <div className="mt-2 space-y-2">
              {REPORT_TYPES.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setReportType(type.value)}
                  className={cn(
                    'w-full p-3 rounded-lg border text-left transition-colors',
                    reportType === type.value
                      ? 'border-primary bg-primary/5'
                      : 'hover:bg-accent'
                  )}
                >
                  <div className="font-medium">{type.label}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {type.description}
                  </div>
                  <div className="text-xs text-primary/70 mt-1 font-medium">
                    {type.audience}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div>
            <label className="text-sm font-medium">Time Period</label>
            <div className="mt-2 flex gap-2">
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={cn(
                    'flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-colors',
                    days === d
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                  )}
                >
                  {d} days
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="p-6 border-t flex gap-3">
          <button
            onClick={onClose}
            disabled={isGenerating}
            className="flex-1 py-2 px-4 rounded-lg border hover:bg-accent transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onGenerate(reportType, days)}
            disabled={isGenerating}
            className="flex-1 py-2 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
