'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  User,
  Bell,
  Shield,
  Github,
  MessageSquare,
  Sparkles,
  Save,
  Loader2,
  Check,
  ExternalLink,
  Key,
  Hash,
  Plus,
  Trash2,
  Target,
  Rocket,
  Clock,
  Heart,
  DollarSign,
  Code,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { tenantsApi, aiProvidersApi, githubTokenApi, channelsApi, goalsApi, type AIProviderConfig, type GitHubTokenStatus, type MonitoredChannel, type TeamGoal, type TeamGoalsConfig } from '@/lib/api';
import { useRoleAccess } from '@/hooks/useRoleAccess';
import { cn } from '@/lib/utils';

type Tab = 'profile' | 'integrations' | 'ai' | 'goals' | 'notifications';

const AI_PROVIDERS = [
  { id: 'claude', name: 'Claude (Anthropic)', description: 'Best for nuanced analysis' },
  { id: 'openai', name: 'OpenAI (GPT-4)', description: 'Fast and reliable' },
  { id: 'gemini', name: 'Google Gemini', description: 'Good for large contexts' },
  { id: 'deepseek', name: 'DeepSeek', description: 'Cost-effective option' },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('profile');

  const { isAdmin } = useRoleAccess();

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }>; adminOnly?: boolean }[] = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'integrations', label: 'Integrations', icon: Github },
    { id: 'ai', label: 'AI Settings', icon: Sparkles },
    { id: 'goals', label: 'Team Goals', icon: Target, adminOnly: true },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ];

  const visibleTabs = tabs.filter(tab => !tab.adminOnly || isAdmin);

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your account and preferences
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Tabs */}
        <div className="lg:w-64 flex-shrink-0">
          <nav className="space-y-1">
            {visibleTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && <ProfileSettings />}
          {activeTab === 'integrations' && <IntegrationsSettings />}
          {activeTab === 'ai' && <AISettings />}
          {activeTab === 'goals' && isAdmin && <GoalsSettings />}
          {activeTab === 'notifications' && <NotificationSettings />}
        </div>
      </div>
    </div>
  );
}

