'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, Menu, Moon, Sun, LogOut, User, Building2, ChevronDown, Check, Globe, Wifi, WifiOff } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAuth } from '@/lib/auth';
import { useTimezone, TIMEZONE_CONFIG, type TimezoneOption } from '@/lib/timezone';
import { useWebSocketContext } from '@/components/providers/WebSocketProvider';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { cn } from '@/lib/utils';

export function Header() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { user, logout, tenants, currentTenantId, fetchTenants, switchTenant } = useAuth();
  const { timezone, setTimezone } = useTimezone();
  const { isConnected, notifications } = useWebSocketContext();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  const currentTenant = tenants.find(t => t.id === currentTenantId);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const handleSwitchTenant = (tenantId: string) => {
    if (tenantId !== currentTenantId) {
      switchTenant(tenantId);
    }
  };

  return (
    <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-border bg-card px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
      {/* Mobile menu button */}
      <button
        type="button"
        className="-m-2.5 p-2.5 text-muted-foreground lg:hidden"
        onClick={() => setMobileMenuOpen(true)}
      >
        <Menu className="h-6 w-6" />
      </button>

      {/* Separator */}
      <div className="h-6 w-px bg-border lg:hidden" />

      <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
        {/* Tenant switcher */}
        {tenants.length > 0 && (
          <div className="flex items-center">
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-accent transition-colors text-sm">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium truncate max-w-[200px]">
                    {currentTenant?.guild_name || 'Select Workspace'}
                  </span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </button>
              </DropdownMenu.Trigger>

              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  className="z-50 min-w-[220px] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80"
                  align="start"
                  sideOffset={5}
                >
                  <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    Switch Workspace
                  </div>
                  {tenants.map((tenant) => (
                    <DropdownMenu.Item
                      key={tenant.id}
                      className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent gap-2"
                      onClick={() => handleSwitchTenant(tenant.id)}
                    >
                      <div className="h-6 w-6 rounded bg-primary/10 flex items-center justify-center text-xs font-medium">
                        {tenant.guild_name[0]?.toUpperCase()}
                      </div>
                      <span className="flex-1 truncate">{tenant.guild_name}</span>
                      {tenant.id === currentTenantId && (
                        <Check className="h-4 w-4 text-primary" />
                      )}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-x-4 lg:gap-x-6">
          {/* Timezone switcher */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-accent transition-colors text-sm">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{TIMEZONE_CONFIG[timezone].shortLabel()}</span>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="z-50 min-w-[160px] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80"
                align="end"
                sideOffset={5}
              >
                <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                  Timezone
                </div>
                {(Object.keys(TIMEZONE_CONFIG) as TimezoneOption[]).map((tz) => (
                  <DropdownMenu.Item
                    key={tz}
                    className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent gap-2"
                    onClick={() => setTimezone(tz)}
                  >
                    <span className="flex-1">
                      {TIMEZONE_CONFIG[tz].label}
                      <span className="text-muted-foreground ml-1">
                        ({TIMEZONE_CONFIG[tz].shortLabel()})
                      </span>
                    </span>
                    {tz === timezone && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>

          {/* Real-time connection status */}
          <div
            className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-colors",
              isConnected
                ? "bg-green-500/10 text-green-600 dark:text-green-400"
                : "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
            )}
            title={isConnected ? "Real-time updates active" : "Connecting..."}
          >
            {isConnected ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                <span className="hidden sm:inline">Live</span>
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3" />
                <span className="hidden sm:inline">Offline</span>
              </>
            )}
          </div>

          {/* Theme toggle */}
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <Sun className="h-5 w-5 hidden dark:block" />
            <Moon className="h-5 w-5 block dark:hidden" />
          </button>

          {/* Notifications */}
          <button className="p-2 text-muted-foreground hover:text-foreground transition-colors relative">
            <Bell className="h-5 w-5" />
            {/* Notification badge - show count from real-time notifications */}
            {notifications.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center">
                {notifications.length > 9 ? '9+' : notifications.length}
              </span>
            )}
          </button>

          {/* Separator */}
          <div className="hidden lg:block lg:h-6 lg:w-px lg:bg-border" />

          {/* User dropdown */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex items-center gap-x-3 p-1.5 rounded-lg hover:bg-accent transition-colors">
                <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground font-medium text-sm">
                  {user?.discord_username?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="hidden lg:flex lg:items-center">
                  <span className="text-sm font-semibold">
                    {user?.discord_username || 'User'}
                  </span>
                </span>
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="z-50 min-w-[180px] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80"
                align="end"
                sideOffset={5}
              >
                <DropdownMenu.Item
                  className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent gap-2"
                  onClick={() => router.push('/dashboard/settings')}
                >
                  <User className="h-4 w-4" />
                  Profile
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <DropdownMenu.Item
                  className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent gap-2 text-red-500"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </div>
    </header>
  );
}
