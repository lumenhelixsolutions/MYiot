import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard, Layers, Scan, Activity, Settings,
  Home, User, Video,
} from 'lucide-react';
import { useApp } from '@/store/AppContext';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/devices', icon: Layers, label: 'Devices' },
  { to: '/cameras', icon: Video, label: 'Monitor' },
  { to: '/discovery', icon: Scan, label: 'Discovery' },
  { to: '/activity', icon: Activity, label: 'Activity' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const { backendSync } = useApp();

  return (
    <aside
      className="glass-panel fixed left-0 top-0 z-40 flex h-screen w-[220px] flex-col"
      style={{ borderRight: '1px solid var(--border-subtle)' }}
    >
      <div className="flex h-14 items-center gap-3 px-5">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-xl shadow-lg"
          style={{ background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)' }}
        >
          <Home className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="text-lg font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>MYiot</span>
          <p className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>Smart Living</p>
        </div>
      </div>

      <nav className="mt-6 flex flex-1 flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)] hover:bg-white/[0.03]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-xl"
                    style={{
                      background: 'linear-gradient(90deg, rgba(99,102,241,0.12), rgba(139,92,246,0.06))',
                      borderLeft: '3px solid #6366F1',
                    }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
                <item.icon className="relative z-10 h-[18px] w-[18px]" />
                <span className="relative z-10">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mx-3 mb-4 rounded-xl px-3 py-2.5" style={{ backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full" style={{ backgroundColor: 'var(--accent-primary)' }}>
            <User className="h-4 w-4 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Admin</span>
            <span className="text-[11px]" style={{ color: backendSync.connected ? '#10b981' : 'var(--text-muted)' }}>
              {backendSync.connected ? 'Hub connected' : 'Local mode'}
            </span>
          </div>
          <div className={`status-dot ml-auto ${backendSync.connected ? 'online' : 'offline'}`} />
        </div>
      </div>
    </aside>
  );
}