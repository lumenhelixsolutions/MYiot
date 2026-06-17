import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lightbulb, Power, Thermometer, Video, Search } from 'lucide-react';
import { useApp } from '@/store/AppContext';
import type { DeviceType } from '@/types';

const filters: Array<{ key: DeviceType | 'all'; label: string }> = [
  { key: 'all', label: 'All' }, { key: 'light', label: 'Lights' }, { key: 'plug', label: 'Plugs' },
  { key: 'thermostat', label: 'Thermostats' }, { key: 'camera', label: 'Cameras' },
];

const typeIcon = (t: DeviceType) => {
  if (t === 'light') return Lightbulb; if (t === 'plug') return Power;
  if (t === 'thermostat') return Thermometer; return Video;
};
const typeColor = (t: DeviceType) => {
  if (t === 'light') return '#fbbf24'; if (t === 'plug') return '#10b981';
  if (t === 'thermostat') return '#f97316'; return '#ef4444';
};

const mfrs = ['Philips Hue', 'TP-Link Kasa', 'Nest', 'Ring', 'Wyze', 'IKEA Tradfri', 'LIFX', 'Govee', 'EOOEIES'];

export default function Devices() {
  const { state, togglePower } = useApp();
  const [activeType, setActiveType] = useState<DeviceType | 'all'>('all');
  const [activeMfrs, setActiveMfrs] = useState<string[]>([]);

  const filtered = useMemo(() => {
    let r = state.devices;
    if (activeType !== 'all') r = r.filter(d => d.type === activeType);
    if (activeMfrs.length > 0) r = r.filter(d => activeMfrs.includes(d.manufacturer));
    if (state.searchQuery) { const q = state.searchQuery.toLowerCase(); r = r.filter(d => d.name.toLowerCase().includes(q) || d.room.toLowerCase().includes(q)); }
    return r;
  }, [state.devices, activeType, activeMfrs, state.searchQuery]);

  const toggleMfr = (m: string) => setActiveMfrs(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-2">
        {filters.map(tf => {
          const c = tf.key === 'all' ? state.devices.length : state.devices.filter(d => d.type === tf.key).length;
          return (
            <button key={tf.key} onClick={() => setActiveType(tf.key)}
              className="rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200"
              style={{ backgroundColor: activeType === tf.key ? 'var(--accent-primary)' : 'var(--bg-surface)', color: activeType === tf.key ? '#fff' : 'var(--text-secondary)', border: `1px solid ${activeType === tf.key ? 'var(--accent-primary)' : 'var(--border-subtle)'}` }}>
              {tf.label} <span className="ml-1 text-xs opacity-70">{c}</span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {mfrs.map(m => (
          <button key={m} onClick={() => toggleMfr(m)}
            className="rounded-full px-3 py-1 text-xs font-medium transition-all"
            style={{ backgroundColor: activeMfrs.includes(m) ? 'rgba(99,102,241,0.15)' : 'var(--bg-surface)', color: activeMfrs.includes(m) ? 'var(--accent-primary-light)' : 'var(--text-muted)', border: `1px solid ${activeMfrs.includes(m) ? 'rgba(99,102,241,0.3)' : 'var(--border-subtle)'}` }}>
            {m}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <AnimatePresence mode="popLayout">
          {filtered.map((device, i) => {
            const Icon = typeIcon(device.type);
            const color = typeColor(device.type);
            return (
              <motion.div key={device.id} layout initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ delay: Math.min(i * 0.02, 0.2), duration: 0.3 }}
                className="cursor-pointer rounded-2xl p-4 transition-all duration-200 hover:-translate-y-0.5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(99,102,241,0.2)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-subtle)'; }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${color}15` }}>
                      <Icon className="h-5 w-5" style={{ color }} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{device.name}</p>
                      <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{device.room} · {device.manufacturer}</p>
                    </div>
                  </div>
                  <div className={`status-dot ${device.online ? 'online' : 'offline'}`} />
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ backgroundColor: device.power ? 'rgba(16,185,129,0.1)' : 'rgba(55,65,81,0.3)', color: device.power ? '#10b981' : 'var(--text-muted)' }}>
                    {device.power ? 'ON' : 'OFF'}
                  </span>
                  <button onClick={e => { e.stopPropagation(); togglePower(device.id); }}
                    className="flex h-7 w-12 items-center rounded-full p-0.5 transition-all duration-200" style={{ backgroundColor: device.power ? 'var(--accent-primary)' : 'var(--bg-inset)' }}>
                    <motion.div layout className="h-6 w-6 rounded-full bg-white shadow" style={{ marginLeft: device.power ? 18 : 0 }} transition={{ type: 'spring', stiffness: 500, damping: 30 }} />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
      {filtered.length === 0 && (
        <div className="flex flex-col items-center py-16">
          <Search className="h-10 w-10" style={{ color: 'var(--text-muted)' }} />
          <p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>No devices match</p>
          <button onClick={() => { setActiveType('all'); setActiveMfrs([]); }} className="mt-2 text-sm font-medium" style={{ color: 'var(--accent-primary)' }}>Clear filters</button>
        </div>
      )}
    </div>
  );
}
