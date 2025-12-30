'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  User,
  MessageSquare,
  CheckCircle,
  XCircle,
  Filter,
  ChevronDown,
} from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

type BlockerStatus = 'active' | 'resolved' | 'all';
type BlockerPriority = 'high' | 'medium' | 'low';

interface Blocker {
  id: string;
  title: string;
  description: string;
  source: 'discord' | 'github';
  priority: BlockerPriority;
  status: 'active' | 'resolved';
  reportedBy: string;
  reportedAt: Date;
  resolvedAt?: Date;
}

// Sample data - would come from API
const SAMPLE_BLOCKERS: Blocker[] = [
  {
    id: '1',
    title: 'CI/CD pipeline failing on main branch',
    description: 'Tests are timing out due to database connection issues in the test environment.',
    source: 'github',
    priority: 'high',
    status: 'active',
    reportedBy: 'John Doe',
    reportedAt: new Date(Date.now() - 2 * 60 * 60 * 1000),
  },
  {
    id: '2',
    title: 'Waiting on API documentation from backend team',
    description: 'Frontend team blocked on implementing new endpoints until documentation is provided.',
    source: 'discord',
    priority: 'medium',
    status: 'active',
    reportedBy: 'Jane Smith',
    reportedAt: new Date(Date.now() - 24 * 60 * 60 * 1000),
  },
  {
    id: '3',
    title: 'Design review pending for new feature',
    description: 'Waiting on design team approval before proceeding with implementation.',
    source: 'discord',
    priority: 'low',
    status: 'resolved',
    reportedBy: 'Mike Johnson',
    reportedAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
    resolvedAt: new Date(Date.now() - 24 * 60 * 60 * 1000),
  },
];

export default function BlockersPage() {
  const [statusFilter, setStatusFilter] = useState<BlockerStatus>('all');
  const [blockers] = useState<Blocker[]>(SAMPLE_BLOCKERS);

  const filteredBlockers = blockers.filter((blocker) => {
    if (statusFilter === 'all') return true;
    return blocker.status === statusFilter;
  });

  const activeCount = blockers.filter((b) => b.status === 'active').length;
  const resolvedCount = blockers.filter((b) => b.status === 'resolved').length;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Blockers</h1>
        <p className="text-muted-foreground mt-1">
          AI-detected blockers and impediments from team discussions
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/10">
              <AlertTriangle className="h-5 w-5 text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeCount}</p>
              <p className="text-sm text-muted-foreground">Active Blockers</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10">
              <CheckCircle className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{resolvedCount}</p>
              <p className="text-sm text-muted-foreground">Resolved This Week</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/10">
              <Clock className="h-5 w-5 text-amber-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">2.5d</p>
              <p className="text-sm text-muted-foreground">Avg. Resolution Time</p>
            </div>
          </div>
        </div>
      </div>

      {/* Blockers list */}
      <div className="rounded-lg border bg-card">
        {/* Filter bar */}
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Filter:</span>
          </div>
          <div className="flex gap-1 p-1 rounded-lg bg-muted">
            {(['all', 'active', 'resolved'] as BlockerStatus[]).map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={cn(
                  'px-3 py-1 text-sm font-medium rounded-md transition-colors capitalize',
                  statusFilter === status
                    ? 'bg-background shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        {/* Blockers */}
        <div className="divide-y">
          {filteredBlockers.length > 0 ? (
            filteredBlockers.map((blocker) => (
              <BlockerItem key={blocker.id} blocker={blocker} />
            ))
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No blockers found</p>
              <p className="text-sm mt-1">
                {statusFilter === 'active'
                  ? 'Great! No active blockers detected.'
                  : 'No blockers match the current filter.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-lg border bg-muted/30 p-6">
        <h3 className="font-semibold mb-2">How Blocker Detection Works</h3>
        <p className="text-sm text-muted-foreground">
          EldenOps uses AI to analyze Discord messages and GitHub activity to identify potential blockers.
          Keywords like "blocked", "waiting on", "can't proceed", and "need help" are detected and
          categorized automatically. You can mark blockers as resolved once they're addressed.
        </p>
      </div>
    </div>
  );
}

function BlockerItem({ blocker }: { blocker: Blocker }) {
  const [expanded, setExpanded] = useState(false);

  const priorityStyles = {
    high: 'bg-red-500/10 text-red-500 border-red-500/20',
    medium: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    low: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  };

  return (
    <div className="p-4">
      <div className="flex items-start gap-4">
        <div
          className={cn(
            'p-2 rounded-lg',
            blocker.status === 'active' ? 'bg-red-500/10' : 'bg-green-500/10'
          )}
        >
          {blocker.status === 'active' ? (
            <XCircle className="h-5 w-5 text-red-500" />
          ) : (
            <CheckCircle className="h-5 w-5 text-green-500" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold">{blocker.title}</h3>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <div className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {blocker.reportedBy}
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {format(blocker.reportedAt, 'MMM d, h:mm a')}
                </div>
                <div className="flex items-center gap-1">
                  {blocker.source === 'discord' ? (
                    <MessageSquare className="h-3 w-3" />
                  ) : (
                    <AlertTriangle className="h-3 w-3" />
                  )}
                  {blocker.source}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'px-2 py-0.5 text-xs font-medium rounded-full border',
                  priorityStyles[blocker.priority]
                )}
              >
                {blocker.priority}
              </span>
              <button
                onClick={() => setExpanded(!expanded)}
                className="p-1 hover:bg-accent rounded transition-colors"
              >
                <ChevronDown
                  className={cn(
                    'h-4 w-4 transition-transform',
                    expanded && 'rotate-180'
                  )}
                />
              </button>
            </div>
          </div>
          {expanded && (
            <div className="mt-3 p-3 rounded-lg bg-muted/50">
              <p className="text-sm">{blocker.description}</p>
              {blocker.resolvedAt && (
                <p className="text-xs text-muted-foreground mt-2">
                  Resolved on {format(blocker.resolvedAt, 'MMM d, yyyy')}
                </p>
              )}
              {blocker.status === 'active' && (
                <button className="mt-3 px-3 py-1.5 text-sm font-medium bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors">
                  Mark as Resolved
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
