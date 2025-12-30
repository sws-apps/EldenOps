'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  DollarSign,
  TrendingUp,
  Brain,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  Shield,
  UserPlus,
  Code,
  GitBranch,
  Coffee,
  Heart,
  BarChart3,
  Briefcase,
  Target,
  AlertCircle,
  HelpCircle,
  UserCheck,
} from 'lucide-react';
import { attendanceApi, githubApi, type TeamStatusResponse } from '@/lib/api';
import { useTimezone, formatTime } from '@/lib/timezone';
import { cn } from '@/lib/utils';
import { useRoleAccess } from '@/hooks/useRoleAccess';

type ViewTab = 'health' | 'capacity' | 'cost' | 'technical';

export default function TeamPage() {
  const [activeTab, setActiveTab] = useState<ViewTab>('health');
  const { timezone } = useTimezone();
  const { canViewTeamData, isOwner } = useRoleAccess();

  // Fetch team status
  const { data: teamStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['attendance', 'status'],
    queryFn: () => attendanceApi.getTeamStatus(),
    refetchInterval: 30000,
  });

  // Fetch GitHub insights
  const { data: githubInsights } = useQuery({
    queryKey: ['github', 'insights', 30],
    queryFn: () => githubApi.getInsights(30),
  });

  const tabs = [
    { id: 'health' as const, label: 'Team Health', icon: Heart, description: 'Who needs support?' },
    { id: 'capacity' as const, label: 'Capacity', icon: BarChart3, description: 'Do we need more people?' },
    { id: 'cost' as const, label: 'Cost', icon: DollarSign, description: 'Are we efficient?', ownerOnly: true },
    { id: 'technical' as const, label: 'Technical', icon: Code, description: 'Knowledge & skills' },
  ];

  const visibleTabs = tabs.filter(tab => !tab.ownerOnly || isOwner);

  // Calculate team metrics
  const activeMembers = teamStatus?.team_status.filter(m => m.status === 'active') || [];
  const onBreakMembers = teamStatus?.team_status.filter(m => m.status === 'on_break') || [];
  const offlineMembers = teamStatus?.team_status.filter(m => m.status === 'offline') || [];
  const totalMembers = teamStatus?.team_status.length || 0;

  // Wellbeing analysis
  const analyzeWellbeing = () => {
    const concerns: { member: TeamStatusResponse['team_status'][0]; issues: string[]; severity: 'alert' | 'warning' }[] = [];

    teamStatus?.team_status.forEach(member => {
      const issues: string[] = [];
      let severity: 'alert' | 'warning' = 'warning';

      if (member.status === 'active' && member.today_stats?.checkin_at) {
        const checkinTime = new Date(member.today_stats.checkin_at);
        const hoursWorked = (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60);

        if (hoursWorked > 10) {
          issues.push(`Working ${Math.round(hoursWorked)}h today`);
          severity = 'alert';
        } else if (hoursWorked > 8) {
          issues.push(`Long day: ${Math.round(hoursWorked)}h`);
        }

        if (member.today_stats.break_count === 0 && hoursWorked > 4) {
          issues.push('No breaks taken');
        }
      }

      if (issues.length > 0) {
        concerns.push({ member, issues, severity });
      }
    });

    return concerns;
  };

  const wellbeingConcerns = analyzeWellbeing();

  // Capacity analysis
  const analyzeCapacity = () => {
    const utilization = totalMembers > 0 ? (activeMembers.length / totalMembers) * 100 : 0;
    const overworkedCount = wellbeingConcerns.filter(c => c.severity === 'alert').length;
    const healthyWorkload = wellbeingConcerns.length === 0;

    return {
      utilization: Math.round(utilization),
      overworkedCount,
      healthyWorkload,
      capacityStatus: overworkedCount > 0 ? 'strained' : utilization > 80 ? 'high' : utilization > 50 ? 'optimal' : 'low',
    };
  };

  const capacity = analyzeCapacity();

  // Technical analysis (bus factor, knowledge silos)
  const analyzeTechnical = () => {
    const contributors = githubInsights?.top_contributors || [];
    const totalCommits = contributors.reduce((sum, c) => sum + c.commits, 0);

    // Bus factor: how many people contribute 80% of code
    let cumulativeCommits = 0;
    let busFactor = 0;
    for (const contributor of contributors) {
      cumulativeCommits += contributor.commits;
      busFactor++;
      if (cumulativeCommits >= totalCommits * 0.8) break;
    }

    // Knowledge concentration
    const topContributorShare = contributors[0]
      ? Math.round((contributors[0].commits / totalCommits) * 100)
      : 0;

    return {
      busFactor: busFactor || 1,
      topContributorShare,
      hasKnowledgeSilo: topContributorShare > 50,
      totalContributors: contributors.length,
    };
  };

  const technical = analyzeTechnical();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Team</h1>
        <p className="text-muted-foreground mt-1">
          Team health, capacity, and insights
        </p>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-2 border-b">
        {visibleTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'health' && (
        <TeamHealthView
          teamStatus={teamStatus}
          wellbeingConcerns={wellbeingConcerns}
          timezone={timezone}
          loading={statusLoading}
        />
      )}

      {activeTab === 'capacity' && (
        <CapacityView
          capacity={capacity}
          teamStatus={teamStatus}
          wellbeingConcerns={wellbeingConcerns}
          loading={statusLoading}
        />
      )}

      {activeTab === 'cost' && isOwner && (
        <CostView
          teamStatus={teamStatus}
          capacity={capacity}
          loading={statusLoading}
        />
      )}

      {activeTab === 'technical' && (
        <TechnicalView
          technical={technical}
          githubInsights={githubInsights}
          loading={statusLoading}
        />
      )}
    </div>
  );
}

