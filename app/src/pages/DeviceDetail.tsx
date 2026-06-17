import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lightbulb, Power, Thermometer, Video, ArrowLeft, ChevronUp, ChevronDown, Flame, Snowflake, Wind, Leaf } from 'lucide-react';
import { useApp } from '@/store/AppContext';
import type { DeviceType, ThermoMode } from '@/types';
import { useState } from 'react';

const typeIcon = (t: DeviceType) => { if (t === 'light') return Lightbulb; if (t === 'plug') return Power; if (t === 'thermostat') return Thermometer; return Video; };
const typeColor = (t: DeviceType) => { if (t === 'light') return '#fbbf24'; if (t === 'plug') return '#10b981'; if (t === 'thermostat') return '#f97316'; return '#ef4444'; };
const typeLabel = (t: DeviceType) => { if (t === 'light') return 'Light'; if (t === 'plug') return 'Smart Plug'; if (t === 'thermostat') return 'Thermostat'; return 'Camera'; };
const presetColors = ['#6366F1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#f97316', '#f1f5f9'];
const lightScenes = [{ name: 'Bright', b: 100, c: '#f1f5f9' }, { name: 'Relax', b: 40, c: '#fbbf24' }, { name: 'Focus', b: 80, c: '#f1f5f9' }, { name: 'Night', b: 15, c: '#818cf8' }, { name: 'Movie', b: 30, c: '#6366F1' }, { name: 'Reading', b: 60, c: '#fbbf24' }];
const modeIcons: Record<ThermoMode, React.ElementType> = { off: Power, heat: Flame, cool: Snowflake, auto: Wind, eco: Leaf };

export default function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const { state, togglePower, updateDevice, removeDevice } = useApp();
  const device = state.devices.find(d => d.id === id);
  const [showRemove, setShowRemove] = useState(false);

  if (!device) return <div className="flex flex-col items-center py-20"><p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Device not found</p></div>;

  const Icon = typeIcon(device.type);
  const color = typeColor(device.type);

  return (
    <div className="flex flex-col gap-5">
      <a href="#/devices" className="flex items-center gap-1.5 text-sm transition-colors hover:opacity-80" style={{ color: 'var(--text-muted)' }}><ArrowLeft className="h-4 w-4" /> Devices</a>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl" style={{ backgroundColor: `${color}15` }}><Icon className="h-7 w-7" style={{ color }} /></div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{device.name}</h2>
            <div className="mt-1 flex items-center gap-2">
              <span className="rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>{device.manufacturer}</span>
              <span className="rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>{device.room}</span>
              <div className="flex items-center gap-1.5"><div className={`status-dot ${device.online ? 'online' : 'offline'}`} /><span className="text-[11px]" style={{ color: device.online ? '#10b981' : 'var(--text-muted)' }}>{device.online ? 'Online' : 'Offline'}</span></div>
            </div>
          </div>
        </div>
        <button onClick={() => togglePower(device.id)} className="flex h-12 w-12 items-center justify-center rounded-2xl transition-all" style={{ backgroundColor: device.power ? `${color}20` : 'var(--bg-elevated)', boxShadow: device.power ? `0 0 20px ${color}30` : 'none' }}>
          <Power className="h-6 w-6" style={{ color: device.power ? color : 'var(--text-muted)' }} />
        </button>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className="rounded-2xl p-6" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        {device.type === 'light' && <LightPanel device={device} updateDevice={updateDevice} />}
        {device.type === 'plug' && <PlugPanel device={device} />}
        {device.type === 'thermostat' && <ThermoPanel device={device} updateDevice={updateDevice} />}
        {device.type === 'camera' && <CamPanel device={device} togglePower={togglePower} />}
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="rounded-2xl p-5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Device Info</h3>
        <div className="grid grid-cols-4 gap-4">
          {[{ l: 'Type', v: typeLabel(device.type) }, { l: 'Model', v: device.model }, { l: 'IP', v: device.ipAddress, m: true }, { l: 'Protocol', v: device.protocol }, { l: 'Firmware', v: device.firmware, m: true }, { l: 'Signal', v: `${device.signalStrength}%` }, { l: 'Last Seen', v: new Date(device.lastSeen).toLocaleTimeString() }, { l: 'ID', v: device.id, m: true }].map(item => (
            <div key={item.l}><p className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{item.l}</p><p className={`mt-1 text-sm font-medium ${item.m ? 'font-mono' : ''}`} style={{ color: 'var(--text-primary)' }}>{item.v}</p></div>
          ))}
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="rounded-2xl p-5" style={{ backgroundColor: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.12)' }}>
        <h3 className="mb-2 text-sm font-semibold" style={{ color: '#ef4444' }}>Danger Zone</h3>
        {!showRemove ? (
          <button onClick={() => setShowRemove(true)} className="rounded-lg px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: '#ef4444' }}>Remove Device</button>
        ) : (
          <div className="flex items-center gap-3">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Confirm removal? This cannot be undone.</p>
            <button onClick={() => removeDevice(device.id)} className="rounded-lg px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: '#ef4444' }}>Confirm</button>
            <button onClick={() => setShowRemove(false)} className="rounded-lg px-4 py-2 text-sm font-medium" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>Cancel</button>
          </div>
        )}
      </motion.div>
    </div>
  );
}

