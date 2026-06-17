import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Palette, Wifi, HardDrive, Key, Shield, ChevronRight, Eye, EyeOff, Trash2, Download, Upload, RefreshCw, AlertTriangle } from 'lucide-react';
import { useApp } from '@/store/AppContext';

const tabs = [
  { key: 'general', icon: Palette, label: 'General' },
  { key: 'manufacturers', icon: Shield, label: 'Mfrs' },
  { key: 'credentials', icon: Key, label: 'Creds' },
  { key: 'network', icon: Wifi, label: 'Network' },
  { key: 'system', icon: HardDrive, label: 'System' },
];

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  return (
    <div className="flex flex-col gap-5">
      <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Settings</h2>
      <div className="flex gap-1 rounded-xl p-1" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)} className="relative flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-all" style={{ color: activeTab === t.key ? 'var(--text-primary)' : 'var(--text-muted)' }}>
            {activeTab === t.key && <motion.div layoutId="st" className="absolute inset-0 rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }} transition={{ type: 'spring', stiffness: 300, damping: 30 }} />}
            <t.icon className="relative z-10 h-4 w-4" /><span className="relative z-10 hidden lg:inline">{t.label}</span>
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
          {activeTab === 'general' && <GeneralTab />}
          {activeTab === 'manufacturers' && <MfrTab />}
          {activeTab === 'credentials' && <CredTab />}
          {activeTab === 'network' && <NetTab />}
          {activeTab === 'system' && <SysTab />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function GeneralTab() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('myiot-theme') as 'dark' | 'light') || 'dark';
  });
  const [accent, setAccent] = useState('indigo');
  const [tempUnit, setTempUnit] = useState('F');
  const [autoDisc, setAutoDisc] = useState(true);
  const accents = [{ k: 'indigo', c: '#6366F1' }, { k: 'cyan', c: '#06b6d4' }, { k: 'violet', c: '#8b5cf6' }, { k: 'emerald', c: '#10b981' }, { k: 'rose', c: '#f43f5e' }, { k: 'amber', c: '#f59e0b' }];

  const applyTheme = (t: 'dark' | 'light') => {
    setTheme(t);
    localStorage.setItem('myiot-theme', t);
    if (t === 'light') document.documentElement.classList.add('light');
    else document.documentElement.classList.remove('light');
  };

  return (
    <div className="flex flex-col gap-4">
      <Sec title="Appearance">
        <Row label="Theme">
          <div className="flex gap-2">
            {(['dark', 'light'] as const).map(t => (
              <button
                key={t}
                onClick={() => applyTheme(t)}
                className="rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-all"
                style={{ backgroundColor: theme === t ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: theme === t ? '#fff' : 'var(--text-muted)' }}
              >{t}</button>
            ))}
          </div>
        </Row>
        <Row label="Accent"><div className="flex gap-2">{accents.map(a => <button key={a.k} onClick={() => setAccent(a.k)} className="h-7 w-7 rounded-full transition-transform hover:scale-110" style={{ backgroundColor: a.c, boxShadow: accent === a.k ? `0 0 0 2px var(--bg-surface), 0 0 0 4px ${a.c}` : 'none' }} />)}</div></Row>
      </Sec>
      <Sec title="Preferences">
        <Row label="Temperature"><div className="flex gap-2">{['F', 'C'].map(u => <button key={u} onClick={() => setTempUnit(u)} className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all" style={{ backgroundColor: tempUnit === u ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: tempUnit === u ? '#fff' : 'var(--text-muted)' }}>&deg;{u}</button>)}</div></Row>
        <Row label="Auto-Discover"><button onClick={() => setAutoDisc(!autoDisc)} className="flex h-6 w-11 items-center rounded-full p-0.5 transition-all" style={{ backgroundColor: autoDisc ? 'var(--accent-primary)' : 'var(--bg-inset)' }}><motion.div layout className="h-5 w-5 rounded-full bg-white shadow" style={{ marginLeft: autoDisc ? 20 : 0 }} transition={{ type: 'spring', stiffness: 500, damping: 30 }} /></button></Row>
      </Sec>
    </div>
  );
}

function MfrTab() {
  const { state, toggleManufacturer } = useApp();
  const [exp, setExp] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{state.manufacturers.filter(m => m.enabled).length} of {state.manufacturers.length} enabled</p>
      {state.manufacturers.map(m => (
        <div key={m.key} className="rounded-xl" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="flex cursor-pointer items-center justify-between px-4 py-3" onClick={() => setExp(exp === m.key ? null : m.key)}>
            <div className="flex items-center gap-3">
              <button onClick={e => { e.stopPropagation(); toggleManufacturer(m.key); }} className="flex h-5 w-9 items-center rounded-full p-0.5 transition-all" style={{ backgroundColor: m.enabled ? 'var(--accent-primary)' : 'var(--bg-inset)' }}><motion.div layout className="h-4 w-4 rounded-full bg-white shadow" style={{ marginLeft: m.enabled ? 14 : 0 }} /></button>
              <div><p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{m.name}</p><p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{m.protocol} · {m.authType}</p></div>
            </div>
            <ChevronRight className="h-4 w-4 transition-transform" style={{ color: 'var(--text-muted)', transform: exp === m.key ? 'rotate(90deg)' : 'none' }} />
          </div>
          <AnimatePresence>{exp === m.key && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><div className="border-t px-4 py-3" style={{ borderColor: 'var(--border-subtle)' }}><div className="grid grid-cols-2 gap-3">{[{ l: 'Protocol', v: m.protocol }, { l: 'Auth', v: m.authType }, { l: 'Port', v: String(m.port || 'Default') }, { l: 'Types', v: m.deviceTypes.join(', ') }].map(i => <div key={i.l}><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{i.l}</p><p className="mt-0.5 text-sm" style={{ color: 'var(--text-primary)' }}>{i.v}</p></div>)}</div></div></motion.div>}</AnimatePresence>
        </div>
      ))}
    </div>
  );
}

