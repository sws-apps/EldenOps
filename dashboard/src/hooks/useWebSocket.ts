'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth';

export type WebSocketEventType = 'attendance_update' | 'discord_event' | 'github_event' | 'ping';

export interface WebSocketMessage {
  type: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface UseWebSocketOptions {
  onAttendanceUpdate?: (data: Record<string, unknown>) => void;
  onDiscordEvent?: (data: Record<string, unknown>) => void;
  onGitHubEvent?: (data: Record<string, unknown>) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  autoInvalidateQueries?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onAttendanceUpdate,
    onDiscordEvent,
    onGitHubEvent,
    onConnect,
    onDisconnect,
    autoInvalidateQueries = true,
  } = options;

  const { currentTenantId, accessToken, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const connect = useCallback(() => {
    if (!currentTenantId || !accessToken || !isAuthenticated) {
      return;
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, '') || 'localhost:8000';
    const wsUrl = `${protocol}//${host}/api/v1/ws/${currentTenantId}?token=${accessToken}`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        onConnect?.();
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Disconnected', event.code, event.reason);
        setIsConnected(false);
        onDisconnect?.();

        // Attempt reconnection after 5 seconds (unless intentionally closed)
        if (event.code !== 1000 && event.code !== 4001 && event.code !== 4003) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[WebSocket] Attempting reconnection...');
            connect();
          }, 5000);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);

          // Handle ping/pong
          if (message.type === 'ping') {
            ws.send('pong');
            return;
          }

          console.log('[WebSocket] Received:', message.type, message.data);

          // Handle different event types
          switch (message.type) {
            case 'attendance_update':
              onAttendanceUpdate?.(message.data);
              if (autoInvalidateQueries) {
                // Invalidate attendance-related queries - match exact keys used in dashboard
                // Using partial key match: ['attendance'] matches ['attendance', 'status'], ['attendance', 'summary'], etc.
                queryClient.invalidateQueries({ queryKey: ['attendance'] });
              }
              break;

            case 'discord_event':
              onDiscordEvent?.(message.data);
              if (autoInvalidateQueries) {
                queryClient.invalidateQueries({ queryKey: ['discord'] });
                queryClient.invalidateQueries({ queryKey: ['attendance'] });
              }
              break;

            case 'github_event':
              onGitHubEvent?.(message.data);
              if (autoInvalidateQueries) {
                // Invalidate GitHub-related queries - match keys used in dashboard
                // ['github'] will match ['github', 'summary', 30], ['github', 'insights', 30], etc.
                queryClient.invalidateQueries({ queryKey: ['github'] });
              }
              break;
          }
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[WebSocket] Failed to connect:', err);
    }
  }, [
    currentTenantId,
    accessToken,
    isAuthenticated,
    queryClient,
    onAttendanceUpdate,
    onDiscordEvent,
    onGitHubEvent,
    onConnect,
    onDisconnect,
    autoInvalidateQueries,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const send = useCallback((data: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(message);
    }
  }, []);

  // Connect when authenticated and tenant is available
  useEffect(() => {
    if (isAuthenticated && currentTenantId && accessToken) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [isAuthenticated, currentTenantId, accessToken, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect,
    send,
  };
}