function LightPanel({ device, updateDevice }: { device: import('@/types').Device; updateDevice: (id: string, u: Partial<import('@/types').Device>) => void }) {
  const [brightness, setBrightness] = useState(device.brightness ?? 50);
  const [selColor, setSelColor] = useState(device.color ?? '#6366F1');
  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="mb-2 flex items-center justify-between"><span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Brightness</span><span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{brightness}%</span></div>
        <input type="range" min={0} max={100} value={brightness} onChange={e => { const v = Number(e.target.value); setBrightness(v); updateDevice(device.id, { brightness: v }); }}
          className="h-2 w-full cursor-pointer appearance-none rounded-full" style={{ background: `linear-gradient(to right, var(--accent-primary) ${brightness}%, var(--bg-inset) ${brightness}%)` }} />
      </div>
      <div>
        <span className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Color</span>
        <div className="flex items-center gap-3">
          {presetColors.map(c => <button key={c} onClick={() => { setSelColor(c); updateDevice(device.id, { color: c }); }} className="h-8 w-8 rounded-full transition-transform hover:scale-110" style={{ backgroundColor: c, boxShadow: selColor === c ? `0 0 0 2px var(--bg-surface), 0 0 0 4px ${c}` : 'none' }} />)}
          <div className="ml-2 flex items-center gap-2"><input type="color" value={selColor} onChange={e => { setSelColor(e.target.value); updateDevice(device.id, { color: e.target.value }); }} className="h-8 w-8 cursor-pointer rounded border-0 bg-transparent p-0" /><span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{selColor.toUpperCase()}</span></div>
        </div>
      </div>
      <div>
        <span className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Scenes</span>
        <div className="flex flex-wrap gap-2">
          {lightScenes.map(s => <button key={s.name} onClick={() => { setBrightness(s.b); setSelColor(s.c); updateDevice(device.id, { brightness: s.b, color: s.c }); }} className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:scale-105" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>{s.name}</button>)}
        </div>
      </div>
    </div>
  );
}

function PlugPanel({ device: _device }: { device: import('@/types').Device }) {
  const usage = [12, 8, 5, 15, 45, 62, 58, 38, 25, 18, 12, 10, 8, 6, 5, 8, 22, 48, 55, 42, 30, 20, 15, 10];
  const maxU = Math.max(...usage);
  return (
    <div>
      <div className="mb-3 flex items-center justify-between"><span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Energy (24h)</span><span className="text-xs" style={{ color: 'var(--text-muted)' }}>~1.2 kWh</span></div>
      <div className="flex h-28 items-end gap-[2px]">{usage.map((v, i) => <div key={i} className="flex-1 rounded-sm" style={{ height: `${(v / maxU) * 100}%`, backgroundColor: i >= 6 && i <= 18 ? 'var(--accent-primary)' : 'rgba(99,102,241,0.25)', minHeight: 2 }} />)}</div>
      <div className="mt-1 flex justify-between">{['12a', '3a', '6a', '9a', '12p', '3p', '6p', '9p'].map((h, i) => <span key={i} className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{h}</span>)}</div>
    </div>
  );
}

function ThermoPanel({ device, updateDevice }: { device: import('@/types').Device; updateDevice: (id: string, u: Partial<import('@/types').Device>) => void }) {
  const [target, setTarget] = useState(device.targetTemp ?? 72);
  const [mode, setMode] = useState<ThermoMode>(device.mode ?? 'auto');
  const hTemp = (d: number) => { const n = Math.round((target + d) * 2) / 2; if (n >= 60 && n <= 90) { setTarget(n); updateDevice(device.id, { targetTemp: n }); } };
  const hMode = (m: ThermoMode) => { setMode(m); updateDevice(device.id, { mode: m }); };
  const pct = ((target - 60) / 30) * 100;
  return (
    <div className="flex flex-col items-center gap-6">
      <div className="relative flex h-52 w-52 items-center justify-center">
        <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 200 200">
          <circle cx="100" cy="100" r="88" fill="none" stroke="var(--bg-inset)" strokeWidth="12" />
          <circle cx="100" cy="100" r="88" fill="none" stroke="url(#tg)" strokeWidth="12" strokeLinecap="round" strokeDasharray={`${(pct / 100) * 553} 553`} />
          <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stopColor="#6366F1" /><stop offset="100%" stopColor="#f97316" /></linearGradient></defs>
        </svg>
        <div className="flex flex-col items-center"><span className="text-4xl font-bold" style={{ color: 'var(--text-primary)' }}>{target}&deg;</span><span className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Target</span><span className="mt-1 text-sm font-medium" style={{ color: '#f97316' }}>{device.currentTemp}&deg; current</span></div>
        <button onClick={() => hTemp(-0.5)} className="absolute left-0 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronDown className="h-5 w-5" style={{ color: 'var(--text-secondary)' }} /></button>
        <button onClick={() => hTemp(0.5)} className="absolute right-0 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronUp className="h-5 w-5" style={{ color: 'var(--text-secondary)' }} /></button>
      </div>
      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Humidity: {device.humidity}%</span>
      <div className="flex gap-2">
        {(['off', 'heat', 'cool', 'auto', 'eco'] as ThermoMode[]).map(m => {
          const MIcon = modeIcons[m];
          return <button key={m} onClick={() => hMode(m)} className="flex flex-col items-center gap-1 rounded-xl px-4 py-2 transition-all" style={{ backgroundColor: mode === m ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: mode === m ? '#fff' : 'var(--text-muted)' }}><MIcon className="h-4 w-4" /><span className="text-[11px] font-medium capitalize">{m}</span></button>;
        })}
      </div>
    </div>
  );
}

function CamPanel({ device, togglePower }: { device: import('@/types').Device; togglePower: (id: string) => void }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="relative aspect-video w-full overflow-hidden rounded-2xl" style={{ backgroundColor: 'var(--bg-inset)' }}>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Video className="h-12 w-12" style={{ color: 'var(--text-muted)' }} />
          <p className="mt-2 text-sm" style={{ color: 'var(--text-muted)' }}>{device.name}</p>
          <p className="mt-1 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{device.streamUrl}</p>
        </div>
        {device.power && device.online && (
          <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full px-2 py-1" style={{ backgroundColor: 'rgba(239,68,68,0.85)' }}>
            <div className="h-2 w-2 animate-pulse rounded-full bg-white" /><span className="text-[11px] font-bold text-white">LIVE</span>
          </div>
        )}
        {!device.power && (
          <div className="absolute inset-0 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="flex flex-col items-center gap-2"><Power className="h-8 w-8" style={{ color: 'var(--text-muted)' }} /><span className="text-sm font-medium text-white">Privacy Mode</span></div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between">
        <button onClick={() => togglePower(device.id)} className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all" style={{ backgroundColor: !device.power ? 'rgba(245,158,11,0.1)' : 'var(--bg-elevated)', color: !device.power ? '#f59e0b' : 'var(--text-secondary)' }}>
          <Power className="h-4 w-4" />{!device.power ? 'Privacy On' : 'Privacy Off'}</button>
        <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{device.signalStrength}% signal · 1080p</span>
      </div>
    </div>
  );
}
