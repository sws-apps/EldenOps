import { useAuth } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private getAuthHeader(): Record<string, string> {
    const { accessToken } = useAuth.getState();
    return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
    const url = new URL(path, this.baseUrl || window.location.origin);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }

  async fetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options;

    const url = this.buildUrl(path, params);

    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
        ...fetchOptions.headers,
      },
    });

    if (response.status === 401) {
      // Try to refresh token
      const { refreshAuth, logout } = useAuth.getState();
      const refreshed = await refreshAuth();

      if (refreshed) {
        // Retry the request
        return this.fetch(path, options);
      } else {
        logout();
        throw new Error('Authentication required');
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Convenience methods
  get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.fetch<T>(path, { method: 'GET', params });
  }

  post<T>(path: string, data?: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(path: string, data?: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  patch<T>(path: string, data?: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  delete<T>(path: string): Promise<T> {
    return this.fetch<T>(path, { method: 'DELETE' });
  }
}

export const api = new ApiClient();

// API Types
export interface OverviewMetrics {
  discord_messages: number;
  discord_active_users: number;
  discord_voice_hours: number;
  github_commits: number;
  github_contributors: number;
  github_prs_opened: number;
  github_prs_merged: number;
  github_issues_opened: number;
  github_issues_closed: number;
  period_days: number;
}

export interface Contributor {
  user_id: string;
  discord_username: string | null;
  github_username: string | null;
  avatar_url?: string;
  discord_messages: number;
  github_commits: number;
  github_prs: number;
  total_score: number;
}

export interface ActivityDataPoint {
  date: string;
  discord_messages: number;
  github_commits: number;
  github_prs: number;
}

export interface UserActivitySummary {
  user_id: string;
  discord_username: string | null;
  github_username: string | null;
  discord_messages: number;
  discord_voice_minutes: number;
  github_commits: number;
  github_prs: number;
  github_reviews: number;
}

export interface Report {
  id: string;
  config_id: string | null;
  report_type: string;
  title: string;
  date_range_start: string | null;
  date_range_end: string | null;
  content: Record<string, unknown>;
  ai_summary: string | null;
  generated_at: string;
}

export interface Tenant {
  id: string;
  discord_guild_id: number;
  guild_name: string | null;
  settings: Record<string, unknown>;
  is_active: boolean;
}

// Attendance types
export interface UserAttendanceStatus {
  user_id: string;
  discord_id: number;
  discord_username: string | null;
  status: 'active' | 'on_break' | 'offline' | 'unknown';
  last_checkin_at: string | null;
  last_checkout_at: string | null;
  last_break_start_at: string | null;
  current_break_reason: string | null;
  expected_return_at: string | null;
  today_stats: {
    checkin_at?: string;
    checkout_at?: string;
    break_count?: number;
    total_break_minutes?: number;
  };
}

export interface TeamStatusResponse {
  team_status: UserAttendanceStatus[];
  summary: {
    active: number;
    on_break: number;
    offline: number;
    unknown: number;
  };
}

export interface AttendanceSummary {
  period_days: number;
  event_counts: {
    checkin?: number;
    checkout?: number;
    break_start?: number;
    break_end?: number;
  };
  unique_users: number;
  total_events: number;
}

// API Functions
export const analyticsApi = {
  getOverview: (tenantId: string, days: number = 7) =>
    api.get<OverviewMetrics>('/api/v1/analytics/overview', { days }),

  getActivity: (tenantId: string, days: number = 7, granularity: string = 'daily') =>
    api.get<ActivityDataPoint[]>('/api/v1/analytics/activity', { days, granularity }),

  getUsers: (tenantId: string, days: number = 7) =>
    api.get<UserActivitySummary[]>('/api/v1/analytics/users', { days }),

  getTopContributors: (tenantId: string, days: number = 7, limit: number = 10) =>
    api.get<Contributor[]>('/api/v1/analytics/contributors', { days, limit }),

  getActivityHeatmap: (tenantId: string, days: number = 7) =>
    api.get<number[][]>('/api/v1/analytics/heatmap', { days }),
};

export const reportsApi = {
  list: (tenantId: string, limit: number = 10, offset: number = 0) =>
    api.get<Report[]>('/api/v1/reports', { limit, offset }),

  get: (reportId: string) =>
    api.get<Report>(`/api/v1/reports/${reportId}`),

  generate: (tenantId: string, reportType: string, days: number = 7) =>
    api.post<Report>('/api/v1/reports/generate', { report_type: reportType, days }),
};

export const tenantsApi = {
  list: () =>
    api.get<{ tenants: Tenant[]; total: number }>('/api/v1/tenants'),

  get: (tenantId: string) =>
    api.get<Tenant>(`/api/v1/tenants/${tenantId}`),
};

export interface AttendanceInsights {
  period_days: number;
  has_data: boolean;
  message?: string;
  checkin_patterns?: {
    peak_hours: Array<{ hour: number; count: number; time: string }>;
    average_time: string | null;
    hour_distribution: Record<string, number>;
  };
  checkout_patterns?: {
    peak_hours: Array<{ hour: number; count: number; time: string }>;
    average_time: string | null;
    hour_distribution: Record<string, number>;
  };
  break_patterns?: {
    peak_hours: Array<{ hour: number; count: number; time: string }>;
    average_time: string | null;
    hour_distribution: Record<string, number>;
    reasons: Array<{ reason: string; count: number }>;
    long_breaks: Array<{
      username: string;
      duration_minutes: number;
      reason: string;
      time: string;
    }>;
  };
  team_insights?: {
    early_birds: Array<{ username: string; avg_checkin_time: string }>;
    night_owls: Array<{ username: string; avg_checkout_time: string }>;
    most_breaks: Array<{ username: string; break_count: number }>;
  };
}

// GitHub types
export interface GitHubRepoSummary {
  repo_full_name: string;
  total_commits: number;
  total_prs: number;
  total_issues: number;
  contributors: number;
  lines_added: number;
  lines_deleted: number;
}

export interface GitHubSummary {
  period_days: number;
  repos: GitHubRepoSummary[];
  totals: {
    commits: number;
    prs: number;
    issues: number;
    contributors: number;
    lines_added: number;
    lines_deleted: number;
  };
}

export interface GitHubContributor {
  github_username: string;
  commits: number;
  prs_opened: number;
  prs_merged: number;
  issues_opened: number;
  lines_added: number;
  lines_deleted: number;
}

export interface GitHubInsights {
  period_days: number;
  has_data: boolean;
  message?: string;
  commit_patterns?: {
    peak_hour: string | null;
    average_hour: string | null;
    hour_distribution: Record<string, number>;
    total: number;
  };
  pr_patterns?: {
    peak_hour: string | null;
    average_hour: string | null;
    hour_distribution: Record<string, number>;
    total: number;
  };
  top_contributors?: GitHubContributor[];
  activity_by_day?: Record<string, number>;
  activity_by_hour?: Record<string, number>;
}

export interface GitHubActivity {
  id: string;
  event_type: string;
  repo_full_name: string;
  github_user: string | null;
  title: string | null;
  ref_id: string | null;
  ref_url: string | null;
  additions: number | null;
  deletions: number | null;
  files_changed: number | null;
  created_at: string;
}

export interface GitHubConnection {
  id: string;
  repo_full_name: string;
  org_name: string | null;
  repo_name: string;
  last_synced_at: string | null;
  is_active: boolean;
}

export const githubApi = {
  getSummary: (days: number = 7) =>
    api.get<GitHubSummary>('/api/v1/github/summary', { days }),

  getInsights: (days: number = 30) =>
    api.get<GitHubInsights>('/api/v1/github/insights', { days }),

  getActivity: (days: number = 7, limit: number = 50) =>
    api.get<GitHubActivity[]>('/api/v1/github/activity', { days, limit }),

  getConnections: () =>
    api.get<GitHubConnection[]>('/api/v1/github/connections'),

  addConnection: (repoFullName: string) =>
    api.post<GitHubConnection>('/api/v1/github/connections', { repo_full_name: repoFullName }),

  removeConnection: (connectionId: string) =>
    api.delete<{ message: string }>(`/api/v1/github/connections/${connectionId}`),

  syncConnection: (connectionId: string, days: number = 30) =>
    api.fetch<{ status: string; repo: string; commits_synced: number; prs_synced: number; issues_synced: number }>(
      `/api/v1/github/connections/${connectionId}/sync`,
      { method: 'POST', params: { days } }
    ),
};

// AI Provider types and API
export interface AIProviderConfig {
  id: string;
  provider: string;
  is_default: boolean;
  is_active: boolean;
}

export const aiProvidersApi = {
  list: (tenantId: string) =>
    api.get<AIProviderConfig[]>(`/api/v1/tenants/${tenantId}/ai-providers`),

  add: (tenantId: string, provider: string, apiKey: string, isDefault: boolean = false) =>
    api.post<AIProviderConfig>(`/api/v1/tenants/${tenantId}/ai-providers`, {
      provider,
      api_key: apiKey,
      is_default: isDefault,
    }),

  update: (tenantId: string, providerId: string, data: { api_key?: string; is_default?: boolean }) =>
    api.fetch<AIProviderConfig>(`/api/v1/tenants/${tenantId}/ai-providers/${providerId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (tenantId: string, providerId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/ai-providers/${providerId}`),
};

// GitHub token types
export interface GitHubTokenStatus {
  is_configured: boolean;
  is_valid?: boolean;
  token_preview?: string;
}

export const githubTokenApi = {
  getStatus: (tenantId: string) =>
    api.get<GitHubTokenStatus>(`/api/v1/tenants/${tenantId}/github-token`),

  setToken: (tenantId: string, token: string) =>
    api.post<GitHubTokenStatus>(`/api/v1/tenants/${tenantId}/github-token`, { token }),

  removeToken: (tenantId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/github-token`),
};

// Monitored channels types and API
export interface MonitoredChannel {
  id: string;
  channel_id: number;
  channel_name: string | null;
  channel_type: string;
  is_active: boolean;
}

export const channelsApi = {
  list: (tenantId: string) =>
    api.get<MonitoredChannel[]>(`/api/v1/tenants/${tenantId}/channels`),

  add: (tenantId: string, channelId: number, channelName: string, channelType: string = 'text') =>
    api.post<MonitoredChannel>(`/api/v1/tenants/${tenantId}/channels`, {
      channel_id: channelId,
      channel_name: channelName,
      channel_type: channelType,
    }),

  remove: (tenantId: string, channelId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/channels/${channelId}`),
};

export const attendanceApi = {
  getTeamStatus: () =>
    api.get<TeamStatusResponse>('/api/v1/attendance/status'),

  getSummary: (days: number = 7) =>
    api.get<AttendanceSummary>('/api/v1/attendance/summary', { days }),

  getInsights: (days: number = 30) =>
    api.get<AttendanceInsights>('/api/v1/attendance/insights', { days }),

  getUserHistory: (userId: string, days: number = 7) =>
    api.get<unknown[]>(`/api/v1/attendance/users/${userId}/history`, { days }),

  getUserPatterns: (userId: string, days: number = 30) =>
    api.get<unknown>(`/api/v1/attendance/users/${userId}/patterns`, { days }),
};

// Project and Team Management types
export interface ProjectConfig {
  id: string;
  task_channel_id: number | null;
  task_channel_name: string | null;
  thread_name_pattern: string;
  auto_create_projects: boolean;
  report_config: Record<string, unknown>;
  default_kpis: Record<string, unknown>;
  ai_config: Record<string, unknown>;
}

export interface ChannelWithThreads {
  channel_id: number;
  channel_name: string;
  thread_count: number;
  sample_threads: string[];
}

export interface DetectedRole {
  role_id: number;
  role_name: string;
  role_type: 'stakeholder' | 'team';
}

export interface AnalysisResult {
  success: boolean;
  channels_with_threads: ChannelWithThreads[];
  recommended_channel: ChannelWithThreads | null;
  detected_pattern: string | null;
  detected_roles: DetectedRole[];
  config_applied: boolean;
  message: string;
}

export interface GitHubIdentity {
  id: string;
  user_id: string;
  committer_email: string;
  committer_name: string | null;
  is_verified: boolean;
}

export interface ProjectMember {
  id: string;
  user_id: string;
  discord_username: string | null;
  github_username: string | null;
  role: string;
  responsibilities: Record<string, unknown>;
  assigned_at: string;
  is_active: boolean;
}

export interface ProjectGitHubLink {
  id: string;
  github_connection_id: string;
  repo_full_name: string;
  branch_filter: string | null;
  is_primary: boolean;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  discord_thread_id: number | null;
  discord_thread_name: string | null;
  start_date: string | null;
  target_launch_date: string | null;
  objectives: Record<string, unknown>;
  kpi_config: Record<string, unknown>;
  launch_checklist: Record<string, unknown>;
  members: ProjectMember[];
  github_links: ProjectGitHubLink[];
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  id: string;
  discord_id: number;
  discord_username: string | null;
  github_username: string | null;
  email: string | null;
  github_identities: GitHubIdentity[];
  project_count: number;
  is_active: boolean;
}

export const projectsApi = {
  // Config
  getConfig: (tenantId: string) =>
    api.get<ProjectConfig | null>(`/api/v1/tenants/${tenantId}/projects/config`),

  updateConfig: (tenantId: string, data: Partial<ProjectConfig>) =>
    api.fetch<ProjectConfig>(`/api/v1/tenants/${tenantId}/projects/config`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Analyze and auto-configure
  analyze: (tenantId: string) =>
    api.post<AnalysisResult>(`/api/v1/tenants/${tenantId}/projects/analyze`),

  // Projects
  list: (tenantId: string, status?: string) =>
    api.get<Project[]>(`/api/v1/tenants/${tenantId}/projects`, status ? { status_filter: status } : {}),

  get: (tenantId: string, projectId: string) =>
    api.get<Project>(`/api/v1/tenants/${tenantId}/projects/${projectId}`),

  create: (tenantId: string, data: {
    name: string;
    description?: string;
    discord_thread_id?: number;
    discord_thread_name?: string;
    start_date?: string;
    target_launch_date?: string;
    objectives?: Record<string, unknown>;
  }) =>
    api.post<Project>(`/api/v1/tenants/${tenantId}/projects`, data),

  update: (tenantId: string, projectId: string, data: Partial<Project>) =>
    api.patch<Project>(`/api/v1/tenants/${tenantId}/projects/${projectId}`, data),

  delete: (tenantId: string, projectId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/projects/${projectId}`),

  // Project Members
  addMember: (tenantId: string, projectId: string, data: {
    user_id: string;
    role?: string;
    responsibilities?: Record<string, unknown>;
  }) =>
    api.post<ProjectMember>(`/api/v1/tenants/${tenantId}/projects/${projectId}/members`, data),

  updateMember: (tenantId: string, projectId: string, memberId: string, data: {
    role?: string;
    responsibilities?: Record<string, unknown>;
    is_active?: boolean;
  }) =>
    api.patch<ProjectMember>(`/api/v1/tenants/${tenantId}/projects/${projectId}/members/${memberId}`, data),

  removeMember: (tenantId: string, projectId: string, memberId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/projects/${projectId}/members/${memberId}`),

  // GitHub Links
  linkRepo: (tenantId: string, projectId: string, data: {
    github_connection_id: string;
    branch_filter?: string;
    is_primary?: boolean;
  }) =>
    api.post<ProjectGitHubLink>(`/api/v1/tenants/${tenantId}/projects/${projectId}/github`, data),

  unlinkRepo: (tenantId: string, projectId: string, linkId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/projects/${projectId}/github/${linkId}`),

  // Team Members (across all projects)
  getTeamMembers: (tenantId: string) =>
    api.get<TeamMember[]>(`/api/v1/tenants/${tenantId}/projects/team/members`),

  // GitHub Identity Mapping
  addGitHubIdentity: (tenantId: string, data: {
    user_id: string;
    committer_email: string;
    committer_name?: string;
  }) =>
    api.post<GitHubIdentity>(`/api/v1/tenants/${tenantId}/projects/team/github-identities`, data),

  removeGitHubIdentity: (tenantId: string, identityId: string) =>
    api.delete<{ message: string }>(`/api/v1/tenants/${tenantId}/projects/team/github-identities/${identityId}`),
};

// Team Goals types and API
export interface TeamGoal {
  id: string;
  name: string;
  description: string;
  priority: number;
  category: 'delivery' | 'productivity' | 'quality' | 'wellbeing' | 'cost';
  target_metric?: string;
  target_value?: number;
  is_active: boolean;
}

export interface TeamGoalsConfig {
  goals: TeamGoal[];
  primary_focus?: string;
}

export const goalsApi = {
  get: () =>
    api.get<TeamGoalsConfig>('/api/v1/goals'),

  update: (goals: TeamGoal[], primaryFocus?: string) =>
    api.put<TeamGoalsConfig>('/api/v1/goals', { goals, primary_focus: primaryFocus }),

  getTemplates: () =>
    api.get<Record<string, TeamGoal>>('/api/v1/goals/templates'),

  applyTemplate: (templateId: string) =>
    api.post<TeamGoalsConfig>(`/api/v1/goals/apply-template/${templateId}`),
};
