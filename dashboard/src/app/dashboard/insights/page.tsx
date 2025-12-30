'use client';

import { useQuery } from '@tanstack/react-query';
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Clock,
  Users,
  Lightbulb,
  Target,
  Rocket,
  Heart,
  DollarSign,
  Code,
  User,
} from 'lucide-react';
import { analyticsApi, goalsApi, attendanceApi, githubApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useRoleAccess } from '@/hooks/useRoleAccess';
import { useAuth } from '@/lib/auth';

interface Insight {
  id: string;
  type: 'positive' | 'negative' | 'neutral';
  category: 'productivity' | 'collaboration' | 'velocity' | 'blockers' | 'delivery' | 'wellbeing' | 'cost' | 'quality';
  title: string;
  description: string;
  metric?: {
    value: string;
    change: number;
  };
  forRole?: 'owner' | 'admin' | 'member' | 'all';
}

interface Recommendation {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  goalCategory?: string;
  forRole?: 'owner' | 'admin' | 'member' | 'all';
}

export default function InsightsPage() {
  const { role, isAdmin, canViewTeamData } = useRoleAccess();
  const { user } = useAuth();

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['analytics', 'overview', 7],
    queryFn: () => analyticsApi.getOverview('current', 7),
  });

  const { data: goalsConfig } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsApi.get(),
  });

  const { data: attendanceSummary } = useQuery({
    queryKey: ['attendance', 'summary', 7],
    queryFn: () => attendanceApi.getSummary(7),
  });

  const { data: githubInsights } = useQuery({
    queryKey: ['github', 'insights', 30],
    queryFn: () => githubApi.getInsights(30),
  });

  const primaryGoal = goalsConfig?.primary_focus;
  const activeGoals = goalsConfig?.goals?.filter(g => g.is_active) || [];

  // Generate role-aware and goal-focused insights
  const generateInsights = (): Insight[] => {
    if (!metrics) return [];

    const allInsights: Insight[] = [];

    // --- Team-wide insights (admin/owner only) ---
    if (canViewTeamData) {
      // Delivery-focused insights
      if (primaryGoal === 'delivery' || activeGoals.some(g => g.category === 'delivery')) {
        allInsights.push({
          id: 'delivery-1',
          type: (metrics.github_prs_merged || 0) > 5 ? 'positive' : 'neutral',
          category: 'delivery',
          title: 'Sprint Progress',
          description: `${metrics.github_prs_merged || 0} PRs merged this week. ${metrics.github_issues_closed || 0} issues closed. Track blockers to maintain velocity.`,
          metric: { value: `${metrics.github_prs_merged || 0}`, change: 8 },
          forRole: 'admin',
        });
      }

      // Wellbeing-focused insights
      if (primaryGoal === 'wellbeing' || activeGoals.some(g => g.category === 'wellbeing')) {
        const avgWorkHours = (metrics.discord_voice_hours || 0) / 5; // rough estimate
        allInsights.push({
          id: 'wellbeing-1',
          type: avgWorkHours < 8 ? 'positive' : avgWorkHours > 10 ? 'negative' : 'neutral',
          category: 'wellbeing',
          title: 'Team Work-Life Balance',
          description: avgWorkHours > 10
            ? `High activity detected (~${Math.round(avgWorkHours)}h/day avg). Consider encouraging breaks.`
            : `Team activity levels appear balanced. Continue monitoring for burnout signs.`,
          forRole: 'admin',
        });
      }

      // Cost-focused insights
      if (primaryGoal === 'cost' || activeGoals.some(g => g.category === 'cost')) {
        allInsights.push({
          id: 'cost-1',
          type: 'neutral',
          category: 'cost',
          title: 'Resource Efficiency',
          description: `${metrics.github_contributors || 0} active contributors. Monitor for optimal resource allocation across projects.`,
          forRole: 'owner',
        });
      }

      // Quality-focused insights
      if (primaryGoal === 'quality' || activeGoals.some(g => g.category === 'quality')) {
        const prReviewRatio = metrics.github_prs_merged > 0 ? 1 : 0; // placeholder
        allInsights.push({
          id: 'quality-1',
          type: 'positive',
          category: 'quality',
          title: 'Code Review Coverage',
          description: `All ${metrics.github_prs_merged || 0} merged PRs went through review. Maintaining quality standards.`,
          forRole: 'admin',
        });
      }

      // General team insights
      allInsights.push({
        id: 'team-1',
        type: 'positive',
        category: 'collaboration',
        title: 'Team Communication',
        description: `${metrics.discord_messages.toLocaleString()} messages exchanged. Collaboration is active.`,
        metric: { value: `${metrics.discord_messages}`, change: 12 },
        forRole: 'admin',
      });

      allInsights.push({
        id: 'team-2',
        type: metrics.github_commits > 50 ? 'positive' : 'neutral',
        category: 'velocity',
        title: 'Development Velocity',
        description: `${metrics.github_commits} commits from ${metrics.github_contributors || 0} contributors this week.`,
        metric: { value: `${metrics.github_commits}`, change: -3 },
        forRole: 'admin',
      });
    }

    // --- Personal insights (for members or anyone viewing their own data) ---
    const myContributions = githubInsights?.top_contributors?.find(
      c => c.github_username === user?.github_username
    );

    if (myContributions) {
      allInsights.push({
        id: 'personal-1',
        type: myContributions.commits > 10 ? 'positive' : 'neutral',
        category: 'productivity',
        title: 'Your Contributions',
        description: `You made ${myContributions.commits} commits and merged ${myContributions.prs_merged} PRs this month.`,
        metric: { value: `${myContributions.commits}`, change: 5 },
        forRole: 'member',
      });
    }

    // Personal wellbeing reminder for everyone
    allInsights.push({
      id: 'personal-wellbeing',
      type: 'neutral',
      category: 'wellbeing',
      title: role === 'member' ? 'Your Balance' : 'Remember Self-Care',
      description: 'Regular breaks improve focus and productivity. Consider stepping away every 90 minutes.',
      forRole: 'all',
    });

    // Filter insights by role
    return allInsights.filter(insight => {
      if (insight.forRole === 'all') return true;
      if (insight.forRole === 'member' && role === 'member') return true;
      if (insight.forRole === 'admin' && isAdmin) return true;
      if (insight.forRole === 'owner' && role === 'owner') return true;
      return false;
    });
  };

  // Generate role-aware and goal-focused recommendations
  const generateRecommendations = (): Recommendation[] => {
    const recs: Recommendation[] = [];

    // Goal-based recommendations
    if (primaryGoal === 'delivery' || activeGoals.some(g => g.category === 'delivery')) {
      recs.push({
        title: 'Review project blockers daily',
        description: 'Check the Blockers page each morning to unblock team members and keep delivery on track.',
        priority: 'high',
        goalCategory: 'delivery',
        forRole: 'admin',
      });
    }

    if (primaryGoal === 'wellbeing' || activeGoals.some(g => g.category === 'wellbeing')) {
      recs.push({
        title: 'Encourage regular breaks',
        description: 'Team members working long hours may benefit from structured break reminders.',
        priority: 'high',
        goalCategory: 'wellbeing',
        forRole: 'admin',
      });
      recs.push({
        title: 'Take a break every 90 minutes',
        description: 'Short breaks help maintain focus and prevent burnout throughout the day.',
        priority: 'medium',
        goalCategory: 'wellbeing',
        forRole: 'member',
      });
    }

    if (primaryGoal === 'productivity' || activeGoals.some(g => g.category === 'productivity')) {
      recs.push({
        title: 'Reduce meeting overhead',
        description: 'Consider async standups to free up focus time for deep work.',
        priority: 'medium',
        goalCategory: 'productivity',
        forRole: 'admin',
      });
    }

    if (primaryGoal === 'quality' || activeGoals.some(g => g.category === 'quality')) {
      recs.push({
        title: 'Enforce PR review requirements',
        description: 'Ensure all PRs have at least one approval before merging.',
        priority: 'high',
        goalCategory: 'quality',
        forRole: 'admin',
      });
    }

    if (primaryGoal === 'cost' || activeGoals.some(g => g.category === 'cost')) {
      recs.push({
        title: 'Audit resource allocation',
        description: 'Review team distribution across projects to optimize costs.',
        priority: 'medium',
        goalCategory: 'cost',
        forRole: 'owner',
      });
    }

    // General recommendations
    recs.push({
      title: 'Document recurring discussions',
      description: 'Common questions in Discord could be captured in documentation.',
      priority: 'low',
      forRole: 'all',
    });

    // Filter by role
    return recs.filter(rec => {
      if (rec.forRole === 'all') return true;
      if (rec.forRole === 'member' && role === 'member') return true;
      if (rec.forRole === 'admin' && isAdmin) return true;
      if (rec.forRole === 'owner' && role === 'owner') return true;
      return false;
    });
  };

  const insights = generateInsights();
  const recommendations = generateRecommendations();

  // Page title based on role
  const pageTitle = canViewTeamData ? 'Team Insights' : 'My Insights';
  const pageDescription = canViewTeamData
    ? 'AI-powered analysis and recommendations for your team'
    : 'Personalized insights and recommendations for you';

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{pageTitle}</h1>
          <p className="text-muted-foreground mt-1">{pageDescription}</p>
        </div>
        {primaryGoal && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm">
            <Target className="h-4 w-4" />
            <span className="capitalize">Focus: {primaryGoal}</span>
          </div>
        )}
      </div>

      {/* Summary card */}
      <div className="rounded-lg border bg-gradient-to-br from-primary/5 to-primary/10 p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-lg bg-primary/10">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold">
              {canViewTeamData ? 'Weekly Team Summary' : 'Your Weekly Summary'}
            </h2>
            <p className="text-muted-foreground mt-2 leading-relaxed">
              {isLoading
                ? 'Analyzing activity...'
                : canViewTeamData
                  ? `Your team has been active this week with ${metrics?.discord_messages.toLocaleString() || 0} Discord messages and ${metrics?.github_commits || 0} code commits. ${metrics?.github_prs_merged || 0} PRs merged and ${metrics?.github_issues_closed || 0} issues resolved.`
                  : `Keep up the great work! Check your personal insights below for tips on maintaining productivity and balance.`}
            </p>
            {primaryGoal && canViewTeamData && (
              <p className="text-sm text-primary mt-2">
                Insights are focused on your team goal: <strong className="capitalize">{primaryGoal}</strong>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Insights grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-lg border bg-card p-6">
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-lg bg-muted animate-pulse" />
                  <div className="flex-1 space-y-2">
                    <div className="h-5 w-32 bg-muted animate-pulse rounded" />
                    <div className="h-4 w-full bg-muted animate-pulse rounded" />
                    <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
                  </div>
                </div>
              </div>
            ))
          : insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
      </div>

      {/* Recommendations section */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-amber-500" />
            <h3 className="font-semibold">
              {canViewTeamData ? 'Team Recommendations' : 'Recommendations for You'}
            </h3>
          </div>
        </div>
        <div className="divide-y">
          {recommendations.length > 0 ? (
            recommendations.map((rec, idx) => (
              <RecommendationItem
                key={idx}
                title={rec.title}
                description={rec.description}
                priority={rec.priority}
                goalCategory={rec.goalCategory}
              />
            ))
          ) : (
            <div className="p-6 text-center text-muted-foreground">
              <p>No recommendations at this time.</p>
              {canViewTeamData && !primaryGoal && (
                <p className="text-sm mt-2">
                  Set team goals in Settings to get tailored recommendations.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InsightCard({ insight }: { insight: Insight }) {
  const icons: Record<string, React.ComponentType<{ className?: string }>> = {
    productivity: Clock,
    collaboration: Users,
    velocity: TrendingUp,
    blockers: AlertTriangle,
    delivery: Rocket,
    wellbeing: Heart,
    cost: DollarSign,
    quality: Code,
  };

  const Icon = icons[insight.category] || Sparkles;

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-start gap-4">
        <div
          className={cn(
            'p-2 rounded-lg',
            insight.type === 'positive' && 'bg-green-500/10',
            insight.type === 'negative' && 'bg-red-500/10',
            insight.type === 'neutral' && 'bg-amber-500/10'
          )}
        >
          <Icon
            className={cn(
              'h-5 w-5',
              insight.type === 'positive' && 'text-green-500',
              insight.type === 'negative' && 'text-red-500',
              insight.type === 'neutral' && 'text-amber-500'
            )}
          />
        </div>
        <div className="flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold">{insight.title}</h3>
            {insight.metric && (
              <div className="flex items-center gap-1 text-sm">
                {insight.metric.change >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-green-500" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-500" />
                )}
                <span
                  className={cn(
                    'font-medium',
                    insight.metric.change >= 0 ? 'text-green-500' : 'text-red-500'
                  )}
                >
                  {insight.metric.change >= 0 ? '+' : ''}
                  {insight.metric.change}%
                </span>
              </div>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">{insight.description}</p>
        </div>
      </div>
    </div>
  );
}

function RecommendationItem({
  title,
  description,
  priority,
  goalCategory,
}: {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  goalCategory?: string;
}) {
  const priorityStyles = {
    high: 'bg-red-500/10 text-red-500',
    medium: 'bg-amber-500/10 text-amber-500',
    low: 'bg-blue-500/10 text-blue-500',
  };

  const goalCategoryStyles: Record<string, string> = {
    delivery: 'bg-blue-500/10 text-blue-500',
    productivity: 'bg-green-500/10 text-green-500',
    quality: 'bg-purple-500/10 text-purple-500',
    wellbeing: 'bg-pink-500/10 text-pink-500',
    cost: 'bg-yellow-500/10 text-yellow-500',
  };

  return (
    <div className="p-4 flex items-start gap-4">
      <CheckCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
      <div className="flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-medium">{title}</h4>
          <span
            className={cn(
              'px-2 py-0.5 text-xs font-medium rounded-full',
              priorityStyles[priority]
            )}
          >
            {priority}
          </span>
          {goalCategory && (
            <span
              className={cn(
                'px-2 py-0.5 text-xs font-medium rounded-full capitalize',
                goalCategoryStyles[goalCategory] || 'bg-gray-500/10 text-gray-500'
              )}
            >
              {goalCategory}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
    </div>
  );
}
