'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Github,
  GitCommit,
  GitPullRequest,
  AlertCircle,
  Users,
  Plus,
  Minus,
  Clock,
  Calendar,
  TrendingUp,
  ExternalLink,
  Code,
  Settings,
  Trash2,
  Link,
  Loader2,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react';
import { githubApi, type GitHubInsights, type GitHubContributor, type GitHubConnection } from '@/lib/api';
import { useTimezone, formatDateTime, TIMEZONE_CONFIG } from '@/lib/timezone';
import { DateRangePicker, type DateRange } from '@/components/ui/date-range-picker';
import { useAuth } from '@/lib/auth';

export default function GitHubPage() {
  const { timezone } = useTimezone();
  const { currentTenantId } = useAuth();
  const [dateRange, setDateRange] = useState<DateRange>('30d');
  const [showSettings, setShowSettings] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [addError, setAddError] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const getWebhookUrl = (connectionId: string) => {
    const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
    return `${baseUrl}/api/v1/webhooks/github/${currentTenantId}/${connectionId}`;
  };

  const copyWebhookUrl = async (connectionId: string) => {
    const url = getWebhookUrl(connectionId);
    await navigator.clipboard.writeText(url);
    setCopiedId(connectionId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const days = {
    '7d': 7,
    '14d': 14,
    '30d': 30,
    '90d': 90,
  }[dateRange];

  // Fetch GitHub connections
  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ['github', 'connections'],
    queryFn: () => githubApi.getConnections(),
  });

  // Fetch GitHub summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['github', 'summary', days],
    queryFn: () => githubApi.getSummary(days),
  });

  // Fetch GitHub insights
  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ['github', 'insights', days],
    queryFn: () => githubApi.getInsights(days),
  });

  // Fetch recent activity
  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['github', 'activity', days],
    queryFn: () => githubApi.getActivity(days, 20),
  });

  // Add connection mutation
  const addConnectionMutation = useMutation({
    mutationFn: (repoFullName: string) => githubApi.addConnection(repoFullName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github'] });
      setNewRepoName('');
      setAddError(null);
    },
    onError: (error: Error) => {
      setAddError(error.message);
    },
  });

  // Remove connection mutation
  const removeConnectionMutation = useMutation({
    mutationFn: (connectionId: string) => githubApi.removeConnection(connectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github'] });
    },
  });

  // Sync connection mutation
  const syncConnectionMutation = useMutation({
    mutationFn: (connectionId: string) => githubApi.syncConnection(connectionId, days),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github'] });
      setSyncingId(null);
    },
    onError: () => {
      setSyncingId(null);
    },
  });

  const handleSync = (connectionId: string) => {
    setSyncingId(connectionId);
    syncConnectionMutation.mutate(connectionId);
  };

  const handleAddConnection = (e: React.FormEvent) => {
    e.preventDefault();
    if (newRepoName.trim()) {
      addConnectionMutation.mutate(newRepoName.trim());
    }
  };

  const isLoading = summaryLoading || insightsLoading;

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">GitHub Analytics</h1>
            <p className="text-muted-foreground mt-1">
              Development velocity and contributor insights
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

  const hasData = insights?.has_data || (summary?.totals.commits ?? 0) > 0;

  if (!hasData) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">GitHub Analytics</h1>
            <p className="text-muted-foreground mt-1">
              Development velocity and contributor insights
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-2 rounded-lg border transition-colors ${showSettings ? 'bg-primary text-primary-foreground' : 'bg-card hover:bg-muted'}`}
              title="Manage repositories"
            >
              <Settings className="h-5 w-5" />
            </button>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>
        </div>

        {/* Repository Settings Panel */}
        {showSettings && (
          <div className="rounded-lg border bg-card p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Link className="h-5 w-5" />
              Connected Repositories
            </h3>

            {/* Add new repo form */}
            <form onSubmit={handleAddConnection} className="mb-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newRepoName}
                  onChange={(e) => {
                    setNewRepoName(e.target.value);
                    setAddError(null);
                  }}
                  placeholder="owner/repository"
                  className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  type="submit"
                  disabled={addConnectionMutation.isPending || !newRepoName.trim()}
                  className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {addConnectionMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                  Add
                </button>
              </div>
              {addError && (
                <p className="text-sm text-red-500 mt-2">{addError}</p>
              )}
            </form>

            {/* Connected repos list */}
            {connectionsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : connections && connections.length > 0 ? (
              <div className="space-y-2">
                {connections.map((conn) => (
                  <div
                    key={conn.id}
                    className="py-2 px-3 rounded-lg bg-muted/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Github className="h-4 w-4 text-muted-foreground" />
                        <a
                          href={`https://github.com/${conn.repo_full_name}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium hover:underline"
                        >
                          {conn.repo_full_name}
                        </a>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleSync(conn.id)}
                          disabled={syncingId === conn.id}
                          className="p-1.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
                          title="Sync repository data"
                        >
                          {syncingId === conn.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => copyWebhookUrl(conn.id)}
                          className="p-1.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
                          title="Copy webhook URL"
                        >
                          {copiedId === conn.id ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => removeConnectionMutation.mutate(conn.id)}
                          disabled={removeConnectionMutation.isPending}
                          className="p-1.5 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors"
                          title="Remove repository"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <code className="text-xs text-muted-foreground bg-background px-1.5 py-0.5 rounded truncate max-w-[300px]">
                        {getWebhookUrl(conn.id)}
                      </code>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No repositories connected yet. Add one above to start tracking.
              </p>
            )}

            <div className="mt-4 pt-4 border-t">
              <p className="text-xs text-muted-foreground">
                <strong>Quick sync:</strong> Click the refresh icon to fetch recent commits, PRs, and issues.
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                <strong>Real-time updates:</strong> Set up a GitHub webhook in your repo settings with the URL shown above. Select events: Pushes, Pull requests, and Issues.
              </p>
            </div>
          </div>
        )}

        {/* Show connected repos status if any but not in settings mode */}
        {!showSettings && connections && connections.length > 0 && (
          <div className="rounded-lg border bg-card p-4">
            <p className="text-sm text-muted-foreground mb-2">
              <strong>{connections.length}</strong> {connections.length === 1 ? 'repository' : 'repositories'} connected, waiting for webhook events:
            </p>
            <div className="flex flex-wrap gap-2">
              {connections.map((conn) => (
                <span key={conn.id} className="px-2 py-1 rounded bg-muted text-sm">
                  {conn.repo_full_name}
                </span>
              ))}
            </div>
          </div>
        )}

        {!showSettings && (
          <div className="rounded-lg border border-dashed bg-muted/50 p-12 text-center">
            <Github className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No GitHub Data Yet</h3>
            <p className="text-muted-foreground max-w-md mx-auto mb-4">
              Connect a GitHub repository and configure webhooks to start tracking commits, PRs, and issues.
            </p>
            <button
              onClick={() => setShowSettings(true)}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 inline-flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Connect Repository
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">GitHub Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Development velocity and contributor insights
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 rounded-lg border bg-card hover:bg-muted transition-colors"
            title="Manage repositories"
          >
            <Settings className="h-5 w-5" />
          </button>
          <DateRangePicker value={dateRange} onChange={setDateRange} />
        </div>
      </div>

      {/* Repository Settings Panel */}
      {showSettings && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Link className="h-5 w-5" />
            Connected Repositories
          </h3>

          {/* Add new repo form */}
          <form onSubmit={handleAddConnection} className="mb-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={newRepoName}
                onChange={(e) => {
                  setNewRepoName(e.target.value);
                  setAddError(null);
                }}
                placeholder="owner/repository"
                className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="submit"
                disabled={addConnectionMutation.isPending || !newRepoName.trim()}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {addConnectionMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Add
              </button>
            </div>
            {addError && (
              <p className="text-sm text-red-500 mt-2">{addError}</p>
            )}
          </form>

          {/* Connected repos list */}
          {connectionsLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : connections && connections.length > 0 ? (
            <div className="space-y-2">
              {connections.map((conn) => (
                <div
                  key={conn.id}
                  className="py-2 px-3 rounded-lg bg-muted/50"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Github className="h-4 w-4 text-muted-foreground" />
                      <a
                        href={`https://github.com/${conn.repo_full_name}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium hover:underline"
                      >
                        {conn.repo_full_name}
                      </a>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleSync(conn.id)}
                        disabled={syncingId === conn.id}
                        className="p-1.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
                        title="Sync repository data"
                      >
                        {syncingId === conn.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                      </button>
                      <button
                        onClick={() => copyWebhookUrl(conn.id)}
                        className="p-1.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
                        title="Copy webhook URL"
                      >
                        {copiedId === conn.id ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                      <button
                        onClick={() => removeConnectionMutation.mutate(conn.id)}
                        disabled={removeConnectionMutation.isPending}
                        className="p-1.5 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors"
                        title="Remove repository"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="text-xs text-muted-foreground bg-background px-1.5 py-0.5 rounded truncate max-w-[300px]">
                      {getWebhookUrl(conn.id)}
                    </code>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No repositories connected yet. Add one above to start tracking.
            </p>
          )}

          <div className="mt-4 pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              <strong>Quick sync:</strong> Click the refresh icon to fetch recent commits, PRs, and issues.
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              <strong>Real-time updates:</strong> Set up a GitHub webhook in your repo settings with the URL shown above. Select events: Pushes, Pull requests, and Issues.
            </p>
          </div>
        </div>
      )}

      {/* Summary stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Commits"
          value={summary?.totals.commits || 0}
          icon={GitCommit}
          subtitle={`${days} day period`}
          color="text-green-500"
        />
        <StatCard
          title="Pull Requests"
          value={summary?.totals.prs || 0}
          icon={GitPullRequest}
          subtitle="Opened & merged"
          color="text-blue-500"
        />
        <StatCard
          title="Issues"
          value={summary?.totals.issues || 0}
          icon={AlertCircle}
          subtitle="Opened & closed"
          color="text-yellow-500"
        />
        <StatCard
          title="Contributors"
          value={summary?.totals.contributors || 0}
          icon={Users}
          subtitle="Active this period"
          color="text-purple-500"
        />
      </div>

      {/* Code stats */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Code className="h-5 w-5" />
            Code Changes
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-green-500/10">
              <div className="flex items-center gap-2 text-green-500">
                <Plus className="h-5 w-5" />
                <span className="text-2xl font-bold">
                  {(summary?.totals.lines_added || 0).toLocaleString()}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">Lines added</p>
            </div>
            <div className="p-4 rounded-lg bg-red-500/10">
              <div className="flex items-center gap-2 text-red-500">
                <Minus className="h-5 w-5" />
                <span className="text-2xl font-bold">
                  {(summary?.totals.lines_deleted || 0).toLocaleString()}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">Lines deleted</p>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Peak Activity Times
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b">
              <span className="text-muted-foreground">Peak commit hour</span>
              <span className="font-medium">
                {insights?.commit_patterns?.peak_hour || '--:--'}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b">
              <span className="text-muted-foreground">Average commit time</span>
              <span className="font-medium">
                {insights?.commit_patterns?.average_hour || '--:--'}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-muted-foreground">Peak PR hour</span>
              <span className="font-medium">
                {insights?.pr_patterns?.peak_hour || '--:--'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Top contributors */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Top Contributors
        </h3>
        {insights?.top_contributors?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Contributor</th>
                  <th className="pb-3 font-medium text-center">Commits</th>
                  <th className="pb-3 font-medium text-center">PRs Opened</th>
                  <th className="pb-3 font-medium text-center">PRs Merged</th>
                  <th className="pb-3 font-medium text-center">Issues</th>
                  <th className="pb-3 font-medium text-right">Lines Changed</th>
                </tr>
              </thead>
              <tbody>
                {insights.top_contributors.map((contributor, idx) => (
                  <ContributorRow key={contributor.github_username} contributor={contributor} rank={idx + 1} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">No contributor data available</p>
        )}
      </div>

      {/* Activity by day */}
      {insights?.activity_by_day && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Activity by Day of Week
          </h3>
          <div className="grid grid-cols-7 gap-2">
            {Object.entries(insights.activity_by_day).map(([day, count]) => {
              const maxCount = Math.max(...Object.values(insights.activity_by_day || {}), 1);
              const intensity = count / maxCount;
              return (
                <div key={day} className="text-center">
                  <div
                    className="h-16 rounded-lg flex items-end justify-center transition-all"
                    style={{
                      backgroundColor: `rgba(34, 197, 94, ${Math.max(intensity * 0.8, 0.1)})`,
                    }}
                  >
                    <span className="text-xs font-medium pb-1">{count}</span>
                  </div>
                  <span className="text-xs text-muted-foreground mt-1 block">
                    {day.slice(0, 3)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Hour distribution */}
      {insights?.activity_by_hour && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Activity by Hour
          </h3>
          <HourDistribution data={insights.activity_by_hour} timezone={timezone} />
        </div>
      )}

      {/* Recent activity */}
      {activity && activity.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {activity.slice(0, 10).map((event) => (
              <ActivityRow key={event.id} event={event} timezone={timezone} />
            ))}
          </div>
        </div>
      )}

      {/* Repository breakdown */}
      {summary?.repos && summary.repos.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Github className="h-5 w-5" />
            Repository Breakdown
          </h3>
          <div className="space-y-3">
            {summary.repos.map((repo) => (
              <div key={repo.repo_full_name} className="flex items-center justify-between py-3 border-b last:border-0">
                <div className="flex items-center gap-3">
                  <Github className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <a
                      href={`https://github.com/${repo.repo_full_name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium hover:underline flex items-center gap-1"
                    >
                      {repo.repo_full_name}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                    <p className="text-sm text-muted-foreground">
                      {repo.contributors} contributors
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  <span className="flex items-center gap-1">
                    <GitCommit className="h-4 w-4 text-green-500" />
                    {repo.total_commits}
                  </span>
                  <span className="flex items-center gap-1">
                    <GitPullRequest className="h-4 w-4 text-blue-500" />
                    {repo.total_prs}
                  </span>
                  <span className="flex items-center gap-1">
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    {repo.total_issues}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  subtitle,
  color,
}: {
  title: string;
  value: number;
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
      <div className="text-3xl font-bold mb-1">{value.toLocaleString()}</div>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function ContributorRow({
  contributor,
  rank,
}: {
  contributor: GitHubContributor;
  rank: number;
}) {
  const linesChanged = contributor.lines_added + contributor.lines_deleted;

  return (
    <tr className="border-b last:border-0">
      <td className="py-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
            {rank}
          </div>
          <a
            href={`https://github.com/${contributor.github_username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium hover:underline"
          >
            {contributor.github_username}
          </a>
        </div>
      </td>
      <td className="py-3 text-center">
        <span className="text-green-500 font-medium">{contributor.commits}</span>
      </td>
      <td className="py-3 text-center">{contributor.prs_opened}</td>
      <td className="py-3 text-center">
        <span className="text-blue-500 font-medium">{contributor.prs_merged}</span>
      </td>
      <td className="py-3 text-center">{contributor.issues_opened}</td>
      <td className="py-3 text-right">
        <span className="text-green-500">+{contributor.lines_added.toLocaleString()}</span>
        {' / '}
        <span className="text-red-500">-{contributor.lines_deleted.toLocaleString()}</span>
      </td>
    </tr>
  );
}

function HourDistribution({ data, timezone }: { data: Record<string, number>; timezone: 'PT' | 'PHT' }) {
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
      <div className="flex items-center justify-end mb-2">
        <span className="text-xs text-muted-foreground">{TIMEZONE_CONFIG[timezone].shortLabel()}</span>
      </div>
      <div className="flex gap-0.5 h-16">
        {hours.map((hour) => {
          const value = localData[hour] || 0;
          const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
          return (
            <div
              key={hour}
              className="flex-1 flex flex-col justify-end group relative"
              title={`${formatHourLabel(hour)}: ${value} events`}
            >
              <div
                className="bg-green-500 rounded-t transition-all hover:bg-green-400"
                style={{ height: `${Math.max(height, value > 0 ? 10 : 0)}%` }}
              />
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

function ActivityRow({ event, timezone }: { event: { event_type: string; github_user: string | null; title: string | null; ref_url: string | null; created_at: string; repo_full_name: string }; timezone: 'PT' | 'PHT' }) {
  const icons: Record<string, React.ComponentType<{ className?: string }>> = {
    commit: GitCommit,
    pull_request: GitPullRequest,
    issue: AlertCircle,
  };
  const Icon = icons[event.event_type] || Github;

  const colors: Record<string, string> = {
    commit: 'text-green-500',
    pull_request: 'text-blue-500',
    issue: 'text-yellow-500',
  };
  const color = colors[event.event_type] || 'text-muted-foreground';

  return (
    <div className="flex items-start gap-3 py-2 border-b last:border-0">
      <div className={`p-1.5 rounded ${color} bg-muted`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{event.github_user || 'Unknown'}</span>
          <span className="text-xs text-muted-foreground">{event.event_type}</span>
        </div>
        {event.title && (
          <p className="text-sm text-muted-foreground truncate">
            {event.ref_url ? (
              <a href={event.ref_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                {event.title}
              </a>
            ) : (
              event.title
            )}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {event.repo_full_name} &middot; {formatDateTime(event.created_at, timezone)}
        </p>
      </div>
    </div>
  );
}
