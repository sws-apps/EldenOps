'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FolderKanban,
  Settings2,
  Users,
  Github,
  Plus,
  Trash2,
  Edit2,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  GitBranch,
  Mail,
  Check,
  X,
  AlertCircle,
  Loader2,
  Sparkles,
  Hash,
  Shield,
  UserCheck,
} from 'lucide-react';
import {
  projectsApi,
  githubApi,
  type Project,
  type ProjectConfig,
  type TeamMember,
  type GitHubConnection,
  type AnalysisResult,
} from '@/lib/api';
import { cn } from '@/lib/utils';

type TabType = 'projects' | 'team' | 'config';

export default function ProjectsPage() {
  const [activeTab, setActiveTab] = useState<TabType>('projects');

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Projects & Team Configuration</h1>
        <p className="text-muted-foreground mt-1">
          Manage projects, team members, and GitHub identity mappings
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <nav className="flex gap-4">
          <TabButton
            active={activeTab === 'projects'}
            onClick={() => setActiveTab('projects')}
            icon={FolderKanban}
            label="Projects"
          />
          <TabButton
            active={activeTab === 'team'}
            onClick={() => setActiveTab('team')}
            icon={Users}
            label="Team Mapping"
          />
          <TabButton
            active={activeTab === 'config'}
            onClick={() => setActiveTab('config')}
            icon={Settings2}
            label="Configuration"
          />
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'projects' && <ProjectsTab />}
      {activeTab === 'team' && <TeamMappingTab />}
      {activeTab === 'config' && <ConfigTab />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
        active
          ? 'border-primary text-foreground'
          : 'border-transparent text-muted-foreground hover:text-foreground'
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

// ============ Projects Tab ============

function ProjectsTab() {
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [showCreateForm, setShowCreateForm] = useState(false);
  const queryClient = useQueryClient();

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list('current'),
  });

  const { data: githubConnections } = useQuery({
    queryKey: ['github', 'connections'],
    queryFn: () => githubApi.getConnections(),
  });

  const toggleExpand = (projectId: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  };

  const statusColors: Record<string, string> = {
    planning: 'bg-blue-500/10 text-blue-500',
    active: 'bg-green-500/10 text-green-500',
    on_hold: 'bg-yellow-500/10 text-yellow-500',
    blocked: 'bg-red-500/10 text-red-500',
    completed: 'bg-purple-500/10 text-purple-500',
    archived: 'bg-muted text-muted-foreground',
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Add project button */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <CreateProjectForm
          onClose={() => setShowCreateForm(false)}
          onSuccess={() => {
            setShowCreateForm(false);
            queryClient.invalidateQueries({ queryKey: ['projects'] });
          }}
        />
      )}

      {/* Projects list */}
      {projects && projects.length > 0 ? (
        <div className="space-y-3">
          {projects.map((project) => (
            <div key={project.id} className="rounded-lg border bg-card">
              {/* Project header */}
              <div
                className="flex items-center gap-4 p-4 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => toggleExpand(project.id)}
              >
                <button className="text-muted-foreground">
                  {expandedProjects.has(project.id) ? (
                    <ChevronDown className="h-5 w-5" />
                  ) : (
                    <ChevronRight className="h-5 w-5" />
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold truncate">{project.name}</h3>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded-full text-xs font-medium capitalize',
                        statusColors[project.status] || 'bg-muted text-muted-foreground'
                      )}
                    >
                      {project.status.replace('_', ' ')}
                    </span>
                  </div>
                  {project.description && (
                    <p className="text-sm text-muted-foreground mt-1 truncate">
                      {project.description}
                    </p>
                  )}
                </div>

                {/* Quick stats */}
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Users className="h-4 w-4" />
                    <span>{project.members.length}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Github className="h-4 w-4" />
                    <span>{project.github_links.length}</span>
                  </div>
                  {project.discord_thread_id && (
                    <div className="flex items-center gap-1.5">
                      <MessageSquare className="h-4 w-4 text-[#5865F2]" />
                    </div>
                  )}
                </div>
              </div>

              {/* Expanded content */}
              {expandedProjects.has(project.id) && (
                <ProjectDetails
                  project={project}
                  githubConnections={githubConnections || []}
                />
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <FolderKanban className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No projects yet</p>
          <p className="text-sm mt-1">Create your first project to get started</p>
        </div>
      )}
    </div>
  );
}

function CreateProjectForm({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [discordThreadId, setDiscordThreadId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof projectsApi.create>[1]) =>
      projectsApi.create('current', data),
    onSuccess,
    onError: (err: Error) => setError(err.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Project name is required');
      return;
    }

    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      discord_thread_id: discordThreadId ? parseInt(discordThreadId) : undefined,
    });
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="font-semibold mb-4">Create New Project</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Project Name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., CUA-BOT"
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description of the project..."
            rows={2}
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Discord Thread ID</label>
          <input
            type="text"
            value={discordThreadId}
            onChange={(e) => setDiscordThreadId(e.target.value)}
            placeholder="Right-click thread > Copy ID"
            className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Link this project to a Discord task-delegation thread
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-500">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
          >
            {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Create Project
          </button>
        </div>
      </form>
    </div>
  );
}

function ProjectDetails({
  project,
  githubConnections,
}: {
  project: Project;
  githubConnections: GitHubConnection[];
}) {
  const queryClient = useQueryClient();
  const [showLinkRepo, setShowLinkRepo] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState('');

  const linkRepoMutation = useMutation({
    mutationFn: (connectionId: string) =>
      projectsApi.linkRepo('current', project.id, { github_connection_id: connectionId }),
    onSuccess: () => {
      setShowLinkRepo(false);
      setSelectedRepo('');
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const unlinkRepoMutation = useMutation({
    mutationFn: (linkId: string) =>
      projectsApi.unlinkRepo('current', project.id, linkId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });

  const deleteProjectMutation = useMutation({
    mutationFn: () => projectsApi.delete('current', project.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });

  const availableRepos = githubConnections.filter(
    (conn) => !project.github_links.some((link) => link.github_connection_id === conn.id)
  );

  return (
    <div className="border-t p-4 bg-muted/20 space-y-6">
      {/* Discord thread info */}
      {project.discord_thread_id && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-[#5865F2]" />
            Linked Discord Thread
          </h4>
          <div className="text-sm text-muted-foreground">
            {project.discord_thread_name || `Thread ID: ${project.discord_thread_id}`}
          </div>
        </div>
      )}

      {/* Team members */}
      <div>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
          <Users className="h-4 w-4" />
          Team Members ({project.members.length})
        </h4>
        {project.members.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {project.members.map((member) => (
              <div
                key={member.id}
                className="flex items-center gap-2 px-3 py-1.5 bg-background rounded-full border text-sm"
              >
                <div className="h-6 w-6 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-medium">
                  {member.discord_username?.[0]?.toUpperCase() || '?'}
                </div>
                <span>{member.discord_username || 'Unknown'}</span>
                <span className="text-xs text-muted-foreground capitalize">
                  ({member.role})
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No team members assigned</p>
        )}
      </div>

      {/* GitHub repos */}
      <div>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
          <Github className="h-4 w-4" />
          Linked Repositories ({project.github_links.length})
        </h4>

        {project.github_links.length > 0 && (
          <div className="space-y-2 mb-3">
            {project.github_links.map((link) => (
              <div
                key={link.id}
                className="flex items-center justify-between px-3 py-2 bg-background rounded-lg border"
              >
                <div className="flex items-center gap-2">
                  <Github className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{link.repo_full_name}</span>
                  {link.is_primary && (
                    <span className="px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded">
                      Primary
                    </span>
                  )}
                  {link.branch_filter && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <GitBranch className="h-3 w-3" />
                      {link.branch_filter}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => unlinkRepoMutation.mutate(link.id)}
                  disabled={unlinkRepoMutation.isPending}
                  className="text-muted-foreground hover:text-red-500 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {showLinkRepo ? (
          <div className="flex items-center gap-2">
            <select
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Select a repository...</option>
              {availableRepos.map((conn) => (
                <option key={conn.id} value={conn.id}>
                  {conn.repo_full_name}
                </option>
              ))}
            </select>
            <button
              onClick={() => selectedRepo && linkRepoMutation.mutate(selectedRepo)}
              disabled={!selectedRepo || linkRepoMutation.isPending}
              className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              <Check className="h-4 w-4" />
            </button>
            <button
              onClick={() => {
                setShowLinkRepo(false);
                setSelectedRepo('');
              }}
              className="p-2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowLinkRepo(true)}
            disabled={availableRepos.length === 0}
            className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 disabled:text-muted-foreground disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            Link Repository
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end border-t pt-4">
        <button
          onClick={() => {
            if (confirm('Are you sure you want to delete this project?')) {
              deleteProjectMutation.mutate();
            }
          }}
          disabled={deleteProjectMutation.isPending}
          className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
          Delete Project
        </button>
      </div>
    </div>
  );
}

// ============ Team Mapping Tab ============

function TeamMappingTab() {
  const queryClient = useQueryClient();
  const [showAddIdentity, setShowAddIdentity] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');

  const { data: teamMembers, isLoading } = useQuery({
    queryKey: ['projects', 'team', 'members'],
    queryFn: () => projectsApi.getTeamMembers('current'),
  });

  const addIdentityMutation = useMutation({
    mutationFn: (data: { user_id: string; committer_email: string; committer_name?: string }) =>
      projectsApi.addGitHubIdentity('current', data),
    onSuccess: () => {
      setShowAddIdentity(null);
      setNewEmail('');
      setNewName('');
      queryClient.invalidateQueries({ queryKey: ['projects', 'team', 'members'] });
    },
  });

  const removeIdentityMutation = useMutation({
    mutationFn: (identityId: string) =>
      projectsApi.removeGitHubIdentity('current', identityId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', 'team', 'members'] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium">GitHub Identity Mapping</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Git commits can have different email addresses than GitHub accounts. Map committer
              emails to team members so we can properly attribute their contributions across projects.
            </p>
          </div>
        </div>
      </div>

      {teamMembers && teamMembers.length > 0 ? (
        <div className="space-y-3">
          {teamMembers.map((member) => (
            <div key={member.id} className="rounded-lg border bg-card p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-lg font-medium">
                    {member.discord_username?.[0]?.toUpperCase() || '?'}
                  </div>
                  <div>
                    <div className="font-semibold">
                      {member.discord_username || 'Unknown User'}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground mt-0.5">
                      {member.github_username && (
                        <span className="flex items-center gap-1">
                          <Github className="h-3.5 w-3.5" />
                          {member.github_username}
                        </span>
                      )}
                      {member.email && (
                        <span className="flex items-center gap-1">
                          <Mail className="h-3.5 w-3.5" />
                          {member.email}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="text-sm text-muted-foreground">
                  {member.project_count} project{member.project_count !== 1 ? 's' : ''}
                </div>
              </div>

              {/* GitHub identities */}
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">Mapped Committer Emails</h4>

                {member.github_identities.length > 0 ? (
                  <div className="space-y-2">
                    {member.github_identities.map((identity) => (
                      <div
                        key={identity.id}
                        className="flex items-center justify-between px-3 py-2 bg-muted/50 rounded-lg"
                      >
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm">{identity.committer_email}</span>
                          {identity.committer_name && (
                            <span className="text-xs text-muted-foreground">
                              ({identity.committer_name})
                            </span>
                          )}
                          {identity.is_verified && (
                            <Check className="h-3.5 w-3.5 text-green-500" />
                          )}
                        </div>
                        <button
                          onClick={() => removeIdentityMutation.mutate(identity.id)}
                          className="text-muted-foreground hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No email mappings configured</p>
                )}

                {/* Add identity form */}
                {showAddIdentity === member.id ? (
                  <div className="flex items-center gap-2 mt-3">
                    <input
                      type="email"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      placeholder="committer@email.com"
                      className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="Name (optional)"
                      className="w-40 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <button
                      onClick={() => {
                        if (newEmail) {
                          addIdentityMutation.mutate({
                            user_id: member.id,
                            committer_email: newEmail,
                            committer_name: newName || undefined,
                          });
                        }
                      }}
                      disabled={!newEmail || addIdentityMutation.isPending}
                      className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => {
                        setShowAddIdentity(null);
                        setNewEmail('');
                        setNewName('');
                      }}
                      className="p-2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowAddIdentity(member.id)}
                    className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 mt-3"
                  >
                    <Plus className="h-4 w-4" />
                    Add Email Mapping
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No team members found</p>
          <p className="text-sm mt-1">Team members will appear here once they join via Discord</p>
        </div>
      )}
    </div>
  );
}

// ============ Config Tab ============

function ConfigTab() {
  const queryClient = useQueryClient();
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);

  const { data: config, isLoading } = useQuery({
    queryKey: ['projects', 'config'],
    queryFn: () => projectsApi.getConfig('current'),
  });

  const [taskChannelId, setTaskChannelId] = useState('');
  const [taskChannelName, setTaskChannelName] = useState('');
  const [threadPattern, setThreadPattern] = useState('{member} ({project})');
  const [autoCreate, setAutoCreate] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);

  // Update local state when config loads
  useState(() => {
    if (config) {
      setTaskChannelId(config.task_channel_id?.toString() || '');
      setTaskChannelName(config.task_channel_name || '');
      setThreadPattern(config.thread_name_pattern || '{member} ({project})');
      setAutoCreate(config.auto_create_projects ?? true);
    }
  });

  const analyzeMutation = useMutation({
    mutationFn: () => projectsApi.analyze('current'),
    onSuccess: (result) => {
      setAnalysisResult(result);
      if (result.config_applied) {
        queryClient.invalidateQueries({ queryKey: ['projects', 'config'] });
        queryClient.invalidateQueries({ queryKey: ['projects'] });
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<ProjectConfig>) =>
      projectsApi.updateConfig('current', data),
    onSuccess: () => {
      setHasChanges(false);
      queryClient.invalidateQueries({ queryKey: ['projects', 'config'] });
    },
  });

  const handleSave = () => {
    updateMutation.mutate({
      task_channel_id: taskChannelId ? parseInt(taskChannelId) : null,
      task_channel_name: taskChannelName || null,
      thread_name_pattern: threadPattern,
      auto_create_projects: autoCreate,
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const patternExamples: Record<string, string> = {
    '{member} ({project})': 'Jeo (CUA-BOT)',
    '{project} - {member}': 'CUA-BOT - Jeo',
    '{project}': 'CUA-BOT',
    '{member}': 'Jeo',
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Smart Auto-Configure */}
      <div className="rounded-lg border-2 border-dashed border-primary/50 bg-primary/5 p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-full bg-primary/10">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-lg">Smart Auto-Configure</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Let AI analyze your Discord server and automatically configure project tracking,
              detect your thread naming pattern, and set up role-based reports.
            </p>
            <button
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending}
              className="mt-4 flex items-center gap-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 font-medium"
            >
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Analyzing Discord Server...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Analyze & Auto-Configure
                </>
              )}
            </button>
          </div>
        </div>

        {/* Analysis Results */}
        {analysisResult && (
          <div className="mt-6 pt-6 border-t border-primary/20">
            <div className={cn(
              "flex items-center gap-2 font-medium mb-4",
              analysisResult.success ? "text-green-600" : "text-yellow-600"
            )}>
              {analysisResult.success ? (
                <Check className="h-5 w-5" />
              ) : (
                <AlertCircle className="h-5 w-5" />
              )}
              {analysisResult.message}
            </div>

            {/* Channels Found */}
            {analysisResult.channels_with_threads.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Hash className="h-4 w-4" />
                  Channels with Threads
                </h4>
                <div className="space-y-2">
                  {analysisResult.channels_with_threads.slice(0, 5).map((ch) => (
                    <div
                      key={ch.channel_id}
                      className={cn(
                        "flex items-center justify-between px-3 py-2 rounded-lg text-sm",
                        analysisResult.recommended_channel?.channel_id === ch.channel_id
                          ? "bg-green-500/10 border border-green-500/30"
                          : "bg-muted/50"
                      )}
                    >
                      <span className="font-medium">#{ch.channel_name}</span>
                      <span className="text-muted-foreground">{ch.thread_count} threads</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Detected Pattern */}
            {analysisResult.detected_pattern && (
              <div className="mb-4">
                <h4 className="text-sm font-medium mb-2">Detected Pattern</h4>
                <code className="px-2 py-1 bg-muted rounded text-sm">
                  {analysisResult.detected_pattern}
                </code>
              </div>
            )}

            {/* Detected Roles */}
            {analysisResult.detected_roles.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Role-Based Reports Configured
                </h4>
                <div className="flex flex-wrap gap-2">
                  {analysisResult.detected_roles.slice(0, 10).map((role) => (
                    <span
                      key={role.role_id}
                      className={cn(
                        "px-2 py-1 rounded-full text-xs font-medium",
                        role.role_type === 'stakeholder'
                          ? "bg-purple-500/10 text-purple-600"
                          : "bg-blue-500/10 text-blue-600"
                      )}
                    >
                      {role.role_type === 'stakeholder' ? (
                        <Shield className="h-3 w-3 inline mr-1" />
                      ) : (
                        <UserCheck className="h-3 w-3 inline mr-1" />
                      )}
                      {role.role_name}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Stakeholders get high-level summaries. Team members get detailed metrics.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-background px-3 text-sm text-muted-foreground">
            Or configure manually
          </span>
        </div>
      </div>

      {/* Task Delegation Channel */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-[#5865F2]" />
          Task Delegation Channel
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Configure which Discord channel contains your task delegation threads. Each thread
          represents a project assignment.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Channel ID</label>
            <input
              type="text"
              value={taskChannelId}
              onChange={(e) => {
                setTaskChannelId(e.target.value);
                setHasChanges(true);
              }}
              placeholder="Right-click channel > Copy ID"
              className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Channel Name (optional)</label>
            <input
              type="text"
              value={taskChannelName}
              onChange={(e) => {
                setTaskChannelName(e.target.value);
                setHasChanges(true);
              }}
              placeholder="e.g., task-delegation"
              className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>
      </div>

      {/* Thread Naming Pattern */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="font-semibold mb-4">Thread Naming Pattern</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Define how your organization names task delegation threads. We&apos;ll parse thread names
          to extract project and member information.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Pattern</label>
            <select
              value={threadPattern}
              onChange={(e) => {
                setThreadPattern(e.target.value);
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="{member} ({project})">{'{member} ({project})'} - e.g., &quot;Jeo (CUA-BOT)&quot;</option>
              <option value="{project} - {member}">{'{project} - {member}'} - e.g., &quot;CUA-BOT - Jeo&quot;</option>
              <option value="{project}">{'{project}'} - e.g., &quot;CUA-BOT&quot;</option>
              <option value="{member}">{'{member}'} - e.g., &quot;Jeo&quot;</option>
            </select>
          </div>

          <div className="p-3 bg-muted/50 rounded-lg">
            <div className="text-sm font-medium">Pattern Variables:</div>
            <ul className="text-sm text-muted-foreground mt-1 space-y-1">
              <li><code className="px-1 bg-muted rounded">{'{member}'}</code> - Team member name</li>
              <li><code className="px-1 bg-muted rounded">{'{project}'}</code> - Project name</li>
            </ul>
            <div className="text-sm mt-2">
              <span className="font-medium">Example thread name:</span>{' '}
              <code className="px-1 bg-muted rounded">{patternExamples[threadPattern]}</code>
            </div>
          </div>
        </div>
      </div>

      {/* Auto-create Projects */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold">Auto-create Projects</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Automatically create projects when new threads are detected in the task delegation
              channel.
            </p>
          </div>
          <button
            onClick={() => {
              setAutoCreate(!autoCreate);
              setHasChanges(true);
            }}
            className={cn(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
              autoCreate ? 'bg-primary' : 'bg-muted'
            )}
          >
            <span
              className={cn(
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                autoCreate ? 'translate-x-6' : 'translate-x-1'
              )}
            />
          </button>
        </div>
      </div>

      {/* Save button */}
      {hasChanges && (
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="flex items-center gap-2 px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
          >
            {updateMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Save Configuration
          </button>
        </div>
      )}
    </div>
  );
}