function CredTab() {
  const { state, addCredential, removeCredential } = useApp();
  const [showAdd, setShowAdd] = useState(false);
  const [vis, setVis] = useState<Record<string, boolean>>({});
  const [mfr, setMfr] = useState(''); const [at, setAt] = useState('Bridge Token'); const [val, setVal] = useState('');
  const toggleVis = (id: string) => setVis(p => ({ ...p, [id]: !p[id] }));
  const handleAdd = () => { if (!mfr.trim() || !val.trim()) return; addCredential({ id: `c-${Date.now()}`, manufacturer: mfr, authType: at, token: val, lastUsed: Date.now() }); setMfr(''); setVal(''); setShowAdd(false); };
  return (
    <div className="flex flex-col gap-4">
      <button onClick={() => setShowAdd(!showAdd)} className="w-full rounded-xl py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90" style={{ backgroundColor: 'var(--accent-primary)' }}>+ Add Credential</button>
      <AnimatePresence>{showAdd && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden rounded-xl p-4" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}><div className="flex flex-col gap-3"><input value={mfr} onChange={e => setMfr(e.target.value)} placeholder="Manufacturer" className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} /><select value={at} onChange={e => setAt(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}><option>Bridge Token</option><option>OAuth2</option><option>API Key</option><option>Bearer Token</option><option>Basic Auth</option><option>PSK</option></select><input value={val} onChange={e => setVal(e.target.value)} placeholder="Token" type="password" className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} /><button onClick={handleAdd} disabled={!mfr.trim() || !val.trim()} className="rounded-lg py-2 text-sm font-medium text-white disabled:opacity-40" style={{ backgroundColor: 'var(--accent-primary)' }}>Save</button></div></motion.div>}</AnimatePresence>
      {state.credentials.map(c => (
        <div key={c.id} className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center justify-between">
            <div><p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{c.manufacturer}</p><p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{c.authType}</p></div>
            <div className="flex items-center gap-1"><button onClick={() => toggleVis(c.id)} className="rounded-lg p-1.5 hover:bg-white/5">{vis[c.id] ? <EyeOff className="h-4 w-4" style={{ color: 'var(--text-muted)' }} /> : <Eye className="h-4 w-4" style={{ color: 'var(--text-muted)' }} />}</button><button onClick={() => removeCredential(c.id)} className="rounded-lg p-1.5 hover:bg-white/5"><Trash2 className="h-4 w-4" style={{ color: '#ef4444' }} /></button></div>
          </div>
          <p className="mt-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{vis[c.id] ? (c.token || 'N/A') : '••••••••••••'}</p>
        </div>
      ))}
    </div>
  );
}

function NetTab() {
  const listeners = [{ n: 'SSDP', p: 1900, s: 'active' as const }, { n: 'mDNS', p: 5353, s: 'active' as const }, { n: 'UDP Broadcast', p: 9999, s: 'active' as const }, { n: 'HTTP API', p: 8000, s: 'active' as const }, { n: 'WebSocket', p: 8000, s: 'active' as const }];
  return (
    <div className="flex flex-col gap-4">
      <Sec title="Protocol Listeners">{listeners.map(l => <div key={l.n} className="flex items-center justify-between rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-inset)' }}><div className="flex items-center gap-3"><div className={`h-2 w-2 rounded-full ${l.s === 'active' ? 'bg-emerald-500' : 'bg-slate-500'}`} /><span className="text-sm" style={{ color: 'var(--text-primary)' }}>{l.n}</span><span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>Port {l.p}</span></div><span className="text-xs font-medium capitalize" style={{ color: l.s === 'active' ? '#10b981' : 'var(--text-muted)' }}>{l.s}</span></div>)}</Sec>
      <Sec title="Discovery"><Row label="Timeout"><span className="text-sm" style={{ color: 'var(--text-muted)' }}>30s</span></Row><Row label="Range"><span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>192.168.1.0/24</span></Row></Sec>
    </div>
  );
}

function SysTab() {
  const { state } = useApp();
  const [showReset, setShowReset] = useState(false);
  const items = [{ l: 'Version', v: '1.0.0' }, { l: 'Uptime', v: '3d 14h' }, { l: 'Devices', v: String(state.devices.length) }, { l: 'Events', v: String(state.events.length) }, { l: 'Hub ID', v: `myiot-${Math.random().toString(36).substring(2, 8)}` }, { l: 'Build', v: '2026.06.15' }];
  return (
    <div className="flex flex-col gap-4">
      <Sec title="Hub Info"><div className="grid grid-cols-2 gap-3">{items.map(it => <div key={it.l} className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-inset)' }}><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{it.l}</p><p className="mt-1 text-sm font-medium font-mono" style={{ color: 'var(--text-primary)' }}>{it.v}</p></div>)}</div></Sec>
      <Sec title="Maintenance"><div className="flex flex-col gap-2"><button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)' }}><RefreshCw className="h-4 w-4" /> Restart</button><button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)' }}><Download className="h-4 w-4" /> Backup</button><button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: 'var(--bg-inset)', color: 'var(--text-secondary)' }}><Upload className="h-4 w-4" /> Restore</button></div></Sec>
      <div className="rounded-xl p-4" style={{ backgroundColor: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.12)' }}>
        <h3 className="mb-2 text-sm font-semibold" style={{ color: '#ef4444' }}>Factory Reset</h3>
        {!showReset ? <button onClick={() => setShowReset(true)} className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: '#ef4444' }}><AlertTriangle className="h-4 w-4" /> Reset</button>
          : <div><p className="mb-3 text-sm" style={{ color: 'var(--text-secondary)' }}>Delete all data? Cannot be undone.</p><div className="flex gap-2"><button onClick={() => setShowReset(false)} className="rounded-lg px-4 py-2 text-sm" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>Cancel</button></div></div>}
      </div>
    </div>
  );
}

function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{title}</h3>{children}</div>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}><span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>{children}</div>;
}
