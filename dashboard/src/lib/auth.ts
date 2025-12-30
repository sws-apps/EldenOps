'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  discord_id: number;
  discord_username: string | null;
  email: string | null;
  github_username: string | null;
}

interface Tenant {
  id: string;
  guild_name: string;
  guild_icon_url: string | null;
  role: 'owner' | 'admin' | 'member';
}

type UserRole = 'owner' | 'admin' | 'member' | null;

// Helper to decode JWT and extract payload
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  tenants: Tenant[];
  currentTenantId: string | null;
  currentRole: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: () => boolean;
  isOwner: () => boolean;
  login: (accessToken: string, refreshToken: string) => Promise<void>;
  logout: () => void;
  refreshAuth: () => Promise<boolean>;
  fetchTenants: () => Promise<void>;
  switchTenant: (tenantId: string) => Promise<void>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      tenants: [],
      currentTenantId: null,
      currentRole: null,
      isAuthenticated: false,
      isLoading: true,

      isAdmin: () => {
        const role = get().currentRole;
        return role === 'owner' || role === 'admin';
      },

      isOwner: () => {
        return get().currentRole === 'owner';
      },

      login: async (accessToken: string, refreshToken: string) => {
        // Extract role from JWT token
        const payload = decodeJwtPayload(accessToken);
        const role = (payload?.role as UserRole) || null;
        set({ accessToken, refreshToken, currentRole: role, isLoading: true });

        try {
          // Fetch user info
          const response = await fetch('/api/v1/auth/me', {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          });

          if (response.ok) {
            const user = await response.json();
            set({ user, isAuthenticated: true, isLoading: false });
            // Fetch tenants after login
            get().fetchTenants();
          } else {
            throw new Error('Failed to fetch user');
          }
        } catch (error) {
          console.error('Login error:', error);
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            tenants: [],
            currentTenantId: null,
            currentRole: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          tenants: [],
          currentTenantId: null,
          currentRole: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },

      refreshAuth: async () => {
        const { refreshToken } = get();

        if (!refreshToken) {
          set({ isLoading: false });
          return false;
        }

        try {
          const response = await fetch('/api/v1/auth/refresh', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (response.ok) {
            const data = await response.json();
            await get().login(data.access_token, data.refresh_token);
            return true;
          }
        } catch (error) {
          console.error('Token refresh error:', error);
        }

        get().logout();
        return false;
      },

      fetchTenants: async () => {
        const { accessToken } = get();
        if (!accessToken) return;

        try {
          const response = await fetch('/api/v1/auth/tenants', {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            set({
              tenants: data.tenants,
              currentTenantId: data.current_tenant_id,
            });
          }
        } catch (error) {
          console.error('Failed to fetch tenants:', error);
        }
      },

      switchTenant: async (tenantId: string) => {
        const { accessToken, tenants } = get();
        if (!accessToken) return;

        try {
          const response = await fetch('/api/v1/auth/tenants/switch', {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${accessToken}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ tenant_id: tenantId }),
          });

          if (response.ok) {
            const data = await response.json();
            // Extract new role from the token
            const payload = decodeJwtPayload(data.access_token);
            const newRole = (payload?.role as UserRole) || null;
            // Or get from tenants list
            const tenant = tenants.find(t => t.id === tenantId);
            const role = newRole || tenant?.role || null;

            set({
              accessToken: data.access_token,
              refreshToken: data.refresh_token,
              currentTenantId: tenantId,
              currentRole: role,
            });
            // Reload the page to refresh all data with new tenant
            window.location.reload();
          }
        } catch (error) {
          console.error('Failed to switch tenant:', error);
        }
      },
    }),
    {
      name: 'eldenops-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        // After hydration, try to restore the session
        if (state?.accessToken) {
          state.refreshAuth();
        } else {
          state?.logout();
        }
      },
    }
  )
);

// Helper to get auth header
export function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuth.getState();
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}
