'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  MessageSquare,
  Hash,
  Volume2,
  Users,
  Settings,
  Plus,
  Trash2,
  Check,
  Loader2,
} from 'lucide-react';
import { tenantsApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Channel {
  id: string;
  name: string;
  type: 'text' | 'voice' | 'announcement';
  isMonitored: boolean;
}

// Sample channels - would come from API
const SAMPLE_CHANNELS: Channel[] = [
  { id: '1', name: 'general', type: 'text', isMonitored: true },
  { id: '2', name: 'dev-chat', type: 'text', isMonitored: true },
  { id: '3', name: 'standup', type: 'text', isMonitored: true },
  { id: '4', name: 'random', type: 'text', isMonitored: false },
  { id: '5', name: 'voice-meeting', type: 'voice', isMonitored: true },
  { id: '6', name: 'announcements', type: 'announcement', isMonitored: false },
];

export default function DiscordPage() {
  const [channels, setChannels] = useState<Channel[]>(SAMPLE_CHANNELS);

  const { data: tenant, isLoading } = useQuery({
    queryKey: ['tenant', 'current'],
    queryFn: () => tenantsApi.get('current'),
  });

  const toggleChannel = (channelId: string) => {
    setChannels((prev) =>
      prev.map((ch) =>
        ch.id === channelId ? { ...ch, isMonitored: !ch.isMonitored } : ch
      )
    );
  };

  const monitoredCount = channels.filter((ch) => ch.isMonitored).length;
  const textChannels = channels.filter((ch) => ch.type === 'text');
  const voiceChannels = channels.filter((ch) => ch.type === 'voice');

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Discord Integration</h1>
        <p className="text-muted-foreground mt-1">
          Configure which Discord channels are monitored for activity
        </p>
      </div>

      {/* Server info */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-full bg-[#5865F2] flex items-center justify-center">
            <MessageSquare className="h-8 w-8 text-white" />
          </div>
          <div className="flex-1">
            {isLoading ? (
              <div className="space-y-2">
                <div className="h-6 w-32 bg-muted animate-pulse rounded" />
                <div className="h-4 w-48 bg-muted animate-pulse rounded" />
              </div>
            ) : (
              <>
                <h2 className="text-xl font-bold">
                  {tenant?.guild_name || 'Your Discord Server'}
                </h2>
                <p className="text-muted-foreground">
                  {monitoredCount} channels monitored
                </p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 text-green-500 text-sm font-medium">
            <Check className="h-4 w-4" />
            Connected
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Text Channels"
          value={textChannels.length}
          monitored={textChannels.filter((ch) => ch.isMonitored).length}
          icon={Hash}
        />
        <StatCard
          title="Voice Channels"
          value={voiceChannels.length}
          monitored={voiceChannels.filter((ch) => ch.isMonitored).length}
          icon={Volume2}
        />
        <StatCard
          title="Active Users"
          value="24"
          monitored={null}
          icon={Users}
        />
      </div>

      {/* Channel configuration */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Monitored Channels</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Select which channels EldenOps should track for activity metrics
              </p>
            </div>
          </div>
        </div>

        {/* Text channels */}
        <div className="p-6 border-b">
          <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            Text Channels
          </h4>
          <div className="space-y-2">
            {textChannels.map((channel) => (
              <ChannelRow
                key={channel.id}
                channel={channel}
                onToggle={() => toggleChannel(channel.id)}
              />
            ))}
          </div>
        </div>

        {/* Voice channels */}
        <div className="p-6">
          <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            Voice Channels
          </h4>
          <div className="space-y-2">
            {voiceChannels.map((channel) => (
              <ChannelRow
                key={channel.id}
                channel={channel}
                onToggle={() => toggleChannel(channel.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Configuration note */}
      <div className="rounded-lg border bg-muted/30 p-6">
        <div className="flex items-start gap-3">
          <Settings className="h-5 w-5 text-muted-foreground mt-0.5" />
          <div>
            <h3 className="font-semibold">Discord Bot Commands</h3>
            <p className="text-sm text-muted-foreground mt-1">
              You can also configure channels directly in Discord using the following commands:
            </p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              <li>
                <code className="px-1 py-0.5 rounded bg-muted">/config channels add #channel</code> - Add a channel to monitor
              </li>
              <li>
                <code className="px-1 py-0.5 rounded bg-muted">/config channels remove #channel</code> - Stop monitoring a channel
              </li>
              <li>
                <code className="px-1 py-0.5 rounded bg-muted">/config channels list</code> - View all monitored channels
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  monitored,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  monitored: number | null;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-[#5865F2]/10">
          <Icon className="h-5 w-5 text-[#5865F2]" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-muted-foreground">
            {title}
            {monitored !== null && (
              <span className="text-[#5865F2]"> ({monitored} monitored)</span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

function ChannelRow({
  channel,
  onToggle,
}: {
  channel: Channel;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-3">
        {channel.type === 'voice' ? (
          <Volume2 className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Hash className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="font-medium">{channel.name}</span>
      </div>
      <button
        onClick={onToggle}
        className={cn(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          channel.isMonitored ? 'bg-[#5865F2]' : 'bg-muted'
        )}
      >
        <span
          className={cn(
            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
            channel.isMonitored ? 'translate-x-6' : 'translate-x-1'
          )}
        />
      </button>
    </div>
  );
}
