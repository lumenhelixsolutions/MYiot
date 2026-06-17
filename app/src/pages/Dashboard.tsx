import { motion } from 'framer-motion';
import { Layers, Wifi, Power, Zap, Video, Lightbulb, Thermometer, Shield, Sun, Moon, Film } from 'lucide-react';
import { useApp } from '@/store/AppContext';

export default function Dashboard() {
  const { state, togglePower, cameras, unackAlerts } = useApp();
  const devices = state.devices;
  const events = state.events;
  const onlineCount = devices.filter(d => d.online).length;
  const onCount = devices.filter(d => d.power).length;
  const roomCount = new Set(devices.map(d => d.room)).size;

  const scenes = [
    { name: 'Morning', icon: Sun, action: () => devices.filter(d => d.type === 'light').forEach(d => { if (!d.power && d.online) togglePower(d.id); }) },
    { name: 'Away', icon: Shield, action: () => devices.filter(d => d.type !== 'thermostat').forEach(d => { if (d.power) togglePower(d.id); }) },
    { name: 'Movie', icon: Film, action: () => {} },
    { name: 'Sleep', icon: Moon, action: () => devices.forEach(d => { if (d.power && d.type !== 'thermostat') togglePower(d.id); }) },
  ];

  const fmtTime = (ts: number) => {
    const d = Date.now() - ts;
    if (d < 60000) return 'Just now';
    if (d < 3600000) return `${Math.floor(d / 60000)}m ago`;
    if (d < 86400000) return `${Math.floor(d / 3600000)}h ago`;
    return `${Math.floor(d / 86400000)}d ago`;
  };

  const getIcon = (type: string) => {
    if (type === 'light') return Lightbulb;
    if (type === 'plug') return Power;
    if (type === 'thermostat') return Thermometer;
    if (type === 'camera') return Video;
    return Layers;
  };

  const getColor = (type: string) => {
    if (type === 'light') return '#fbbf24';
    if (type === 'plug') return '#10b981';
    if (type === 'thermostat') return '#f97316';
    if (type === 'camera') return '#ef4444';
    return '#6366f1';
  };

  return (
    <div className="flex flex-col gap-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Welcome back</h2>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>
          {devices.length} devices · {roomCount} rooms · {onlineCount} online · {cameras.length} cameras · {unackAlerts.length} unack alerts
        </p>
      </motion.div>

      <div className="grid grid-cols-5 gap-4">
        {[
          { label: 'Devices', value: devices.length, icon: Layers, color: '#6366F1' },
          { label: 'Online', value: onlineCount, icon: Wifi, color: '#10b981' },
          { label: 'Active', value: onCount, icon: Power, color: '#06b6d4' },
          { label: 'Cameras', value: cameras.length, icon: Video, color: '#ef4444' },
          { label: 'Alerts', value: unackAlerts.length, icon: Zap, color: '#f59e0b' },
        ].map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.04 * i, duration: 0.35 }}
            className="rounded-2xl p-5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${s.color}15` }}>
              <s.icon className="h-5 w-5" style={{ color: s.color }} />
            </div>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{s.value}</p>
            <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 flex flex-col gap-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Rooms</h3>
          <div className="grid grid-cols-2 gap-3">
            {state.rooms.map((room, i) => (
              <motion.div key={room.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 * i, duration: 0.35 }}
                className={`relative overflow-hidden rounded-2xl p-4 bg-gradient-to-br ${room.gradient}`}
                style={{ border: '1px solid var(--border-subtle)', minHeight: 100 }}>
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                <div className="relative">
                  <p className="text-base font-semibold text-white">{room.name}</p>
                  <p className="mt-1 text-xs text-white/60">{room.deviceCount} devices</p>
                  <div className="mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ backgroundColor: 'rgba(16,185,129,0.2)', color: '#10b981' }}>
                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    {room.activeCount} active
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <h3 className="mt-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Scenes</h3>
          <div className="grid grid-cols-4 gap-3">
            {scenes.map((scene, i) => (
              <motion.button key={scene.name} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.04, duration: 0.3 }}
                onClick={scene.action}
                className="flex flex-col items-center gap-2 rounded-2xl p-4 transition-all hover:scale-[1.02]" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: 'rgba(99,102,241,0.1)' }}>
                  <scene.icon className="h-5 w-5" style={{ color: 'var(--accent-primary)' }} />
                </div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{scene.name}</span>
              </motion.button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Recent Activity</h3>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: '#10b981' }} />
              <span className="text-[11px]" style={{ color: '#10b981' }}>Live</span>
            </div>
          </div>
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto rounded-2xl p-3" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', maxHeight: 420 }}>
            {events.slice(0, 15).map((ev, i) => {
              const Icon = getIcon(state.devices.find(d => d.id === ev.deviceId)?.type ?? '');
              const color = getColor(state.devices.find(d => d.id === ev.deviceId)?.type ?? '');
              return (
                <motion.div key={ev.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.02, duration: 0.3 }}
                  className="flex items-start gap-2.5 rounded-xl p-2.5 transition-colors hover:bg-white/[0.03]">
                  <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: `${color}15` }}>
                    <Icon className="h-3.5 w-3.5" style={{ color }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{ev.description}</p>
                    <p className="mt-0.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>{ev.deviceName || 'System'} · {fmtTime(ev.timestamp)}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
