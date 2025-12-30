'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Coffee,
  Heart,
  HelpCircle,
  Rocket,
  Target,
  TrendingDown,
  TrendingUp,
  UserCheck,
  Users,
  XCircle,
  Calendar,
  ArrowRight,
  Flame,
  Shield,
} from 'lucide-react';
import Link from 'next/link';
import { attendanceApi, githubApi, goalsApi, projectsApi, type TeamStatusResponse } from '@/lib/api';
import { useTimezone, formatTime } from '@/lib/timezone';
import { useRoleAccess } from '@/hooks/useRoleAccess';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const { timezone } = useTimezone();
  const { role, isAdmin, canViewTeamData } = useRoleAccess();
  const { user, currentTenantId } = useAuth();

  // Fetch team status
  const { data: teamStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['attendance', 'status'],
    queryFn: () => attendanceApi.getTeamStatus(),
    refetchInterval: 30000,
  });

  // Fetch goals
  const { data: goalsConfig } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsApi.get(),
  });

  // Fetch attendance insights for wellbeing signals
  const { data: attendanceInsights } = useQuery({
    queryKey: ['attendance', 'insights', 30],
    queryFn: () => attendanceApi.getInsights(30),
  });

  // Fetch GitHub summary
  const { data: githubSummary } = useQuery({
    queryKey: ['github', 'summary', 7],
    queryFn: () => githubApi.getSummary(7),
  });

  const primaryGoal = goalsConfig?.primary_focus;

  // Calculate key metrics
  const activeCount = teamStatus?.summary.active || 0;
  const onBreakCount = teamStatus?.summary.on_break || 0;
  const totalTeam = teamStatus?.team_status.length || 0;

  // Detect wellbeing concerns
  const detectWellbeingConcerns = () => {
    const concerns: { user: string; issue: string; severity: 'warning' | 'alert' }[] = [];

    teamStatus?.team_status.forEach(member => {
      // Long work hours (checked in for 10+ hours)
      if (member.status === 'active' && member.today_stats?.checkin_at) {
        const checkinTime = new Date(member.today_stats.checkin_at);
        const hoursWorked = (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60);
        if (hoursWorked > 10) {
          concerns.push({
            user: member.discord_username || 'Unknown',
            issue: `Working ${Math.round(hoursWorked)}+ hours today`,
            severity: 'alert',
          });
        } else if (hoursWorked > 8) {
          concerns.push({
            user: member.discord_username || 'Unknown',
            issue: `Working ${Math.round(hoursWorked)}+ hours today`,
            severity: 'warning',
          });
        }
      }

      // No breaks taken
      if (member.status === 'active' && member.today_stats?.break_count === 0 && member.today_stats?.checkin_at) {
        const checkinTime = new Date(member.today_stats.checkin_at);
        const hoursWorked = (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60);
        if (hoursWorked > 4) {
          concerns.push({
            user: member.discord_username || 'Unknown',
            issue: 'No breaks in 4+ hours',
            severity: 'warning',
          });
        }
      }
    });

    return concerns;
  };

  const wellbeingConcerns = detectWellbeingConcerns();

  // Calculate overall status
  const getOverallStatus = () => {
    if (wellbeingConcerns.some(c => c.severity === 'alert')) {
      return { status: 'needs-attention', label: 'Needs Attention', color: 'text-red-500' };
    }
    if (wellbeingConcerns.length > 0) {
      return { status: 'watch', label: 'Watch', color: 'text-yellow-500' };
    }
    return { status: 'healthy', label: 'Healthy', color: 'text-green-500' };
  };

  const overallStatus = getOverallStatus();

  // Page title based on role
  const pageTitle = canViewTeamData ? 'Mission Control' : 'My Dashboard';
  const pageDescription = canViewTeamData
    ? 'Are we on track? Is the team healthy?'
    : 'Your personal productivity hub';

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{pageTitle}</h1>
          <p className="text-muted-foreground mt-1">{pageDescription}</p>
        </div>
        {primaryGoal && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm">
            <Target className="h-4 w-4" />
            <span className="capitalize">Goal: {primaryGoal}</span>
          </div>
        )}
      </div>

      {/* Key Questions - Big Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* On Track? */}
        <KeyMetricCard
          question="On Track?"
          answer={githubSummary?.totals?.prs ? 'Yes' : 'No Data'}
          status={githubSummary?.totals?.prs ? 'good' : 'neutral'}
          detail={`${githubSummary?.totals?.prs || 0} PRs merged this week`}
          icon={Rocket}
          loading={statusLoading}
        />

        {/* Team Health */}
        <KeyMetricCard
          question="Team Health"
          answer={overallStatus.label}
          status={overallStatus.status === 'healthy' ? 'good' : overallStatus.status === 'watch' ? 'warning' : 'bad'}
          detail={wellbeingConcerns.length > 0 ? `${wellbeingConcerns.length} concern(s)` : 'All good'}
          icon={Heart}
          loading={statusLoading}
        />

        {/* Blockers */}
        <KeyMetricCard
          question="Blockers"
          answer={githubSummary?.totals?.issues ? `${githubSummary.totals.issues}` : '0'}
          status={githubSummary?.totals?.issues && githubSummary.totals.issues > 5 ? 'warning' : 'good'}
          detail="Open issues"
          icon={AlertTriangle}
          loading={statusLoading}
          href="/dashboard/blockers"
        />

        {/* Who's Working */}
        <KeyMetricCard
          question="Who's Working"
          answer={`${activeCount}/${totalTeam}`}
          status={activeCount > 0 ? 'good' : 'neutral'}
          detail={onBreakCount > 0 ? `${onBreakCount} on break` : 'Team online'}
          icon={Users}
          loading={statusLoading}
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column - Delivery Focus */}
        <div className="space-y-6">
          {/* What's Happening Now */}
          <div className="rounded-lg border bg-card">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-500" />
                Right Now
              </h3>
            </div>
            <div className="p-4 space-y-3">
              {statusLoading ? (
                <LoadingState />
              ) : teamStatus?.team_status.filter(u => u.status === 'active').length === 0 ? (
                <EmptyState message="No one is currently working" />
              ) : (
                teamStatus?.team_status
                  .filter(u => u.status === 'active')
                  .slice(0, 4)
                  .map(member => (
                    <ActiveMemberRow key={member.user_id} member={member} timezone={timezone} />
                  ))
              )}
              {(teamStatus?.team_status.filter(u => u.status === 'active').length || 0) > 4 && (
                <Link
                  href="/dashboard/team"
                  className="block text-center text-sm text-muted-foreground hover:text-foreground py-2"
                >
                  +{(teamStatus?.team_status.filter(u => u.status === 'active').length || 0) - 4} more →
                </Link>
              )}
            </div>
          </div>

          {/* This Week's Progress */}
          <div className="rounded-lg border bg-card">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                This Week
              </h3>
              <Link
                href="/dashboard/github"
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Details →
              </Link>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-500">{githubSummary?.totals?.prs || 0}</p>
                  <p className="text-xs text-muted-foreground mt-1">PRs Shipped</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-blue-500">{githubSummary?.totals?.issues || 0}</p>
                  <p className="text-xs text-muted-foreground mt-1">Issues Open</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-purple-500">{githubSummary?.totals?.contributors || 0}</p>
                  <p className="text-xs text-muted-foreground mt-1">Contributing</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Team Health */}
        <div className="space-y-6">
          {/* Wellbeing Alerts */}
          <div className="rounded-lg border bg-card">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
                <Shield className="h-4 w-4 text-pink-500" />
                Team Wellbeing
              </h3>
            </div>
            <div className="p-4">
              {wellbeingConcerns.length === 0 ? (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-green-500/10 text-green-700 dark:text-green-400">
                  <CheckCircle2 className="h-5 w-5" />
                  <div>
                    <p className="font-medium">All Good</p>
                    <p className="text-sm opacity-80">No wellbeing concerns detected</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {wellbeingConcerns.map((concern, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        'flex items-center gap-3 p-3 rounded-lg',
                        concern.severity === 'alert'
                          ? 'bg-red-500/10 text-red-700 dark:text-red-400'
                          : 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400'
                      )}
                    >
                      {concern.severity === 'alert' ? (
                        <Flame className="h-5 w-5" />
                      ) : (
                        <AlertTriangle className="h-5 w-5" />
                      )}
                      <div>
                        <p className="font-medium">{concern.user}</p>
                        <p className="text-sm opacity-80">{concern.issue}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* On Break */}
          <div className="rounded-lg border bg-card">
            <div className="p-4 border-b">
              <h3 className="font-semibold flex items-center gap-2">
                <Coffee className="h-4 w-4 text-yellow-500" />
                Taking a Break ({onBreakCount})
              </h3>
            </div>
            <div className="p-4">
              {statusLoading ? (
                <LoadingState />
              ) : onBreakCount === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-2">
                  No one on break right now
                </p>
              ) : (
                <div className="space-y-2">
                  {teamStatus?.team_status
                    .filter(u => u.status === 'on_break')
                    .map(member => (
                      <div key={member.user_id} className="flex items-center justify-between py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-8 w-8 rounded-full bg-yellow-500/20 flex items-center justify-center text-sm font-medium">
                            {member.discord_username?.[0]?.toUpperCase() || '?'}
                          </div>
                          <div>
                            <p className="text-sm font-medium">{member.discord_username}</p>
                            {member.current_break_reason && (
                              <p className="text-xs text-muted-foreground">{member.current_break_reason}</p>
                            )}
                          </div>
                        </div>
                        {member.expected_return_at && (
                          <span className="text-xs text-muted-foreground">
                            Back ~{formatTime(member.expected_return_at, timezone)}
                          </span>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-4">Quick Actions</h3>
        <div className="grid gap-3 md:grid-cols-4">
          <QuickAction
            href="/dashboard/insights"
            icon={Target}
            label="View Insights"
            description="AI recommendations"
          />
          <QuickAction
            href="/dashboard/blockers"
            icon={AlertTriangle}
            label="Check Blockers"
            description="Unblock the team"
          />
          <QuickAction
            href="/dashboard/team"
            icon={Users}
            label="Team Status"
            description="Who's doing what"
          />
          <QuickAction
            href="/dashboard/settings"
            icon={Target}
            label="Set Goals"
            description="Configure focus"
          />
        </div>
      </div>
    </div>
  );
}

function KeyMetricCard({
  question,
  answer,
  status,
  detail,
  icon: Icon,
  loading,
  href,
}: {
  question: string;
  answer: string;
  status: 'good' | 'warning' | 'bad' | 'neutral';
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  href?: string;
}) {
  const statusColors = {
    good: 'border-green-500/30 bg-green-500/5',
    warning: 'border-yellow-500/30 bg-yellow-500/5',
    bad: 'border-red-500/30 bg-red-500/5',
    neutral: 'border-muted bg-muted/5',
  };

  const answerColors = {
    good: 'text-green-500',
    warning: 'text-yellow-500',
    bad: 'text-red-500',
    neutral: 'text-muted-foreground',
  };

  const content = (
    <div className={cn('rounded-lg border p-4 transition-colors', statusColors[status], href && 'hover:bg-accent cursor-pointer')}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{question}</p>
          {loading ? (
            <div className="h-8 w-16 bg-muted animate-pulse rounded mt-1" />
          ) : (
            <p className={cn('text-2xl font-bold mt-1', answerColors[status])}>{answer}</p>
          )}
          <p className="text-xs text-muted-foreground mt-1">{detail}</p>
        </div>
        <Icon className={cn('h-5 w-5', answerColors[status])} />
      </div>
    </div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
}

function ActiveMemberRow({
  member,
  timezone,
}: {
  member: TeamStatusResponse['team_status'][0];
  timezone: 'PT' | 'PHT';
}) {
  const checkinTime = member.today_stats?.checkin_at ? new Date(member.today_stats.checkin_at) : null;
  const hoursWorked = checkinTime ? (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60) : 0;

  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-3">
        <div className="relative">
          <div className="h-9 w-9 rounded-full bg-green-500/20 flex items-center justify-center text-sm font-medium">
            {member.discord_username?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full bg-green-500 border-2 border-card" />
        </div>
        <div>
          <p className="font-medium text-sm">{member.discord_username}</p>
          {checkinTime && (
            <p className="text-xs text-muted-foreground">
              {Math.round(hoursWorked)}h today
            </p>
          )}
        </div>
      </div>
      {hoursWorked > 8 && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-600">
          Long day
        </span>
      )}
    </div>
  );
}

function QuickAction({
  href,
  icon: Icon,
  label,
  description,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors"
    >
      <Icon className="h-5 w-5 text-muted-foreground" />
      <div>
        <p className="font-medium text-sm">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </Link>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full bg-muted animate-pulse" />
          <div className="flex-1 space-y-1">
            <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            <div className="h-3 w-16 bg-muted animate-pulse rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-6">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
