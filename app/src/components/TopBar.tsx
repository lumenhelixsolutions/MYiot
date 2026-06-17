import { useLocation } from 'react-router-dom';
import { Search, Bell, Server, WifiOff, Loader2 } from 'lucide-react';
import { useApp } from '@/store/AppContext';

const titles: Record<string, string> = {
  '/': 'Dashboard',
  '/devices': 'Devices',
  '/cameras': 'Camera Monitor',
  '/discovery': 'Discovery',
  '/activity': 'Activity',
  '/settings': 'Settings',
};

export default function TopBar() {
  const loc = useLocation();
  const { state, unackAlerts, setSearch, backendSync } = useApp();
  const online = state.devices.filter(d => d.online).length;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between px-6" style={{ backgroundColor: 'rgba(7,7,13,0.85)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border-subtle)' }}>
      <h1 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{titles[loc.pathname] || 'MYiot'}</h1>
      <div className="flex items-center gap-4">
        {/* Backend connection indicator */}
        <div className="flex items-center gap-1.5 rounded-full px-2.5 py-1" style={{ backgroundColor: backendSync.connected ? 'rgba(16,185,129,0.06)' : backendSync.wsStatus === 'connecting' ? 'rgba(245,158,11,0.06)' : 'rgba(239,68,68,0.06)' }}>
          {backendSync.connected ? <Server className="h-3 w-3" style={{ color: '#10b981' }} /> : backendSync.wsStatus === 'connecting' ? <Loader2 className="h-3 w-3 animate-spin" style={{ color: '#f59e0b' }} /> : <WifiOff className="h-3 w-3" style={{ color: '#ef4444' }} />}
          <span className="text-[10px] font-medium" style={{ color: backendSync.connected ? '#10b981' : backendSync.wsStatus === 'connecting' ? '#f59e0b' : '#ef4444' }}>
            {backendSync.connected ? 'Live' : backendSync.wsStatus === 'connecting' ? 'Syncing' : 'Local'}
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-lg px-3 py-1.5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <Search className="h-3.5 w-3.5" style={{ color: 'var(--text-muted)' }} />
          <input type="text" placeholder="Search..." value={state.searchQuery} onChange={e => setSearch(e.target.value)}
            className="w-44 border-0 bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]" style={{ color: 'var(--text-primary)' }} />
        </div>
        <div className="relative flex items-center gap-2 rounded-full px-3 py-1" style={{ backgroundColor: 'rgba(16,185,129,0.06)' }}>
          <div className="status-dot online" />
          <span className="text-xs font-medium" style={{ color: '#10b981' }}>{online}/{state.devices.length}</span>
        </div>
        <button className="relative flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:bg-white/5" style={{ color: 'var(--text-secondary)' }}>
          <Bell className="h-[18px] w-[18px]" />
          {unackAlerts.length > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white" style={{ backgroundColor: '#ef4444' }}>{unackAlerts.length}</span>
          )}
        </button>
      </div>
    </header>
  );
}