function ProfileSettings() {
  const { user } = useAuth();

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-6 border-b">
        <h2 className="text-lg font-semibold">Profile Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Your account information from Discord
        </p>
      </div>
      <div className="p-6 space-y-6">
        {/* Avatar and username */}
        <div className="flex items-center gap-4">
          <div className="h-20 w-20 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-2xl font-bold">
            {user?.discord_username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <h3 className="text-lg font-semibold">{user?.discord_username || 'User'}</h3>
            <p className="text-sm text-muted-foreground">
              Discord ID: {user?.discord_id || 'Not available'}
            </p>
          </div>
        </div>

        {/* Info fields */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium">Discord Username</label>
            <input
              type="text"
              value={user?.discord_username || ''}
              disabled
              className="w-full px-3 py-2 rounded-lg border bg-muted text-muted-foreground"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Email</label>
            <input
              type="email"
              value={user?.email || 'Not provided'}
              disabled
              className="w-full px-3 py-2 rounded-lg border bg-muted text-muted-foreground"
            />
          </div>
        </div>

        <div className="p-4 rounded-lg bg-muted/50 border">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div>
              <p className="text-sm font-medium">Account managed by Discord</p>
              <p className="text-xs text-muted-foreground mt-1">
                Your profile information is synced from your Discord account.
                To update your username or avatar, please update your Discord profile.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function IntegrationsSettings() {
  const { currentTenantId } = useAuth();
  const queryClient = useQueryClient();
  const [githubToken, setGithubToken] = useState('');
  const [githubError, setGithubError] = useState<string | null>(null);
  const [githubSaved, setGithubSaved] = useState(false);

  // Channel management state
  const [newChannelId, setNewChannelId] = useState('');
  const [newChannelName, setNewChannelName] = useState('');
  const [channelError, setChannelError] = useState<string | null>(null);

  const { data: tenant, isLoading } = useQuery({
    queryKey: ['tenant', 'current'],
    queryFn: () => tenantsApi.get('current'),
  });

  // Fetch monitored channels
  const { data: channels, isLoading: isLoadingChannels } = useQuery<MonitoredChannel[]>({
    queryKey: ['channels', currentTenantId],
    queryFn: () => currentTenantId ? channelsApi.list(currentTenantId) : Promise.resolve([]),
    enabled: !!currentTenantId,
  });

  // Add channel mutation
  const addChannelMutation = useMutation({
    mutationFn: async () => {
      if (!currentTenantId) throw new Error('No tenant selected');
      const channelId = parseInt(newChannelId, 10);
      if (isNaN(channelId)) throw new Error('Invalid channel ID');
      return channelsApi.add(currentTenantId, channelId, newChannelName || `channel-${channelId}`, 'text');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] });
      setNewChannelId('');
      setNewChannelName('');
      setChannelError(null);
    },
    onError: (err: Error) => {
      setChannelError(err.message);
    },
  });

  // Remove channel mutation
  const removeChannelMutation = useMutation({
    mutationFn: async (channelId: string) => {
      if (!currentTenantId) throw new Error('No tenant selected');
      return channelsApi.remove(currentTenantId, channelId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['channels'] });
    },
  });

  // Fetch GitHub token status
  const { data: githubTokenStatus, isLoading: isLoadingGithubToken } = useQuery<GitHubTokenStatus>({
    queryKey: ['github-token', currentTenantId],
    queryFn: () => currentTenantId ? githubTokenApi.getStatus(currentTenantId) : Promise.resolve({ is_configured: false } as GitHubTokenStatus),
    enabled: !!currentTenantId,
  });

  // Save GitHub token mutation
  const saveGithubTokenMutation = useMutation({
    mutationFn: async () => {
      if (!currentTenantId) throw new Error('No tenant selected');
      return githubTokenApi.setToken(currentTenantId, githubToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-token'] });
      setGithubToken('');
      setGithubError(null);
      setGithubSaved(true);
      setTimeout(() => setGithubSaved(false), 2000);
    },
    onError: (err: Error) => {
      setGithubError(err.message);
    },
  });

  // Remove GitHub token mutation
  const removeGithubTokenMutation = useMutation({
    mutationFn: async () => {
      if (!currentTenantId) throw new Error('No tenant selected');
      return githubTokenApi.removeToken(currentTenantId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-token'] });
    },
  });

  const handleSaveGithubToken = () => {
    if (!githubToken.trim()) return;
    saveGithubTokenMutation.mutate();
  };

  return (
    <div className="space-y-6">
      {/* Discord */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[#5865F2]/10">
              <MessageSquare className="h-5 w-5 text-[#5865F2]" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Discord</h2>
              <p className="text-sm text-muted-foreground">
                Manage your Discord server connection
              </p>
            </div>
          </div>
        </div>
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : tenant ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                <div className="flex items-center gap-3">
                  <Check className="h-5 w-5 text-green-500" />
                  <div>
                    <p className="font-medium">Connected</p>
                    <p className="text-sm text-muted-foreground">
                      {tenant.guild_name || 'Unknown Server'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Monitored Channels */}
              <div className="pt-4 border-t">
                <h3 className="text-sm font-semibold mb-3">Monitored Channels</h3>

                {isLoadingChannels ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : channels && channels.length > 0 ? (
                  <div className="space-y-2 mb-4">
                    {channels.map((channel) => (
                      <div
                        key={channel.id}
                        className="flex items-center justify-between p-3 rounded-lg border bg-muted/30"
                      >
                        <div className="flex items-center gap-2">
                          <Hash className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{channel.channel_name || `ID: ${channel.channel_id}`}</span>
                          <span className="text-xs bg-muted px-1.5 py-0.5 rounded">{channel.channel_type}</span>
                        </div>
                        <button
                          onClick={() => removeChannelMutation.mutate(channel.id)}
                          disabled={removeChannelMutation.isPending}
                          className="text-red-500 hover:text-red-600 p-1"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground mb-4">No channels monitored yet.</p>
                )}

                {/* Add channel form */}
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Channel ID"
                      value={newChannelId}
                      onChange={(e) => {
                        setNewChannelId(e.target.value);
                        setChannelError(null);
                      }}
                      className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <input
                      type="text"
                      placeholder="Channel name (optional)"
                      value={newChannelName}
                      onChange={(e) => setNewChannelName(e.target.value)}
                      className="flex-1 px-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <button
                      onClick={() => addChannelMutation.mutate()}
                      disabled={addChannelMutation.isPending || !newChannelId.trim()}
                      className="inline-flex items-center gap-1 px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                      {addChannelMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      Add
                    </button>
                  </div>
                  {channelError && (
                    <p className="text-xs text-red-500">{channelError}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    To find a channel ID: Enable Developer Mode in Discord Settings → App Settings → Advanced, then right-click a channel and select "Copy Channel ID".
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-muted-foreground">No Discord server connected</p>
              <a
                href={`https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID}&permissions=274877975552&scope=bot%20applications.commands`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-[#5865F2] text-white rounded-lg hover:bg-[#5865F2]/90 transition-colors"
              >
                Add Bot to Server
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          )}
        </div>
      </div>

      {/* GitHub */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-foreground/10">
              <Github className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">GitHub</h2>
              <p className="text-sm text-muted-foreground">
                Connect GitHub repositories for commit tracking
              </p>
            </div>
          </div>
        </div>
        <div className="p-6 space-y-4">
          {/* Current status */}
          {isLoadingGithubToken ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : githubTokenStatus?.is_configured ? (
            <div className="space-y-4">
              <div className={cn(
                'flex items-center justify-between p-4 rounded-lg border',
                githubTokenStatus.is_valid
                  ? 'bg-green-500/10 border-green-500/20'
                  : 'bg-yellow-500/10 border-yellow-500/20'
              )}>
                <div className="flex items-center gap-3">
                  {githubTokenStatus.is_valid ? (
                    <Check className="h-5 w-5 text-green-500" />
                  ) : (
                    <Shield className="h-5 w-5 text-yellow-500" />
                  )}
                  <div>
                    <p className="font-medium">
                      {githubTokenStatus.is_valid ? 'Token configured' : 'Token invalid'}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Token: {githubTokenStatus.token_preview}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeGithubTokenMutation.mutate()}
                  disabled={removeGithubTokenMutation.isPending}
                  className="text-sm text-red-500 hover:text-red-600"
                >
                  {removeGithubTokenMutation.isPending ? 'Removing...' : 'Remove'}
                </button>
              </div>
              {!githubTokenStatus.is_valid && (
                <p className="text-sm text-yellow-600">
                  Your GitHub token appears to be invalid. Please update it below.
                </p>
              )}
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-muted/50 border">
              <p className="text-sm text-muted-foreground">
                No GitHub token configured. Add a Personal Access Token to connect repositories.
              </p>
            </div>
          )}

          {/* Token input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {githubTokenStatus?.is_configured ? 'Update GitHub Token' : 'GitHub Personal Access Token'}
            </label>
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="password"
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                value={githubToken}
                onChange={(e) => {
                  setGithubToken(e.target.value);
                  setGithubError(null);
                }}
                className="w-full pl-9 pr-4 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Create a token at{' '}
              <a
                href="https://github.com/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                GitHub Settings → Developer settings → Personal access tokens
              </a>
              . Required scopes: <code>repo</code> (for private repos) or <code>public_repo</code> (for public only).
            </p>
            {githubError && (
              <p className="text-xs text-red-500">{githubError}</p>
            )}
          </div>

          {/* Save button */}
          <div className="flex justify-end">
            <button
              onClick={handleSaveGithubToken}
              disabled={saveGithubTokenMutation.isPending || !githubToken.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {saveGithubTokenMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Validating...
                </>
              ) : githubSaved ? (
                <>
                  <Check className="h-4 w-4" />
                  Saved!
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  {githubTokenStatus?.is_configured ? 'Update Token' : 'Save Token'}
                </>
              )}
            </button>
          </div>

          {/* Instructions */}
          {githubTokenStatus?.is_configured && githubTokenStatus.is_valid && (
            <div className="pt-4 border-t">
              <p className="text-sm text-muted-foreground">
                You can now connect repositories from the{' '}
                <a href="/dashboard/github" className="text-primary hover:underline">
                  GitHub page
                </a>
                .
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AISettings() {
  const { currentTenantId } = useAuth();
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [saved, setSaved] = useState(false);
  const [savedProvider, setSavedProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch existing AI provider configs
  const { data: configs, isLoading } = useQuery({
    queryKey: ['ai-providers', currentTenantId],
    queryFn: () => currentTenantId ? aiProvidersApi.list(currentTenantId) : Promise.resolve([]),
    enabled: !!currentTenantId,
  });

  // Find the existing config for the selected provider
  const existingConfig = configs?.find(c => c.provider === selectedProvider);

  // Add/Update mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!currentTenantId) throw new Error('No tenant selected');

      if (existingConfig) {
        // Update existing config
        return aiProvidersApi.update(currentTenantId, existingConfig.id, {
          api_key: apiKey,
          is_default: true,
        });
      } else {
        // Add new config
        return aiProvidersApi.add(currentTenantId, selectedProvider, apiKey, true);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers', currentTenantId] });
      setApiKey('');
      setSaved(true);
      setSavedProvider(AI_PROVIDERS.find(p => p.id === selectedProvider)?.name || selectedProvider);
      setError(null);
      // Keep the success message visible for longer (5 seconds)
      setTimeout(() => {
        setSaved(false);
        setSavedProvider(null);
      }, 5000);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const handleSave = () => {
    if (!apiKey.trim()) return;
    saveMutation.mutate();
  };

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-6 border-b">
        <h2 className="text-lg font-semibold">AI Provider Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure which AI provider to use for attendance detection and report generation
        </p>
      </div>
      <div className="p-6 space-y-6">
        {/* Success banner */}
        {saved && savedProvider && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-green-500/10 border border-green-500/30 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="flex-shrink-0 p-1.5 rounded-full bg-green-500/20">
              <Check className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <p className="font-medium text-green-700 dark:text-green-400">
                API Key Saved Successfully
              </p>
              <p className="text-sm text-green-600 dark:text-green-500">
                Your {savedProvider} API key has been securely stored and is now active.
              </p>
            </div>
          </div>
        )}

        {/* No tenant warning */}
        {!currentTenantId && (
          <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
            <p className="text-sm text-yellow-700 dark:text-yellow-400">
              No Discord server connected. Please connect a server first to configure AI providers.
            </p>
          </div>
        )}

        {/* Loading state */}
        {isLoading && currentTenantId && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Loading configured providers...</span>
          </div>
        )}

        {/* Configured providers */}
        {!isLoading && configs && configs.length > 0 && (
          <div className="space-y-2">
            <label className="text-sm font-medium">Configured Providers</label>
            <div className="space-y-2">
              {configs.map((config) => (
                <div
                  key={config.id}
                  className={cn(
                    'flex items-center justify-between p-3 rounded-lg border',
                    config.is_default ? 'border-green-500/50 bg-green-500/5' : ''
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Check className={cn('h-4 w-4', config.is_default ? 'text-green-500' : 'text-muted-foreground')} />
                    <span className="font-medium">
                      {AI_PROVIDERS.find(p => p.id === config.provider)?.name || config.provider}
                    </span>
                    {config.is_default && (
                      <span className="text-xs bg-green-500/10 text-green-600 px-2 py-0.5 rounded">Default</span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">API key configured</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Provider selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium">
            {configs && configs.length > 0 ? 'Add or Update Provider' : 'Select AI Provider'}
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            {AI_PROVIDERS.map((provider) => {
              const isConfigured = configs?.some(c => c.provider === provider.id);
              return (
                <button
                  key={provider.id}
                  onClick={() => setSelectedProvider(provider.id)}
                  className={cn(
                    'p-4 rounded-lg border text-left transition-colors relative',
                    selectedProvider === provider.id
                      ? 'border-primary bg-primary/5'
                      : 'hover:bg-accent'
                  )}
                >
                  <div className="font-medium">{provider.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {provider.description}
                  </div>
                  {isConfigured && (
                    <span className="absolute top-2 right-2 text-xs bg-muted px-1.5 py-0.5 rounded">
                      Configured
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* API Key */}
        <div className="space-y-2">
          <label className="text-sm font-medium">
            {existingConfig ? 'Update API Key' : 'API Key'}
          </label>
          <div className="relative">
            <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="password"
              placeholder={existingConfig
                ? `Enter new API key to update ${AI_PROVIDERS.find((p) => p.id === selectedProvider)?.name}`
                : `Enter your ${AI_PROVIDERS.find((p) => p.id === selectedProvider)?.name} API key`
              }
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                setError(null);
              }}
              className="w-full pl-9 pr-4 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Your API key is encrypted and stored securely. It will only be used for AI features.
          </p>
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
              <Shield className="h-4 w-4 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}
        </div>

        {/* Save button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending || !apiKey.trim() || !currentTenantId}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving API Key...
              </>
            ) : saved ? (
              <>
                <Check className="h-4 w-4" />
                Saved Successfully!
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                {existingConfig ? 'Update API Key' : 'Save API Key'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function NotificationSettings() {
  const [notifications, setNotifications] = useState({
    dailyDigest: true,
    weeklyReport: true,
    blockerAlerts: false,
    teamUpdates: true,
  });

  const toggleNotification = (key: keyof typeof notifications) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-6 border-b">
        <h2 className="text-lg font-semibold">Notification Preferences</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Control what notifications you receive
        </p>
      </div>
      <div className="divide-y">
        <NotificationToggle
          title="Daily Digest"
          description="Receive a summary of daily activity"
          enabled={notifications.dailyDigest}
          onToggle={() => toggleNotification('dailyDigest')}
        />
        <NotificationToggle
          title="Weekly Reports"
          description="Get weekly team performance reports"
          enabled={notifications.weeklyReport}
          onToggle={() => toggleNotification('weeklyReport')}
        />
        <NotificationToggle
          title="Blocker Alerts"
          description="Get notified when blockers are detected"
          enabled={notifications.blockerAlerts}
          onToggle={() => toggleNotification('blockerAlerts')}
        />
        <NotificationToggle
          title="Team Updates"
          description="Notifications about team member activity"
          enabled={notifications.teamUpdates}
          onToggle={() => toggleNotification('teamUpdates')}
        />
      </div>
    </div>
  );
}

function NotificationToggle({
  title,
  description,
  enabled,
  onToggle,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between p-6">
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
      </div>
      <button
        onClick={onToggle}
        className={cn(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          enabled ? 'bg-primary' : 'bg-muted'
        )}
      >
        <span
          className={cn(
            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
            enabled ? 'translate-x-6' : 'translate-x-1'
          )}
        />
      </button>
    </div>
  );
}

const GOAL_CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  delivery: Rocket,
  productivity: Clock,
  quality: Code,
  wellbeing: Heart,
  cost: DollarSign,
};

const GOAL_CATEGORY_COLORS: Record<string, string> = {
  delivery: 'text-blue-500 bg-blue-500/10',
  productivity: 'text-green-500 bg-green-500/10',
  quality: 'text-purple-500 bg-purple-500/10',
  wellbeing: 'text-pink-500 bg-pink-500/10',
  cost: 'text-yellow-500 bg-yellow-500/10',
};

function GoalsSettings() {
  const queryClient = useQueryClient();

  const { data: goalsConfig, isLoading } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsApi.get(),
  });

  const { data: templates } = useQuery({
    queryKey: ['goals', 'templates'],
    queryFn: () => goalsApi.getTemplates(),
  });

  const applyTemplateMutation = useMutation({
    mutationFn: (templateId: string) => goalsApi.applyTemplate(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const updateGoalsMutation = useMutation({
    mutationFn: ({ goals, primaryFocus }: { goals: TeamGoal[]; primaryFocus?: string }) =>
      goalsApi.update(goals, primaryFocus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const handleSetPrimaryFocus = (category: string) => {
    if (goalsConfig) {
      updateGoalsMutation.mutate({
        goals: goalsConfig.goals,
        primaryFocus: category,
      });
    }
  };

  const handleRemoveGoal = (goalId: string) => {
    if (goalsConfig) {
      const updatedGoals = goalsConfig.goals.filter(g => g.id !== goalId);
      updateGoalsMutation.mutate({
        goals: updatedGoals,
        primaryFocus: goalsConfig.primary_focus,
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Current Goals */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Target className="h-5 w-5" />
            Team Goals
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Set goals to focus AI insights and recommendations
          </p>
        </div>
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : goalsConfig?.goals && goalsConfig.goals.length > 0 ? (
            <div className="space-y-4">
              {goalsConfig.goals.map((goal) => {
                const Icon = GOAL_CATEGORY_ICONS[goal.category] || Target;
                const colorClass = GOAL_CATEGORY_COLORS[goal.category] || 'text-gray-500 bg-gray-500/10';
                const isPrimary = goalsConfig.primary_focus === goal.category;

                return (
                  <div
                    key={goal.id}
                    className={cn(
                      'flex items-start gap-4 p-4 rounded-lg border',
                      isPrimary && 'ring-2 ring-primary'
                    )}
                  >
                    <div className={cn('p-2 rounded-lg', colorClass)}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium">{goal.name}</h3>
                        {isPrimary && (
                          <span className="text-xs px-2 py-0.5 bg-primary text-primary-foreground rounded-full">
                            Primary Focus
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{goal.description}</p>
                      {goal.target_metric && goal.target_value !== undefined && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Target: {goal.target_metric} = {goal.target_value}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {!isPrimary && (
                        <button
                          onClick={() => handleSetPrimaryFocus(goal.category)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                          disabled={updateGoalsMutation.isPending}
                        >
                          Set as Primary
                        </button>
                      )}
                      <button
                        onClick={() => handleRemoveGoal(goal.id)}
                        className="p-1 text-muted-foreground hover:text-destructive"
                        disabled={updateGoalsMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8">
              <Target className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No goals configured yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Add goals from the templates below to focus AI insights
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Goal Templates */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold">Available Goal Templates</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Quick-add common team goals
          </p>
        </div>
        <div className="p-6">
          {templates ? (
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(templates).map(([id, template]) => {
                const Icon = GOAL_CATEGORY_ICONS[template.category] || Target;
                const colorClass = GOAL_CATEGORY_COLORS[template.category] || 'text-gray-500 bg-gray-500/10';
                const isAdded = goalsConfig?.goals.some(g => g.id === id);

                return (
                  <button
                    key={id}
                    onClick={() => !isAdded && applyTemplateMutation.mutate(id)}
                    disabled={isAdded || applyTemplateMutation.isPending}
                    className={cn(
                      'flex items-start gap-3 p-4 rounded-lg border text-left transition-colors',
                      isAdded
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:bg-accent cursor-pointer'
                    )}
                  >
                    <div className={cn('p-2 rounded-lg', colorClass)}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-sm">{template.name}</h3>
                        {isAdded && (
                          <Check className="h-4 w-4 text-green-500" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{template.description}</p>
                    </div>
                    {!isAdded && (
                      <Plus className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
