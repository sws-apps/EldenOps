'use client';

import { useAuth } from '@/lib/auth';

export type UserRole = 'owner' | 'admin' | 'member';

interface RoleAccessConfig {
  // Whether this role can see team-wide data
  canViewTeamData: boolean;
  // Whether this role can manage settings
  canManageSettings: boolean;
  // Whether this role can view analytics
  canViewAnalytics: boolean;
  // Whether this role can manage projects
  canManageProjects: boolean;
  // Whether this role can view all members
  canViewAllMembers: boolean;
  // Whether this role can view costs/billing
  canViewCosts: boolean;
}

const ROLE_CONFIGS: Record<UserRole, RoleAccessConfig> = {
  owner: {
    canViewTeamData: true,
    canManageSettings: true,
    canViewAnalytics: true,
    canManageProjects: true,
    canViewAllMembers: true,
    canViewCosts: true,
  },
  admin: {
    canViewTeamData: true,
    canManageSettings: true,
    canViewAnalytics: true,
    canManageProjects: true,
    canViewAllMembers: true,
    canViewCosts: false,
  },
  member: {
    canViewTeamData: false,
    canManageSettings: false,
    canViewAnalytics: false,
    canManageProjects: false,
    canViewAllMembers: false,
    canViewCosts: false,
  },
};

export function useRoleAccess() {
  const { currentRole, isAdmin, isOwner } = useAuth();

  const role = currentRole || 'member';
  const config = ROLE_CONFIGS[role as UserRole] || ROLE_CONFIGS.member;

  return {
    role,
    isAdmin: isAdmin(),
    isOwner: isOwner(),
    ...config,

    // Helper to check if user can perform an action
    can: (permission: keyof RoleAccessConfig) => config[permission],

    // Helper for conditional rendering based on role
    forRole: <T>(options: { owner?: T; admin?: T; member?: T; default?: T }): T | undefined => {
      if (role === 'owner' && options.owner !== undefined) return options.owner;
      if (role === 'admin' && options.admin !== undefined) return options.admin;
      if (role === 'member' && options.member !== undefined) return options.member;
      return options.default;
    },
  };
}

// Component wrapper for role-based rendering
export function RoleGate({
  children,
  allowedRoles,
  fallback = null,
}: {
  children: React.ReactNode;
  allowedRoles: UserRole[];
  fallback?: React.ReactNode;
}) {
  const { role } = useRoleAccess();

  if (allowedRoles.includes(role as UserRole)) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}
