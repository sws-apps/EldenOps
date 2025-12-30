'use client';

import { createContext, useContext, ReactNode, useState, useCallback } from 'react';
import { useWebSocket, WebSocketMessage } from '@/hooks/useWebSocket';

interface WebSocketContextValue {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  notifications: Notification[];
  clearNotifications: () => void;
}

interface Notification {
  id: string;
  type: 'attendance' | 'github' | 'discord';
  title: string;
  message: string;
  timestamp: Date;
  data?: Record<string, unknown>;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider');
  }
  return context;
}

interface WebSocketProviderProps {
  children: ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const newNotification: Notification = {
      ...notification,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    };
    setNotifications((prev) => [newNotification, ...prev].slice(0, 50)); // Keep last 50
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const handleAttendanceUpdate = useCallback((data: Record<string, unknown>) => {
    const username = data.discord_username as string || 'Someone';
    const status = data.status as string || 'updated';
    const eventType = data.event_type as string || '';

    let message = `${username} is now ${status}`;
    if (eventType === 'checkin') {
      message = `${username} checked in`;
    } else if (eventType === 'checkout') {
      message = `${username} checked out`;
    } else if (eventType === 'break_start') {
      message = `${username} went on break`;
    } else if (eventType === 'break_end') {
      message = `${username} is back from break`;
    }

    addNotification({
      type: 'attendance',
      title: 'Attendance Update',
      message,
      data,
    });
  }, [addNotification]);

  const handleGitHubEvent = useCallback((data: Record<string, unknown>) => {
    const eventType = data.event_type as string || 'event';
    const repo = data.repo_full_name as string || '';
    const user = data.user as string || 'Someone';
    const title = data.title as string || '';

    let message = `${user} triggered ${eventType} on ${repo}`;
    if (eventType === 'push') {
      message = `${user} pushed to ${repo}`;
    } else if (eventType === 'pull_request') {
      message = `${user} opened PR: ${title}`;
    } else if (eventType === 'issues') {
      message = `${user} opened issue: ${title}`;
    }

    addNotification({
      type: 'github',
      title: 'GitHub Activity',
      message,
      data,
    });
  }, [addNotification]);

  const { isConnected, lastMessage } = useWebSocket({
    onAttendanceUpdate: handleAttendanceUpdate,
    onGitHubEvent: handleGitHubEvent,
    autoInvalidateQueries: true,
  });

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        lastMessage,
        notifications,
        clearNotifications,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}
