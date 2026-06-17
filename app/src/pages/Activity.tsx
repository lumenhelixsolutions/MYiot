import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Power, Thermometer, Activity as AIcon, Zap, Shield, AlertTriangle, Wifi, Lock, Video } from 'lucide-react';
import { useApp } from '@/store/AppContext';
import type { ActivityEvent } from '@/types';

const cfg: Record<ActivityEvent['type'], { icon: React.ElementType; color: string; label: string }> = {
  power_on: { icon: Power, color: '#10b981', label: 'ON' },
  power_off: { icon: Power, color: '#475569', label: 'OFF' },
  temperature: { icon: Thermometer, color: '#f97316', label: 'Temp' },
  motion: { icon: Video, color: '#8b5cf6', label: 'Motion' },
  zone_breach: { icon: AlertTriangle, color: '#ef4444', label: 'Zone' },
  alert_triggered: { icon: Zap, color: '#f59e0b', label: 'Alert' },
  connection: { icon: Wifi, color: '#06b6d4', label: 'Conn' },
  automation: { icon: Shield, color: '#6366f1', label: 'Auto' },
  error: { icon: AlertTriangle, color: '#ef4444', label: 'Error' },
  discovery: { icon: AIcon, color: '#10b981', label: 'Disc' },
  auth: { icon: Lock, color: '#f59e0b', label: 'Auth' },
};

const ft: Array<ActivityEvent['type'] | 'all'> = ['all', 'power_on', 'power_off', 'motion', 'zone_breach', 'alert_triggered', 'temperature', 'connection', 'discovery', 'automation', 'error'];

export default function Activity() {
  const { state, dispatch } = useApp();
  const [filter, setFilter] = useState<ActivityEvent['type'] | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const events = state.events;

  const filtered = useMemo(() => filter === 'all' ? events : events.filter(e => e.type === filter), [events, filter]);

  const fmt = (ts: number) => { const d = Date.now() - ts; if (d < 60000) return 'Just now'; if (d < 3600000) return `${Math.floor(d / 60000)}m`; if (d < 86400000) return `${Math.floor(d / 3600000)}h`; if (d < 172800000) return 'Yest'; return `${Math.floor(d / 86400000)}d`; };

  const groups = useMemo(() => {
    const g: { label: string; events: ActivityEvent[] }[] = [];
    const t: ActivityEvent[] = []; const y: ActivityEvent[] = []; const o: ActivityEvent[] = [];
    filtered.forEach(e => { const d = Date.now() - e.timestamp; if (d < 86400000) t.push(e); else if (d < 172800000) y.push(e); else o.push(e); });
    if (t.length) g.push({ label: 'Today', events: t }); if (y.length) g.push({ label: 'Yesterday', events: y }); if (o.length) g.push({ label: 'Earlier', events: o });
    return g;
  }, [filtered]);

  const stats = { total: events.length, errors: events.filter(e => e.type === 'error').length, warns: events.filter(e => e.type === 'connection' || e.type === 'error').length, discs: events.filter(e => e.type === 'discovery').length };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Activity Log</h2>
          <div className="flex items-center gap-1.5"><div className="h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: '#10b981' }} /><span className="text-[11px]" style={{ color: '#10b981' }}>Live</span></div>
        </div>
        <button onClick={() => dispatch({ type: 'CLEAR_EVENTS' })} className="rounded-lg px-3 py-1.5 text-xs font-medium" style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>Clear All</button>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[{ l: 'Total', v: stats.total, c: '#6366F1' }, { l: 'Errors', v: stats.errors, c: '#ef4444' }, { l: 'Warnings', v: stats.warns, c: '#f59e0b' }, { l: 'Discoveries', v: stats.discs, c: '#10b981' }].map(s => (
          <div key={s.l} className="rounded-xl p-3" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <p className="text-lg font-bold" style={{ color: s.c }}>{s.v}</p><p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{s.l}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {ft.map(f => {
          const c = f === 'all' ? events.length : events.filter(e => e.type === f).length;
          return <button key={f} onClick={() => setFilter(f)} className="rounded-full px-3 py-1 text-xs font-medium transition-all" style={{ backgroundColor: filter === f ? 'var(--accent-primary)' : 'var(--bg-surface)', color: filter === f ? '#fff' : 'var(--text-muted)', border: `1px solid ${filter === f ? 'var(--accent-primary)' : 'var(--border-subtle)'}` }}>{f === 'all' ? 'All' : cfg[f].label} ({c})</button>;
        })}
      </div>

      <div className="flex flex-col gap-4">
        {groups.map(g => (
          <div key={g.label}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{g.label}</h3>
            <div className="flex flex-col gap-1.5">
              {g.events.map((ev, i) => {
                const c = cfg[ev.type]; const Icon = c.icon; const isExp = expanded === ev.id;
                return (
                  <motion.div key={ev.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.01 }}
                    onClick={() => setExpanded(isExp ? null : ev.id)} className="cursor-pointer rounded-xl p-3 transition-colors hover:bg-white/[0.02]" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: `${c.color}15` }}><Icon className="h-4 w-4" style={{ color: c.color }} /></div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{ev.description}</p>
                        <p className="mt-0.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>{ev.deviceName || 'System'} · {fmt(ev.timestamp)}</p>
                      </div>
                      <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: `${c.color}10`, color: c.color }}>{c.label}</span>
                    </div>
                    {isExp && ev.details && <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-2 overflow-hidden"><pre className="rounded-lg p-2 font-mono text-[11px]" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-muted)' }}>{JSON.stringify(ev.details, null, 2)}</pre></motion.div>}
                  </motion.div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && <div className="flex flex-col items-center py-16"><AIcon className="h-10 w-10" style={{ color: 'var(--text-muted)' }} /><p className="mt-3 text-sm" style={{ color: 'var(--text-muted)' }}>No events</p></div>}
    </div>
  );
}