// ============ Team Health View (Manager) ============
function TeamHealthView({
  teamStatus,
  wellbeingConcerns,
  timezone,
  loading,
}: {
  teamStatus: TeamStatusResponse | undefined;
  wellbeingConcerns: { member: TeamStatusResponse['team_status'][0]; issues: string[]; severity: 'alert' | 'warning' }[];
  timezone: 'PT' | 'PHT';
  loading: boolean;
}) {
  const activeMembers = teamStatus?.team_status.filter(m => m.status === 'active') || [];
  const onBreakMembers = teamStatus?.team_status.filter(m => m.status === 'on_break') || [];

  return (
    <div className="space-y-6">
      {/* Key question */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <HelpCircle className="h-5 w-5 text-blue-500" />
          Who needs support?
        </h2>

        {wellbeingConcerns.length === 0 ? (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-green-500/10 text-green-700 dark:text-green-400">
            <CheckCircle2 className="h-6 w-6" />
            <div>
              <p className="font-semibold">Everyone looks good</p>
              <p className="text-sm opacity-80">No one is showing signs of overwork or burnout</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {wellbeingConcerns.map((concern, idx) => (
              <div
                key={idx}
                className={cn(
                  'flex items-center justify-between p-4 rounded-lg',
                  concern.severity === 'alert'
                    ? 'bg-red-500/10 border border-red-500/20'
                    : 'bg-yellow-500/10 border border-yellow-500/20'
                )}
              >
                <div className="flex items-center gap-3">
                  {concern.severity === 'alert' ? (
                    <Flame className="h-5 w-5 text-red-500" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                  )}
                  <div>
                    <p className="font-medium">{concern.member.discord_username}</p>
                    <p className="text-sm text-muted-foreground">{concern.issues.join(' · ')}</p>
                  </div>
                </div>
                <span className={cn(
                  'text-xs px-2 py-1 rounded-full',
                  concern.severity === 'alert' ? 'bg-red-500/20 text-red-600' : 'bg-yellow-500/20 text-yellow-600'
                )}>
                  {concern.severity === 'alert' ? 'Needs attention' : 'Watch'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Current status */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Working now */}
        <div className="rounded-lg border bg-card">
          <div className="p-4 border-b flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-green-500" />
              Working Now ({activeMembers.length})
            </h3>
          </div>
          <div className="p-4">
            {loading ? (
              <LoadingState />
            ) : activeMembers.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No one working</p>
            ) : (
              <div className="space-y-3">
                {activeMembers.map(member => {
                  const checkinTime = member.today_stats?.checkin_at ? new Date(member.today_stats.checkin_at) : null;
                  const hoursWorked = checkinTime ? (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60) : 0;
                  const isOverworked = hoursWorked > 8;

                  return (
                    <div key={member.user_id} className="flex items-center justify-between py-2">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'h-9 w-9 rounded-full flex items-center justify-center text-sm font-medium',
                          isOverworked ? 'bg-yellow-500/20' : 'bg-green-500/20'
                        )}>
                          {member.discord_username?.[0]?.toUpperCase() || '?'}
                        </div>
                        <div>
                          <p className="font-medium text-sm">{member.discord_username}</p>
                          <p className="text-xs text-muted-foreground">
                            {Math.round(hoursWorked)}h today · {member.today_stats?.break_count || 0} breaks
                          </p>
                        </div>
                      </div>
                      {isOverworked && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-600">
                          Long day
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* On break */}
        <div className="rounded-lg border bg-card">
          <div className="p-4 border-b">
            <h3 className="font-semibold flex items-center gap-2">
              <Coffee className="h-4 w-4 text-yellow-500" />
              On Break ({onBreakMembers.length})
            </h3>
          </div>
          <div className="p-4">
            {loading ? (
              <LoadingState />
            ) : onBreakMembers.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No one on break</p>
            ) : (
              <div className="space-y-3">
                {onBreakMembers.map(member => (
                  <div key={member.user_id} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-yellow-500/20 flex items-center justify-center text-sm font-medium">
                        {member.discord_username?.[0]?.toUpperCase() || '?'}
                      </div>
                      <div>
                        <p className="font-medium text-sm">{member.discord_username}</p>
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
  );
}

// ============ Capacity View (Hiring) ============
function CapacityView({
  capacity,
  teamStatus,
  wellbeingConcerns,
  loading,
}: {
  capacity: { utilization: number; overworkedCount: number; healthyWorkload: boolean; capacityStatus: string };
  teamStatus: TeamStatusResponse | undefined;
  wellbeingConcerns: { member: TeamStatusResponse['team_status'][0]; issues: string[]; severity: 'alert' | 'warning' }[];
  loading: boolean;
}) {
  const totalMembers = teamStatus?.team_status.length || 0;
  const activeCount = teamStatus?.summary.active || 0;

  const getCapacityColor = (status: string) => {
    switch (status) {
      case 'strained': return 'text-red-500';
      case 'high': return 'text-yellow-500';
      case 'optimal': return 'text-green-500';
      default: return 'text-blue-500';
    }
  };

  const getCapacityBg = (status: string) => {
    switch (status) {
      case 'strained': return 'bg-red-500/10 border-red-500/20';
      case 'high': return 'bg-yellow-500/10 border-yellow-500/20';
      case 'optimal': return 'bg-green-500/10 border-green-500/20';
      default: return 'bg-blue-500/10 border-blue-500/20';
    }
  };

  return (
    <div className="space-y-6">
      {/* Key question */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-blue-500" />
          Do we need to hire?
        </h2>

        <div className={cn('p-4 rounded-lg border', getCapacityBg(capacity.capacityStatus))}>
          <div className="flex items-center justify-between">
            <div>
              <p className={cn('text-2xl font-bold', getCapacityColor(capacity.capacityStatus))}>
                {capacity.capacityStatus === 'strained' ? 'Yes - Team is strained' :
                 capacity.capacityStatus === 'high' ? 'Watch - High utilization' :
                 capacity.capacityStatus === 'optimal' ? 'No - Capacity is good' :
                 'Maybe - Low utilization'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {capacity.overworkedCount > 0
                  ? `${capacity.overworkedCount} team member(s) showing signs of overwork`
                  : 'Workload appears balanced'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Team Size"
          value={totalMembers}
          subtitle="Total members"
          icon={Users}
        />
        <MetricCard
          label="Currently Active"
          value={`${activeCount}/${totalMembers}`}
          subtitle={`${capacity.utilization}% utilization`}
          icon={UserCheck}
          status={capacity.utilization > 80 ? 'warning' : 'good'}
        />
        <MetricCard
          label="Overworked"
          value={capacity.overworkedCount}
          subtitle={capacity.overworkedCount > 0 ? 'Need support' : 'All healthy'}
          icon={Flame}
          status={capacity.overworkedCount > 0 ? 'bad' : 'good'}
        />
      </div>

      {/* Workload distribution */}
      <div className="rounded-lg border bg-card">
        <div className="p-4 border-b">
          <h3 className="font-semibold flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Workload Distribution
          </h3>
        </div>
        <div className="p-4">
          {loading ? (
            <LoadingState />
          ) : (
            <div className="space-y-4">
              {teamStatus?.team_status.map(member => {
                const checkinTime = member.today_stats?.checkin_at ? new Date(member.today_stats.checkin_at) : null;
                const hoursWorked = checkinTime && member.status === 'active'
                  ? (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60)
                  : 0;
                const workloadPct = Math.min((hoursWorked / 8) * 100, 150);

                return (
                  <div key={member.user_id} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{member.discord_username}</span>
                      <span className="text-muted-foreground">
                        {member.status === 'active' ? `${Math.round(hoursWorked)}h today` : member.status}
                      </span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          workloadPct > 100 ? 'bg-red-500' :
                          workloadPct > 80 ? 'bg-yellow-500' : 'bg-green-500'
                        )}
                        style={{ width: `${Math.min(workloadPct, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Hiring signals */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-orange-500" />
          Hiring Signals
        </h3>
        <div className="space-y-3">
          <SignalItem
            signal="Team members consistently working overtime"
            detected={wellbeingConcerns.some(c => c.severity === 'alert')}
            impact="High burnout risk, quality may suffer"
          />
          <SignalItem
            signal="High utilization rate (>80%)"
            detected={capacity.utilization > 80}
            impact="No slack for unexpected work"
          />
          <SignalItem
            signal="Frequent missed breaks"
            detected={wellbeingConcerns.some(c => c.issues.includes('No breaks taken'))}
            impact="Team is stretched thin"
          />
        </div>
      </div>
    </div>
  );
}

// ============ Cost View (CFO) ============
function CostView({
  teamStatus,
  capacity,
  loading,
}: {
  teamStatus: TeamStatusResponse | undefined;
  capacity: { utilization: number; overworkedCount: number };
  loading: boolean;
}) {
  const activeCount = teamStatus?.summary.active || 0;
  const totalMembers = teamStatus?.team_status.length || 0;

  // Calculate overtime (rough estimate)
  let totalOvertimeHours = 0;
  teamStatus?.team_status.forEach(member => {
    if (member.status === 'active' && member.today_stats?.checkin_at) {
      const checkinTime = new Date(member.today_stats.checkin_at);
      const hoursWorked = (Date.now() - checkinTime.getTime()) / (1000 * 60 * 60);
      if (hoursWorked > 8) {
        totalOvertimeHours += hoursWorked - 8;
      }
    }
  });

  return (
    <div className="space-y-6">
      {/* Key question */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-green-500" />
          Are we cost-efficient?
        </h2>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="p-4 rounded-lg bg-muted/50">
            <p className="text-sm text-muted-foreground">Utilization Rate</p>
            <p className={cn(
              'text-3xl font-bold mt-1',
              capacity.utilization > 80 ? 'text-yellow-500' :
              capacity.utilization > 50 ? 'text-green-500' : 'text-blue-500'
            )}>
              {capacity.utilization}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {capacity.utilization > 80 ? 'High - watch for burnout' :
               capacity.utilization > 50 ? 'Optimal range' : 'Low - capacity available'}
            </p>
          </div>
          <div className="p-4 rounded-lg bg-muted/50">
            <p className="text-sm text-muted-foreground">Overtime Today</p>
            <p className={cn(
              'text-3xl font-bold mt-1',
              totalOvertimeHours > 4 ? 'text-red-500' :
              totalOvertimeHours > 0 ? 'text-yellow-500' : 'text-green-500'
            )}>
              {Math.round(totalOvertimeHours)}h
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalOvertimeHours > 4 ? 'Significant overtime cost' :
               totalOvertimeHours > 0 ? 'Some overtime' : 'No overtime'}
            </p>
          </div>
        </div>
      </div>

      {/* Cost insights */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Cost Insights</h3>
        <div className="space-y-4">
          <InsightRow
            label="Active vs Total"
            value={`${activeCount} of ${totalMembers} working`}
            status={capacity.utilization > 50 ? 'good' : 'neutral'}
          />
          <InsightRow
            label="Overtime Risk"
            value={capacity.overworkedCount > 0 ? `${capacity.overworkedCount} at risk` : 'None detected'}
            status={capacity.overworkedCount > 0 ? 'warning' : 'good'}
          />
          <InsightRow
            label="Break Compliance"
            value="Track break patterns for compliance"
            status="neutral"
          />
        </div>

        <div className="mt-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-sm text-blue-700 dark:text-blue-400">
            <strong>Note:</strong> Connect payroll/HR system to see actual cost data like salaries, contractor spend, and cost per project.
          </p>
        </div>
      </div>
    </div>
  );
}

// ============ Technical View (CTO) ============
function TechnicalView({
  technical,
  githubInsights,
  loading,
}: {
  technical: { busFactor: number; topContributorShare: number; hasKnowledgeSilo: boolean; totalContributors: number };
  githubInsights: any;
  loading: boolean;
}) {
  return (
    <div className="space-y-6">
      {/* Key question */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-500" />
          Is knowledge spread well?
        </h2>

        <div className={cn(
          'p-4 rounded-lg border',
          technical.hasKnowledgeSilo
            ? 'bg-yellow-500/10 border-yellow-500/20'
            : 'bg-green-500/10 border-green-500/20'
        )}>
          <div className="flex items-center gap-3">
            {technical.hasKnowledgeSilo ? (
              <AlertTriangle className="h-6 w-6 text-yellow-500" />
            ) : (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            )}
            <div>
              <p className={cn(
                'text-xl font-bold',
                technical.hasKnowledgeSilo ? 'text-yellow-600' : 'text-green-600'
              )}>
                {technical.hasKnowledgeSilo
                  ? 'Knowledge Silo Detected'
                  : 'Knowledge is Well Distributed'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {technical.hasKnowledgeSilo
                  ? `Top contributor owns ${technical.topContributorShare}% of recent code`
                  : 'No single person dominates the codebase'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Technical metrics */}
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Bus Factor"
          value={technical.busFactor}
          subtitle={technical.busFactor <= 1 ? 'Critical risk!' : technical.busFactor <= 2 ? 'Low - improve' : 'Acceptable'}
          icon={AlertTriangle}
          status={technical.busFactor <= 1 ? 'bad' : technical.busFactor <= 2 ? 'warning' : 'good'}
        />
        <MetricCard
          label="Top Contributor"
          value={`${technical.topContributorShare}%`}
          subtitle="Of recent commits"
          icon={Code}
          status={technical.topContributorShare > 50 ? 'warning' : 'good'}
        />
        <MetricCard
          label="Contributors"
          value={technical.totalContributors}
          subtitle="Active in codebase"
          icon={Users}
        />
      </div>

      {/* Contributors breakdown */}
      <div className="rounded-lg border bg-card">
        <div className="p-4 border-b">
          <h3 className="font-semibold flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Code Ownership (30 days)
          </h3>
        </div>
        <div className="p-4">
          {!githubInsights?.top_contributors?.length ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No GitHub data available
            </p>
          ) : (
            <div className="space-y-4">
              {githubInsights.top_contributors.slice(0, 5).map((contributor: any, idx: number) => {
                const totalCommits = githubInsights.top_contributors.reduce((sum: number, c: any) => sum + c.commits, 0);
                const share = totalCommits > 0 ? Math.round((contributor.commits / totalCommits) * 100) : 0;

                return (
                  <div key={contributor.github_username} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{contributor.github_username}</span>
                      <span className="text-muted-foreground">{share}% ({contributor.commits} commits)</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          share > 50 ? 'bg-yellow-500' :
                          share > 30 ? 'bg-blue-500' : 'bg-green-500'
                        )}
                        style={{ width: `${share}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Recommendations */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Target className="h-4 w-4 text-blue-500" />
          Technical Recommendations
        </h3>
        <div className="space-y-3">
          {technical.busFactor <= 2 && (
            <RecommendationItem
              text="Increase code reviews from other team members"
              priority="high"
            />
          )}
          {technical.hasKnowledgeSilo && (
            <RecommendationItem
              text="Pair programming sessions to spread knowledge"
              priority="high"
            />
          )}
          <RecommendationItem
            text="Document critical systems and processes"
            priority="medium"
          />
          <RecommendationItem
            text="Rotate ownership of key components"
            priority="medium"
          />
        </div>
      </div>
    </div>
  );
}

// ============ Shared Components ============

function MetricCard({
  label,
  value,
  subtitle,
  icon: Icon,
  status = 'neutral',
}: {
  label: string;
  value: string | number;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  status?: 'good' | 'warning' | 'bad' | 'neutral';
}) {
  const statusColors = {
    good: 'border-green-500/20 bg-green-500/5',
    warning: 'border-yellow-500/20 bg-yellow-500/5',
    bad: 'border-red-500/20 bg-red-500/5',
    neutral: 'border-muted',
  };

  const valueColors = {
    good: 'text-green-500',
    warning: 'text-yellow-500',
    bad: 'text-red-500',
    neutral: 'text-foreground',
  };

  return (
    <div className={cn('rounded-lg border p-4', statusColors[status])}>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <p className={cn('text-2xl font-bold mt-2', valueColors[status])}>{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
    </div>
  );
}

function SignalItem({
  signal,
  detected,
  impact,
}: {
  signal: string;
  detected: boolean;
  impact: string;
}) {
  return (
    <div className={cn(
      'flex items-center justify-between p-3 rounded-lg',
      detected ? 'bg-red-500/10' : 'bg-muted/50'
    )}>
      <div className="flex items-center gap-3">
        {detected ? (
          <AlertCircle className="h-5 w-5 text-red-500" />
        ) : (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        )}
        <div>
          <p className="font-medium text-sm">{signal}</p>
          <p className="text-xs text-muted-foreground">{impact}</p>
        </div>
      </div>
      <span className={cn(
        'text-xs px-2 py-1 rounded-full',
        detected ? 'bg-red-500/20 text-red-600' : 'bg-green-500/20 text-green-600'
      )}>
        {detected ? 'Detected' : 'Not detected'}
      </span>
    </div>
  );
}

function InsightRow({
  label,
  value,
  status = 'neutral',
}: {
  label: string;
  value: string;
  status?: 'good' | 'warning' | 'neutral';
}) {
  const statusColors = {
    good: 'text-green-500',
    warning: 'text-yellow-500',
    neutral: 'text-muted-foreground',
  };

  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <span className="text-sm">{label}</span>
      <span className={cn('text-sm font-medium', statusColors[status])}>{value}</span>
    </div>
  );
}

function RecommendationItem({
  text,
  priority,
}: {
  text: string;
  priority: 'high' | 'medium' | 'low';
}) {
  const priorityColors = {
    high: 'bg-red-500/10 text-red-600 border-red-500/20',
    medium: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    low: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
      <span className={cn('text-xs px-2 py-0.5 rounded border', priorityColors[priority])}>
        {priority}
      </span>
      <span className="text-sm">{text}</span>
    </div>
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
